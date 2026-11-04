import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.inference import MockPredictor, build_prediction
from api.main import create_app
from ml import quality

FIXTURES = Path(__file__).resolve().parents[2] / "docs" / "fixtures"


def fake_fundus(seed=0, size=600):
    """Orange-red disc on black with vessels. Each seed gives different bytes."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size]
    centre = size // 2
    radius = int(size * 0.46)
    falloff = 1 - 0.35 * np.hypot(xx - centre, yy - centre) / radius
    retina = np.stack([30 * falloff, 75 * falloff, 170 * falloff], axis=2)
    retina += rng.normal(0, 5, retina.shape)
    image = np.clip(retina, 0, 255).astype(np.uint8)
    for _ in range(40):
        start, end = rng.integers(centre - radius, centre + radius, (2, 2))
        cv2.line(image, tuple(map(int, start)), tuple(map(int, end)), (15, 25, 95), 2)
    disc = np.zeros((size, size), dtype=np.uint8)
    cv2.circle(disc, (centre, centre), radius, 255, -1)
    image[disc == 0] = 0
    return image


def encode(image, extension=".png"):
    return cv2.imencode(extension, image)[1].tobytes()


def fundus_bytes(seed=0):
    return encode(fake_fundus(seed))


def dark_bytes():
    return encode((fake_fundus() * 0.2).astype(np.uint8))


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


class ScriptedPredictor(MockPredictor):
    """Returns queued probs so tests control grade, abstention and referral."""

    def __init__(self):
        self.queue = []
        self.calls = 0

    def predict(self, image):
        self.calls += 1
        result = super().predict(image)
        if self.queue:
            result["prediction"] = build_prediction(
                self.queue.pop(0), self.model["abstain_threshold"], self.model["referable_threshold"]
            )
        return result


@pytest.fixture
def thresholds():
    base = quality.compute_metrics(fake_fundus())
    return {
        "sharpness_min": base["sharpness"] * 0.4,
        "brightness_min": base["brightness"] * 0.6,
        "brightness_max": base["brightness"] * 1.6,
        "contrast_min": base["contrast"] * 0.5,
        "coverage_min": base["field_coverage"] * 0.6,
        "glare_max": base["glare_fraction"] + 0.02,
    }


@pytest.fixture
def predictor():
    return ScriptedPredictor()


@pytest.fixture
def make_client(tmp_path, thresholds):
    def build(predictor=None, **client_options):
        app = create_app(
            predictor=predictor or MockPredictor(),
            db_path=tmp_path / "test.db",
            uploads_dir=tmp_path / "uploads",
            thresholds=thresholds,
        )
        return TestClient(app, **client_options)

    return build


@pytest.fixture
def client(make_client, predictor):
    return make_client(predictor)


@pytest.fixture
def upload(client):
    counter = iter(range(1000, 100000))

    def send(data=None, **fields):
        data = fundus_bytes(next(counter)) if data is None else data
        return client.post("/api/analyse", files={"image": ("eye.png", data, "image/png")}, data=fields)

    return send
