"""Tests for the real model behind the API. Skipped if the trained artifacts are absent.

Also guards colour order: the quality gate must get BGR and the model RGB.
"""
import base64
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytest

from api.inference import MockPredictor, RealPredictor
from api.main import ARTIFACTS
from api.tests.conftest import encode, fake_fundus
from ml import quality

NEEDED = ["model.pt", "calibration.json", "train_index.npz", "operating_curve.json", "splits.csv"]
have_artifacts = all((ARTIFACTS / n).is_file() for n in NEEDED) and (
    (ARTIFACTS / "thumbs").is_dir() or (ARTIFACTS / "thumbs.zip").is_file())
needs_model = pytest.mark.skipif(not have_artifacts, reason="trained artifacts not in artifacts/")


@pytest.fixture(scope="module")
def real():
    return RealPredictor(ARTIFACTS)


def decode_png(uri):
    raw = base64.b64decode(uri.split(",", 1)[1])
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)


@needs_model
def test_real_prediction_follows_contract(real):
    from infer import priority, recommendation

    rgb = cv2.cvtColor(fake_fundus(3, size=900), cv2.COLOR_BGR2RGB)
    out = real.predict(rgb)
    p, cal = out["prediction"], json.loads((ARTIFACTS / "calibration.json").read_text())
    assert set(out) == {"prediction", "recommendation", "priority", "evidence", "model"}
    assert abs(sum(p["probs"]) - 1) < 1e-3 and len(p["probs"]) == 5
    assert p["grade"] == int(np.argmax(p["probs"])) and p["confidence"] == max(p["probs"])
    assert p["abstained"] == (p["confidence"] < cal["abstain_threshold"])
    assert p["referable"] == (p["referable_prob"] >= cal["referable_threshold"])
    assert out["recommendation"] == recommendation(p) and out["priority"] == priority(p)
    assert out["model"]["mock"] is False and out["model"]["calibrated_on"] == "validation"
    assert out["model"]["temperature"] == cal["temperature"]


@needs_model
def test_heatmap_aligned_and_capped(real):
    for h, w in ((900, 1350), (2000, 3000)):
        img = cv2.resize(fake_fundus(4, size=600), (w, h))
        hm = decode_png(real.predict(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))["evidence"]["heatmap_png"])
        assert hm.shape[2] == 4, "heatmap must have alpha"
        assert max(hm.shape[:2]) <= 1024
        assert abs(hm.shape[1] / hm.shape[0] - w / h) < 0.01, "heatmap must keep the upload's aspect ratio"


@needs_model
def test_similar_cases_are_training_images_and_served(real, make_client):
    train = set(pd.read_csv(ARTIFACTS / "splits.csv").query("split == 'train'").id_code)
    sim = real.predict(cv2.cvtColor(fake_fundus(5), cv2.COLOR_BGR2RGB))["evidence"]["similar"]
    assert len(sim) == 3 and all(s["id_code"] in train for s in sim)
    client = make_client(real)
    r = client.get(sim[0]["image_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert client.get("/api/similar/../model.jpg").status_code == 404


@needs_model
def test_health_and_curve_report_real_model(real, make_client):
    client = make_client(real)
    h = client.get("/api/health").json()
    assert h["model"]["mock"] is False and h["model"]["loaded"] is True
    curve = client.get("/api/operating-curve").json()
    assert curve == json.loads((ARTIFACTS / "operating_curve.json").read_text())
    assert curve["source"] == "validation" and curve["mock"] is False


def test_colour_order_quality_gets_bgr_model_gets_rgb(make_client, monkeypatch):
    """Upload an image whose red and blue channels differ strongly, then check
    which order each stage received. Swapping them changes measured brightness by
    about 20% on real fundus photos."""
    seen = {}
    real_check = quality.check

    def spy_check(image, thresholds):
        seen["quality"] = image.copy()
        return real_check(image, thresholds)

    class SpyPredictor(MockPredictor):
        def predict(self, image):
            seen["model"] = image.copy()
            return super().predict(image)

    monkeypatch.setattr(quality, "check", spy_check)
    bgr = fake_fundus(7)  # BGR, red-dominant like a real fundus: channel 2 (R) > channel 0 (B)
    client = make_client(SpyPredictor())
    r = client.post("/api/analyse", files={"image": ("eye.png", encode(bgr), "image/png")})
    assert r.status_code == 201 and "model" in seen, r.text
    q, m = seen["quality"], seen["model"]
    assert q[..., 2].mean() > q[..., 0].mean(), "quality gate must receive BGR (red in channel 2)"
    assert m[..., 0].mean() > m[..., 2].mean(), "model must receive RGB (red in channel 0)"
    assert np.array_equal(q[..., ::-1], m)


@needs_model
def test_similar_cases_are_not_duplicate_photos(real):
    """APTOS has duplicate photos; the same image must not be shown twice."""
    from api.tests.conftest import fake_fundus as ff
    idx = {str(i): n for n, i in enumerate(real._model.index_ids)}
    for seed in (5, 6, 7):
        sim = real.predict(cv2.cvtColor(ff(seed), cv2.COLOR_BGR2RGB))["evidence"]["similar"]
        e = real._model.index_emb[[idx[s["id_code"]] for s in sim]]
        pair = e @ e.T
        assert (pair[~np.eye(3, dtype=bool)] < 0.99).all()
