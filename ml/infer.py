"""Single-image inference for the backend: calibrated grade, abstention, Grad-CAM, similar cases.

Lane B wraps this (api/inference.py) instead of re-implementing it, so serving
uses exactly the preprocessing, temperature and thresholds that evaluate.py
fitted on the validation split.

    from infer import RetinaModel
    m = RetinaModel("artifacts")            # model.pt, calibration.json, train_index.npz
    out = m.predict(rgb_uint8)              # {"prediction", "recommendation", "evidence", "priority", "model"}

Quality gating is NOT done here (lane B runs ml/quality.py first).
Grad-CAM shows the image regions that most influenced the predicted grade. It is
coarse (one cell is about 32 px of the model input) and is not lesion detection.
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch

from common import (GRADE_LABELS, REFERABLE_MIN_GRADE, heatmap_to_original, load_checkpoint, preprocess,
                    to_tensor_array)

HEATMAP_NOTE = ("Grad-CAM: image regions that most influenced the predicted grade. "
                "Coarse; not lesion detection.")
HEATMAP_MAX_SIDE = 512  # Grad-CAM is ~16x16 cells; more pixels add size, not detail (contract cap: 1024)


def recommendation(pred: dict | None) -> str:
    """Contract section 1, 'Recommendation text' (first matching row wins)."""
    if pred is None:
        return "Image not gradable. Please retake the photo (see reasons)."
    if pred["abstained"]:
        return "Model is not confident. Routed to an ophthalmologist for review."
    if pred["referable"] and pred["grade"] >= 3:
        return "Urgent referral to an ophthalmologist is suggested."
    if pred["referable"]:
        return "Referral to an ophthalmologist is suggested."
    return "No referable DR suggested by the model. Re-screen as per local protocol."


def priority(pred: dict | None) -> float | None:
    """Contract section 1, 'Triage priority' (a heuristic, not clinically validated)."""
    if pred is None:
        return None
    p = pred["referable_prob"] + 0.5 * (1 - pred["confidence"]) + (0.25 if pred["abstained"] else 0.0)
    return round(float(p), 3)


def _colourise(cam: np.ndarray) -> np.ndarray:
    """[0,1] heatmap -> RGBA uint8 (jet colours, alpha grows with activation)."""
    jet = cv2.applyColorMap((cam * 255).astype(np.uint8), cv2.COLORMAP_JET)  # BGR
    alpha = (np.clip((cam - 0.15) / 0.85, 0, 1) * 200).astype(np.uint8)       # weak areas transparent
    jet[alpha == 0] = 0  # invisible pixels need no colour; keeps the PNG small
    return np.dstack([jet, alpha])  # BGRA, as cv2.imencode expects


def _png_data_uri(bgra: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", bgra)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()


class RetinaModel:
    def __init__(self, artifacts_dir, device: str | None = None):
        a = Path(artifacts_dir)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model, self.meta = load_checkpoint(a / "model.pt", self.device)
        self.cal = json.loads((a / "calibration.json").read_text())
        if self.cal.get("fitted_on") != "validation":
            raise ValueError("calibration.json must be fitted on the validation split")
        idx = np.load(a / "train_index.npz")  # training split only (see embed.py)
        self.index_emb = idx["emb"].astype(np.float32)
        self.index_ids = idx["id_code"]
        self.index_grades = idx["grade"].astype(int)
        self.size = int(self.meta["img_size"])
        self.clahe = bool(self.meta.get("clahe", True))

    @property
    def model_info(self) -> dict:
        return {"version": self.meta.get("version", "unknown"), "mock": False,
                "temperature": self.cal["temperature"], "abstain_threshold": self.cal["abstain_threshold"],
                "referable_threshold": self.cal["referable_threshold"], "calibrated_on": "validation"}

    def predict(self, rgb: np.ndarray, with_evidence: bool = True, k: int = 3) -> dict:
        t0 = time.perf_counter()
        img, box = preprocess(rgb, self.size, clahe=self.clahe)
        x = torch.from_numpy(to_tensor_array(img))[None].to(self.device)

        # One forward pass gives logits, the pooled embedding and the Grad-CAM features.
        with torch.enable_grad():
            feats = self.model.forward_features(x)
            feats.retain_grad()
            logits = self.model.forward_head(feats)
            probs = torch.softmax(logits.detach() / self.cal["temperature"], dim=1)[0].cpu().numpy()
            grade = int(probs.argmax())
            if with_evidence:
                self.model.zero_grad(set_to_none=True)
                logits[0, grade].backward()

        conf = float(probs.max())
        ref_p = float(probs[REFERABLE_MIN_GRADE:].sum())
        pred = {
            "grade": grade,
            "grade_label": GRADE_LABELS[grade],
            "probs": [round(float(p), 4) for p in probs],
            "confidence": round(conf, 4),
            "abstained": conf < self.cal["abstain_threshold"],
            "referable": ref_p >= self.cal["referable_threshold"],
            "referable_prob": round(ref_p, 4),
        }
        out = {"prediction": pred, "recommendation": recommendation(pred), "priority": priority(pred),
               "evidence": None, "model": self.model_info}

        if with_evidence:
            f, g = feats.detach()[0], feats.grad[0]
            cam = torch.relu((g.mean(dim=(1, 2))[:, None, None] * f).sum(0)).cpu().numpy()
            cam = cam / cam.max() if cam.max() > 0 else cam
            cam_in = cv2.resize(cam, (self.size, self.size), interpolation=cv2.INTER_LINEAR)
            full = heatmap_to_original(cam_in, box, rgb.shape[:2])
            h, w = full.shape
            s = min(1.0, HEATMAP_MAX_SIDE / max(h, w))
            if s < 1.0:
                full = cv2.resize(full, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)

            with torch.no_grad():
                emb = self.model.forward_head(feats.detach(), pre_logits=True)
                emb = torch.nn.functional.normalize(emb.float(), dim=1)[0].cpu().numpy()
            sims = self.index_emb @ emb
            top = self._distinct_top(sims, k)
            out["evidence"] = {
                "heatmap_png": _png_data_uri(_colourise(full)),
                "heatmap_note": HEATMAP_NOTE,
                "similar": [{"id_code": str(self.index_ids[i]), "grade": int(self.index_grades[i]),
                             "grade_label": GRADE_LABELS[int(self.index_grades[i])],
                             "distance": round(float(1 - sims[i]), 4),
                             "image_url": f"/api/similar/{self.index_ids[i]}.jpg"} for i in top],
            }
        out["latency_ms"] = round((time.perf_counter() - t0) * 1000)
        return out

    def _distinct_top(self, sims: np.ndarray, k: int, dup_sim: float = 0.99) -> list[int]:
        """Top-k most similar training images, skipping near-identical copies.

        APTOS contains duplicate photos; without this the same image can be shown
        twice as two 'similar cases'.
        """
        picked: list[int] = []
        for i in np.argsort(-sims)[: k * 20]:
            if all(float(self.index_emb[i] @ self.index_emb[j]) < dup_sim for j in picked):
                picked.append(int(i))
                if len(picked) == k:
                    break
        return picked


if __name__ == "__main__":
    import argparse
    from common import load_rgb

    ap = argparse.ArgumentParser(description="Run inference on one image and print the JSON (heatmap truncated).")
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--save_heatmap", default="", help="optional path to save the heatmap overlay as PNG")
    a = ap.parse_args()
    m = RetinaModel(a.artifacts)
    rgb = load_rgb(a.image)
    r = m.predict(rgb)
    if a.save_heatmap and r["evidence"]:
        raw = base64.b64decode(r["evidence"]["heatmap_png"].split(",", 1)[1])
        hm = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
        base = cv2.resize(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), (hm.shape[1], hm.shape[0]))
        a_ = hm[..., 3:4].astype(np.float32) / 255
        cv2.imwrite(a.save_heatmap, (base * (1 - a_) + hm[..., :3] * a_).astype(np.uint8))
    if r["evidence"]:
        r["evidence"]["heatmap_png"] = r["evidence"]["heatmap_png"][:60] + "..."
    print(json.dumps(r, indent=2))
