"""How does performance degrade on bad images, and does the quality gate catch them?

Applies synthetic degradations to the RAW held-out test images (before
preprocessing, as a bad camera would), runs the trained model with the
calibration fixed on validation, and reports per condition: accuracy, QWK,
referable sensitivity/specificity, abstention rate, and (if ml/quality.py and
its thresholds are available) the share of images the quality gate rejects plus
accuracy on the images it lets through.

Uses the test split, but only to *measure*: nothing is fitted or tuned here.
Output: degradation.json and degradation.csv in --out.
"""
from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch

from common import REFERABLE_MIN_GRADE, load_checkpoint, load_rgb, preprocess, referable_prob, save_json, to_tensor_array
from evaluate import binary_stats, qwk, safe_auc, softmax

CONDITIONS = {
    "original": lambda im, s: im,
    "blur_mild": lambda im, s: cv2.GaussianBlur(im, (0, 0), 2 * s),
    "blur_strong": lambda im, s: cv2.GaussianBlur(im, (0, 0), 5 * s),
    "blur_severe": lambda im, s: cv2.GaussianBlur(im, (0, 0), 10 * s),
    "dark_50": lambda im, s: (im.astype(np.float32) * 0.5).astype(np.uint8),
    "dark_25": lambda im, s: (im.astype(np.float32) * 0.25).astype(np.uint8),
    "dark_12": lambda im, s: (im.astype(np.float32) * 0.12).astype(np.uint8),
    "overexposed": lambda im, s: np.clip(im.astype(np.float32) * 1.8 + 30, 0, 255).astype(np.uint8),
    "low_contrast": lambda im, s: np.clip((im.astype(np.float32) - im.mean()) * 0.35 + im.mean(), 0, 255
                                          ).astype(np.uint8),
    "jpeg_q8": lambda im, s: cv2.imdecode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 8])[1],
                                          cv2.IMREAD_UNCHANGED),
}

_A = None


def _init(a):
    global _A, _quality, _thr
    _A = a
    _quality, _thr = None, None
    if a.quality_thresholds and Path(a.quality_thresholds).exists():
        try:
            import quality as q  # lane B's module (ml/quality.py)
            _quality, _thr = q, json.loads(Path(a.quality_thresholds).read_text())
        except Exception as e:  # noqa: BLE001
            print("quality gate unavailable:", e, flush=True)


def _work(item):
    id_code, src = item
    raw = load_rgb(src)
    s = max(raw.shape[:2]) / 1000.0  # scale blur to image resolution
    out = {}
    for name, fn in CONDITIONS.items():
        im = fn(raw, s)
        x, _ = preprocess(im, _A.size, clahe=_A.clahe)
        q_ok = None
        if _quality is not None:
            # quality.check() expects BGR (OpenCV order); `im` is RGB here.
            q_ok = bool(_quality.check(cv2.cvtColor(im, cv2.COLOR_RGB2BGR), _thr)["ok"])
        out[name] = (to_tensor_array(x), q_ok)
    return id_code, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--calibration", required=True)
    ap.add_argument("--splits", required=True)
    ap.add_argument("--img_dir", required=True, help="raw APTOS train_images/")
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality_thresholds", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, meta = load_checkpoint(a.ckpt, device)
    a.size, a.clahe = int(meta["img_size"]), bool(meta.get("clahe", True))
    cal = json.loads(Path(a.calibration).read_text())
    assert cal["fitted_on"] == "validation"
    te = pd.read_csv(a.splits).query("split == 'test'").reset_index(drop=True)
    if a.limit:
        te = te.head(a.limit)
    labels = dict(zip(te.id_code, te.diagnosis))
    items = [(i, next(p for ext in (".png", ".jpg", ".jpeg") if (p := Path(a.img_dir) / f"{i}{ext}").exists()))
             for i in te.id_code]

    logits = {c: [] for c in CONDITIONS}
    gate = {c: [] for c in CONDITIONS}
    ys = []
    with Pool(a.workers, initializer=_init, initargs=(a,)) as pool, torch.no_grad():
        for k, (id_code, res) in enumerate(pool.imap(_work, items, chunksize=4), 1):
            ys.append(labels[id_code])
            x = torch.from_numpy(np.stack([res[c][0] for c in CONDITIONS])).to(device)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
                lg = model(x).float().cpu().numpy()
            for j, c in enumerate(CONDITIONS):
                logits[c].append(lg[j])
                gate[c].append(res[c][1])
            if k % 100 == 0:
                print(f"  {k}/{len(items)}", flush=True)

    y = np.array(ys)
    rows = []
    for c in CONDITIONS:
        p = softmax(np.stack(logits[c]) / cal["temperature"])
        pred, conf = p.argmax(1), p.max(1)
        pr, yr = referable_prob(p), y >= REFERABLE_MIN_GRADE
        b = binary_stats(pr, yr, cal["referable_threshold"])
        covered = conf >= cal["abstain_threshold"]
        row = {"condition": c, "n": int(len(y)), "accuracy": float((pred == y).mean()), "qwk": qwk(y, pred),
               "referable_sensitivity": b["sensitivity"], "referable_specificity": b["specificity"],
               "referable_auc": safe_auc(yr, pr), "abstention_rate": float(1 - covered.mean()),
               "mean_confidence": float(conf.mean())}
        g = np.array(gate[c])
        if g[0] is not None:
            ok = g.astype(bool)
            row["quality_reject_rate"] = float(1 - ok.mean())
            row["accuracy_on_gate_passed"] = float((pred[ok] == y[ok]).mean()) if ok.any() else None
            row["n_gate_passed"] = int(ok.sum())
        rows.append(row)
        print(f"{c:13s} acc={row['accuracy']:.3f} qwk={row['qwk']:.3f} sens={row['referable_sensitivity']:.3f} "
              f"spec={row['referable_specificity']:.3f} abstain={row['abstention_rate']:.3f}"
              + (f" gate_reject={row['quality_reject_rate']:.3f}" if "quality_reject_rate" in row else ""),
              flush=True)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "degradation.csv", index=False)
    save_json({"split": "test", "note": "degradations applied to raw images before preprocessing; "
               "calibration fixed on validation; nothing fitted here",
               "quality_gate_used": rows[0].get("quality_reject_rate") is not None,
               "conditions": list(CONDITIONS), "rows": rows}, out / "degradation.json")


if __name__ == "__main__":
    main()
