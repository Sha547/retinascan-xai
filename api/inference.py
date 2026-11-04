"""Predictor interface and the mock predictor.

Routes only talk to Predictor, so Phase 2 replaces MockPredictor with the real
model without touching them.

MockPredictor output is fake: it is derived from a hash of the image and says
nothing about the eye. Every response carries model.mock = true.
"""
from __future__ import annotations

import base64
import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path

import cv2
import numpy as np

GRADE_LABELS = ["No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR"]
REFERABLE_MIN_GRADE = 2
MOCK_NOTE = "Mock heatmap for development. Not Grad-CAM and not derived from image content."
FIXTURE_CURVE = Path(__file__).resolve().parents[1] / "docs" / "fixtures" / "operating_curve.json"


class ModelUnavailable(Exception):
    """The model cannot serve requests. Returned to clients as a 503."""


def build_prediction(probs: list[float], abstain_threshold: float, referable_threshold: float) -> dict:
    """The contract's section 1 rules, shared by every predictor."""
    confidence = max(probs)
    grade = probs.index(confidence)
    referable_prob = round(sum(probs[REFERABLE_MIN_GRADE:]), 4)
    return {
        "grade": grade,
        "grade_label": GRADE_LABELS[grade],
        "probs": probs,
        "confidence": confidence,
        "abstained": confidence < abstain_threshold,
        "referable": referable_prob >= referable_threshold,
        "referable_prob": referable_prob,
    }


def recommendation_for(prediction: dict | None) -> str:
    """First matching row of the contract's recommendation table wins."""
    if prediction is None:
        return "Image not gradable. Please retake the photo (see reasons)."
    if prediction["abstained"]:
        return "Model is not confident. Routed to an ophthalmologist for review."
    if prediction["referable"] and prediction["grade"] >= 3:
        return "Urgent referral to an ophthalmologist is suggested."
    if prediction["referable"]:
        return "Referral to an ophthalmologist is suggested."
    return "No referable DR suggested by the model. Re-screen as per local protocol."


def priority_for(prediction: dict | None) -> float | None:
    """Heuristic triage score from the contract. Not clinically validated."""
    if prediction is None:
        return None
    bonus = 0.25 if prediction["abstained"] else 0
    return round(prediction["referable_prob"] + 0.5 * (1 - prediction["confidence"]) + bonus, 3)


class Predictor(ABC):
    """model is the contract's Case.model object."""

    model: dict

    @abstractmethod
    def predict(self, image: np.ndarray) -> dict:
        """RGB uint8 image -> {"prediction", "evidence", "model"}, or raise ModelUnavailable."""

    @abstractmethod
    def thumbnail(self, id_code: str) -> bytes | None:
        """JPEG bytes for a similar-case id, or None if it does not exist."""

    @abstractmethod
    def operating_curve(self) -> dict:
        """The operating_curve.json payload, or raise ModelUnavailable."""

    def health(self) -> dict:
        return {"version": self.model["version"], "mock": self.model["mock"], "loaded": True}


class MockPredictor(Predictor):
    """Deterministic per image. About one image in four abstains."""

    model = {
        "version": "mock-0",
        "mock": True,
        "temperature": 1.0,
        "abstain_threshold": 0.55,
        "referable_threshold": 0.35,
        "calibrated_on": "validation",
    }

    def predict(self, image: np.ndarray) -> dict:
        digest = hashlib.sha256(str(image.shape).encode() + image.tobytes()).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
        grade = digest[8] % 5
        abstain = digest[9] % 4 == 0

        probs = self._probs(rng, grade, abstain)
        prediction = build_prediction(
            probs, self.model["abstain_threshold"], self.model["referable_threshold"]
        )
        evidence = {
            "heatmap_png": self._heatmap(rng, image.shape[:2]),
            "heatmap_note": MOCK_NOTE,
            "similar": self._similar(rng, digest, grade),
        }
        return {"prediction": prediction, "evidence": evidence, "model": dict(self.model)}

    def thumbnail(self, id_code: str) -> bytes | None:
        if not id_code.startswith("mock"):
            return None
        image = np.full((256, 256, 3), 24, dtype=np.uint8)
        cv2.circle(image, (128, 128), 118, (60, 90, 150), -1)
        cv2.putText(image, "MOCK", (72, 138), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (235, 235, 235), 2)
        return cv2.imencode(".jpg", image)[1].tobytes()

    def operating_curve(self) -> dict:
        return json.loads(FIXTURE_CURVE.read_text())

    @staticmethod
    def _probs(rng: np.random.Generator, grade: int, abstain: bool) -> list[float]:
        # Keeping the top value at 0.30 or more and the others at 0.5 to 1.0 weights
        # guarantees the top value stays the largest, so grade is always the argmax.
        top = rng.uniform(0.30, 0.50) if abstain else rng.uniform(0.60, 0.92)
        weights = rng.uniform(0.5, 1.0, 4)
        rest = (1 - top) * weights / weights.sum()
        values = np.insert(rest, grade, top)
        probs = [round(float(value), 4) for value in values]
        probs[grade] = round(probs[grade] + 1 - sum(probs), 4)
        return probs

    @staticmethod
    def _heatmap(rng: np.random.Generator, shape: tuple[int, int]) -> str:
        size = 128
        cx, cy = rng.uniform(0.3, 0.7, 2) * size
        yy, xx = np.mgrid[0:size, 0:size]
        strength = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (size * 0.16) ** 2))
        small = np.zeros((size, size, 4), dtype=np.uint8)  # BGRA
        small[..., 1] = (200 * (1 - strength)).astype(np.uint8)
        small[..., 2] = 255
        small[..., 3] = (200 * strength).astype(np.uint8)
        height, width = shape
        full = cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR)
        encoded = base64.b64encode(cv2.imencode(".png", full)[1].tobytes()).decode()
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def _similar(rng: np.random.Generator, digest: bytes, grade: int) -> list[dict]:
        items = []
        for index in range(3):
            near = int(np.clip(grade + rng.integers(-1, 2), 0, 4))
            id_code = f"mock{digest[:4].hex()}{index}"
            items.append(
                {
                    "id_code": id_code,
                    "grade": near,
                    "grade_label": GRADE_LABELS[near],
                    "distance": round(0.18 + 0.05 * index, 2),
                    "image_url": f"/api/similar/{id_code}.jpg",
                }
            )
        return items
