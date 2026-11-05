import base64
import re
import sqlite3

import cv2
import numpy as np
import pytest

from api import main
from api.inference import MockPredictor, ModelUnavailable, priority_for, recommendation_for
from api.main import create_app
from api.tests.conftest import dark_bytes, encode, fake_fundus, fixture, fundus_bytes
from ml import quality

GRADED = [0.03, 0.09, 0.71, 0.12, 0.05]
ABSTAIN = [0.08, 0.38, 0.30, 0.14, 0.10]
HEALTHY = [0.90, 0.07, 0.02, 0.005, 0.005]
URGENT = [0.02, 0.03, 0.05, 0.80, 0.10]
MILD_BUT_REFERABLE = [0.05, 0.56, 0.20, 0.10, 0.09]


def assert_same_shape(actual, expected, path="$"):
    """Same keys at every level as the contract fixture. Values may differ."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert set(actual) == set(expected), path
        for key, value in expected.items():
            assert_same_shape(actual[key], value, f"{path}.{key}")
    elif isinstance(expected, list) and expected:
        assert isinstance(actual, list), path
        for item in actual:
            assert_same_shape(item, expected[0], f"{path}[]")


def queue(predictor, upload, *probs):
    predictor.queue.extend(probs)
    return [upload().json() for _ in probs]


# ------------------------------------------------------------------- health
def test_health_matches_fixture(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == fixture("health")


# ------------------------------------------------------------------ analyse
def test_analyse_graded_matches_contract(client, predictor, upload):
    predictor.queue.append(GRADED)
    response = upload(patient_id="PHC-2026-00042", eye="left")
    assert response.status_code == 201
    case = response.json()
    assert_same_shape(case, fixture("analyse_graded"))
    assert case["patient_id"] == "PHC-2026-00042"
    assert case["eye"] == "left"
    assert case["status"] == "pending"
    assert case["model"]["mock"] is True
    assert case["prediction"]["grade"] == 2
    assert case["prediction"]["grade_label"] == "Moderate NPDR"
    assert case["prediction"]["referable_prob"] == pytest.approx(0.88)
    # contract v1.2: referable_prob + 0.5*E[grade]/4 + 0.5*(1-confidence)
    expected = 0.88 + 0.5 * (0.09 + 2 * 0.71 + 3 * 0.12 + 4 * 0.05) / 4 + 0.5 * (1 - 0.71)
    assert case["priority"] == pytest.approx(round(expected, 3))
    assert case["recommendation"] == "Referral to an ophthalmologist is suggested."
    assert len(case["evidence"]["similar"]) == 3
    assert re.fullmatch(r"c_\d{8}_[0-9a-f]{6}", case["case_id"])
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", case["created_at"])
    assert case["image_url"] == f"/api/cases/{case['case_id']}/image"


def test_analyse_abstained_matches_contract(predictor, upload):
    predictor.queue.append(ABSTAIN)
    case = upload().json()
    assert_same_shape(case, fixture("analyse_abstained"))
    assert case["prediction"]["abstained"] is True
    assert case["status"] == "pending"
    assert case["recommendation"] == "Model is not confident. Routed to an ophthalmologist for review."


def test_quality_failure_returns_retake_and_no_grade(predictor, upload):
    response = upload(dark_bytes())
    assert response.status_code == 201
    case = response.json()
    assert_same_shape(case, fixture("analyse_retake"))
    assert case["status"] == "retake"
    assert case["quality"]["ok"] is False
    assert "too_dark" in {reason["code"] for reason in case["quality"]["reasons"]}
    assert case["prediction"] is None
    assert case["evidence"] is None
    assert case["priority"] is None
    assert case["recommendation"] == "Image not gradable. Please retake the photo (see reasons)."
    assert predictor.calls == 0


def test_generated_patient_id_and_default_eye(upload):
    first, second = upload().json(), upload(patient_id="   ").json()
    assert re.fullmatch(r"PHC-\d{4}-\d{5}", first["patient_id"])
    assert re.fullmatch(r"PHC-\d{4}-\d{5}", second["patient_id"])
    assert first["patient_id"] != second["patient_id"]
    assert first["eye"] == "unknown"


def test_jpeg_upload_is_served_back_as_jpeg(client):
    data = encode(fake_fundus(), ".jpg")
    case = client.post("/api/analyse", files={"image": ("e.jpg", data, "image/jpeg")}).json()
    response = client.get(case["image_url"])
    assert response.content == data
    assert response.headers["content-type"] == "image/jpeg"


def test_case_uses_quality_gate_from_ml_package(upload):
    case = upload().json()
    assert set(case["quality"]["metrics"]) == set(quality.METRIC_KEYS)


# ------------------------------------------------------------- upload errors
def assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]


def test_rejects_text_upload_with_fixture_body(upload):
    response = upload(b"not an image at all")
    assert response.status_code == 415
    assert response.json() == fixture("error_415")


def test_type_comes_from_content_not_header(client):
    gif = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    response = client.post("/api/analyse", files={"image": ("eye.png", gif, "image/png")})
    assert_error(response, 415, "unsupported_media_type")


def test_truncated_image_header_rejected(upload):
    assert_error(upload(fundus_bytes()[:20]), 415, "unsupported_media_type")


def test_empty_upload_rejected(upload):
    assert_error(upload(b""), 415, "unsupported_media_type")


def test_oversized_upload_rejected_by_content_length(upload):
    assert_error(upload(b"\x00" * (main.MAX_REQUEST_BYTES + 1)), 413, "payload_too_large")


def test_oversized_upload_rejected_when_read(upload, monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 100)
    assert_error(upload(), 413, "payload_too_large")


def test_huge_dimensions_rejected_before_decoding(upload, monkeypatch):
    monkeypatch.setattr(main, "MAX_IMAGE_PIXELS", 1000)
    assert_error(upload(), 400, "bad_request")


def test_missing_image_is_422(client):
    assert_error(client.post("/api/analyse", data={"eye": "left"}), 422, "validation_error")


def test_bad_eye_is_422(upload):
    assert_error(upload(eye="middle"), 422, "validation_error")


def test_long_patient_id_is_422(upload):
    assert_error(upload(patient_id="x" * 65), 422, "validation_error")


def test_rejected_uploads_store_nothing(client, upload, tmp_path):
    upload(b"nope")
    assert client.get("/api/cases?status=all").json()["total"] == 0
    assert list((tmp_path / "uploads").iterdir()) == []


# -------------------------------------------------------------- triage queue
def test_pending_queue_sorted_by_priority(client, predictor, upload):
    healthy, urgent, abstained, graded = queue(predictor, upload, HEALTHY, URGENT, ABSTAIN, GRADED)
    upload(dark_bytes())
    body = client.get("/api/cases").json()
    # v1.2 adds expected severity: a confident grade-3 case outranks an uncertain one
    assert [case["case_id"] for case in body["cases"]] == [
        urgent["case_id"],
        abstained["case_id"],
        graded["case_id"],
        healthy["case_id"],
    ]
    priorities = [case["priority"] for case in body["cases"]]
    assert priorities == sorted(priorities, reverse=True)
    assert body["total"] == 4
    assert_same_shape(body, fixture("cases_pending"))


def test_equal_priority_oldest_first(client, predictor, upload):
    first, second, third = queue(predictor, upload, GRADED, GRADED, GRADED)
    ids = [case["case_id"] for case in client.get("/api/cases").json()["cases"]]
    assert ids == [first["case_id"], second["case_id"], third["case_id"]]


def test_equal_priority_uses_created_at_before_insert_order(client, predictor, upload, tmp_path):
    first, second = queue(predictor, upload, GRADED, GRADED)
    with sqlite3.connect(tmp_path / "test.db") as connection:
        connection.execute(
            "UPDATE cases SET created_at = '2020-01-01T00:00:00Z' WHERE case_id = ?",
            (second["case_id"],),
        )
    ids = [case["case_id"] for case in client.get("/api/cases").json()["cases"]]
    assert ids == [second["case_id"], first["case_id"]]


def test_retake_not_in_doctor_queue_and_listed_separately(client, predictor, upload):
    (graded,) = queue(predictor, upload, GRADED)
    retake = upload(dark_bytes()).json()
    pending = client.get("/api/cases").json()["cases"]
    assert [case["case_id"] for case in pending] == [graded["case_id"]]
    listed = client.get("/api/cases?status=retake").json()
    assert [case["case_id"] for case in listed["cases"]] == [retake["case_id"]]
    summary = listed["cases"][0]
    assert summary["quality_ok"] is False
    assert summary["priority"] is None
    assert summary["grade"] is None
    assert summary["grade_label"] is None
    assert summary["confidence"] is None
    assert summary["abstained"] is None
    assert summary["referable"] is None


def test_reviewed_sorted_by_latest_decision(client, predictor, upload):
    first, second = queue(predictor, upload, GRADED, HEALTHY)
    decide(client, first, "accept")
    decide(client, second, "accept")
    decide(client, first, "override", final_grade=3)
    ids = [case["case_id"] for case in client.get("/api/cases?status=reviewed").json()["cases"]]
    assert ids == [first["case_id"], second["case_id"]]


def test_all_lists_newest_first_with_total_ignoring_limit(client, predictor, upload):
    cases = queue(predictor, upload, GRADED, HEALTHY, URGENT)
    body = client.get("/api/cases?status=all&limit=2").json()
    assert [case["case_id"] for case in body["cases"]] == [cases[2]["case_id"], cases[1]["case_id"]]
    assert body["total"] == 3
    assert_same_shape(body, fixture("cases_all"))


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "limit=x", "status=done"])
def test_bad_list_query_is_422(client, query):
    assert_error(client.get(f"/api/cases?{query}"), 422, "validation_error")


def test_limit_200_is_allowed(client):
    assert client.get("/api/cases?limit=200").status_code == 200


# ----------------------------------------------------------------- decisions
def decide(client, case, action, reviewer="Dr. Rao", **fields):
    response = client.post(
        f"/api/cases/{case['case_id']}/decision", json={"action": action, "reviewer": reviewer, **fields}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_accept_uses_predicted_grade_and_is_logged(client, predictor, upload):
    (case,) = queue(predictor, upload, GRADED)
    updated = decide(client, case, "accept", final_grade=4)
    assert updated["status"] == "accepted"
    assert updated["final_grade"] == 2
    assert_same_shape(updated, fixture("case_reviewed"))
    (decision,) = updated["decisions"]
    assert decision["action"] == "accept"
    assert decision["final_grade"] == 2
    assert decision["note"] == ""
    assert decision["case_id"] == case["case_id"]


def test_accept_ignores_invalid_final_grade(client, predictor, upload):
    (case,) = queue(predictor, upload, GRADED)
    assert decide(client, case, "accept", final_grade="nonsense")["final_grade"] == 2


def test_override_sets_grade_and_is_logged(client, predictor, upload):
    (case,) = queue(predictor, upload, GRADED)
    updated = decide(client, case, "override", final_grade=3, note="Venous beading seen.")
    assert updated["status"] == "overridden"
    assert updated["final_grade"] == 3
    assert updated["prediction"]["grade"] == 2
    assert updated["decisions"][0]["note"] == "Venous beading seen."
    assert updated["decisions"][0]["reviewer"] == "Dr. Rao"


def test_later_decision_supersedes_and_all_are_kept(client, predictor, upload):
    (case,) = queue(predictor, upload, GRADED)
    decide(client, case, "override", final_grade=4)
    decide(client, case, "override", final_grade=1, reviewer="Dr. Iyer")
    final = decide(client, case, "accept")
    assert final["status"] == "accepted"
    assert final["final_grade"] == 2
    assert [item["final_grade"] for item in final["decisions"]] == [4, 1, 2]
    ids = [item["decision_id"] for item in final["decisions"]]
    assert ids == sorted(ids)
    assert client.get(f"/api/cases/{case['case_id']}").json()["decisions"] == final["decisions"]


def test_reviewed_case_leaves_pending_queue(client, predictor, upload):
    (case,) = queue(predictor, upload, GRADED)
    decide(client, case, "accept")
    assert client.get("/api/cases").json()["total"] == 0


def test_decision_rows_cannot_be_deleted_or_changed(client, predictor, upload, tmp_path):
    (case,) = queue(predictor, upload, GRADED)
    decide(client, case, "override", final_grade=3)
    with sqlite3.connect(tmp_path / "test.db") as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM decisions")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE decisions SET final_grade = 0")
        assert connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1


def test_decision_on_retake_is_409(client, upload):
    case = upload(dark_bytes()).json()
    response = client.post(
        f"/api/cases/{case['case_id']}/decision", json={"action": "accept", "reviewer": "Dr. Rao"}
    )
    assert_error(response, 409, "bad_request")
    assert client.get(f"/api/cases/{case['case_id']}").json()["decisions"] == []


def test_decision_on_unknown_case_is_404(client):
    response = client.post("/api/cases/nope/decision", json={"action": "accept", "reviewer": "Dr. Rao"})
    assert_error(response, 404, "not_found")


@pytest.mark.parametrize(
    "body",
    [
        {"action": "accept"},
        {"action": "accept", "reviewer": "   "},
        {"action": "override", "reviewer": "Dr. Rao"},
        {"action": "override", "reviewer": "Dr. Rao", "final_grade": 5},
        {"action": "override", "reviewer": "Dr. Rao", "final_grade": -1},
        {"action": "override", "reviewer": "Dr. Rao", "final_grade": "3"},
        {"action": "override", "reviewer": "Dr. Rao", "final_grade": True},
        {"action": "delete", "reviewer": "Dr. Rao"},
    ],
)
def test_bad_decision_is_422_and_not_logged(client, predictor, upload, body):
    (case,) = queue(predictor, upload, GRADED)
    response = client.post(f"/api/cases/{case['case_id']}/decision", json=body)
    assert_error(response, 422, "validation_error")
    stored = client.get(f"/api/cases/{case['case_id']}").json()
    assert stored["decisions"] == []
    assert stored["status"] == "pending"


# -------------------------------------------------------------- case reads
def test_get_case_returns_what_analyse_returned(client, upload):
    case = upload().json()
    assert client.get(f"/api/cases/{case['case_id']}").json() == case


def test_get_unknown_case_is_404(client):
    assert_error(client.get("/api/cases/nope"), 404, "not_found")


def test_image_returns_original_bytes(client, upload):
    data = fundus_bytes(7)
    case = upload(data).json()
    response = client.get(case["image_url"])
    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "image/png"


def test_image_for_unknown_case_is_404(client):
    assert_error(client.get("/api/cases/nope/image"), 404, "not_found")


def test_cases_survive_restart(make_client, predictor, upload):
    case = upload().json()
    assert make_client(predictor).get(f"/api/cases/{case['case_id']}").json() == case


# ------------------------------------------------------- similar and curve
def test_similar_thumbnail_from_case_is_served(client, upload):
    case = upload().json()
    response = client.get(case["evidence"]["similar"][0]["image_url"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR) is not None


@pytest.mark.parametrize("id_code", ["unknown", "mock..secret", "mock%2F..%2Fsecret"])
def test_unknown_or_unsafe_similar_id_is_404(client, id_code):
    assert_error(client.get(f"/api/similar/{id_code}.jpg"), 404, "not_found")


def test_operating_curve_returns_fixture_under_mock(client):
    response = client.get("/api/operating-curve")
    assert response.status_code == 200
    assert response.json() == fixture("operating_curve")
    assert response.json()["mock"] is True


# ------------------------------------------------------------ server errors
class BrokenPredictor(MockPredictor):
    def predict(self, image):
        raise ModelUnavailable("Model weights are not loaded.")

    def operating_curve(self):
        raise ModelUnavailable()


def test_model_unavailable_is_503_and_stores_nothing(make_client, tmp_path):
    client = make_client(BrokenPredictor())
    response = client.post("/api/analyse", files={"image": ("e.png", fundus_bytes(), "image/png")})
    assert_error(response, 503, "model_unavailable")
    assert_error(client.get("/api/operating-curve"), 503, "model_unavailable")
    assert client.get("/api/cases?status=all").json()["total"] == 0
    assert list((tmp_path / "uploads").iterdir()) == []


class CrashingPredictor(MockPredictor):
    def predict(self, image):
        raise RuntimeError("secret internal detail")


def test_unexpected_error_is_500_without_details(make_client):
    client = make_client(CrashingPredictor(), raise_server_exceptions=False)
    response = client.post("/api/analyse", files={"image": ("e.png", fundus_bytes(), "image/png")})
    assert_error(response, 500, "internal")
    assert "secret" not in response.text


def test_failed_save_removes_the_image(make_client, tmp_path, monkeypatch):
    client = make_client(raise_server_exceptions=False)
    monkeypatch.setattr("api.store.Store.add_case", lambda *_: (_ for _ in ()).throw(RuntimeError()))
    response = client.post("/api/analyse", files={"image": ("e.png", fundus_bytes(), "image/png")})
    assert response.status_code == 500
    assert list((tmp_path / "uploads").iterdir()) == []


def test_unknown_route_uses_error_shape(client):
    assert_error(client.get("/api/nope"), 404, "not_found")


def test_wrong_method_uses_error_shape(client):
    assert_error(client.delete("/api/health"), 405, "bad_request")


def test_cors_allows_the_lan_frontend(client):
    response = client.get("/api/health", headers={"Origin": "http://192.168.2.50:5173"})
    assert response.headers["access-control-allow-origin"] == "*"


# ------------------------------------------------------------ domain rules
@pytest.mark.parametrize(
    "probs, text",
    [
        (ABSTAIN, "Model is not confident. Routed to an ophthalmologist for review."),
        (URGENT, "Urgent referral to an ophthalmologist is suggested."),
        (GRADED, "Referral to an ophthalmologist is suggested."),
        (MILD_BUT_REFERABLE, "Model is not confident. Routed to an ophthalmologist for review."),
        (HEALTHY, "No referable DR suggested by the model. Re-screen as per local protocol."),
    ],
)
def test_recommendation_rows(predictor, upload, probs, text):
    predictor.queue.append(probs)
    assert upload().json()["recommendation"] == text


def test_recommendation_and_priority_for_missing_prediction():
    assert recommendation_for(None).startswith("Image not gradable")
    assert priority_for(None) is None


def test_grade_referral_conflict_abstains(predictor, upload):
    """Contract v1.2: a grade that disagrees with the referable call is never shown as a decision."""
    predictor.queue.append(MILD_BUT_REFERABLE)  # confident grade 1, but P(grade>=2) above threshold
    case = upload().json()
    prediction = case["prediction"]
    assert prediction["grade"] == 1 and prediction["referable"] is True
    assert prediction["abstained"] is True
    assert prediction["abstain_reason"] == "grade_referral_conflict"
    assert case["recommendation"].startswith("Model is not confident")


def test_moderate_but_not_referable_abstains():
    """The conflict found by the independent review on real test predictions: grade 2 with
    confidence above the abstain threshold, but P(grade>=2) below the referable threshold."""
    from common import decide

    d = decide(np.array([0.02, 0.40, 0.58, 0.0, 0.0]), 0.55, 0.60)
    assert int(d["grade"]) == 2 and not bool(d["referable"])
    assert bool(d["conflict"]) and bool(d["abstained"])


def test_abstained_priority_gets_bonus(predictor, upload):
    predictor.queue.append(ABSTAIN)
    case = upload().json()
    expected = 0.54 + 0.5 * (0.38 + 2 * 0.30 + 3 * 0.14 + 4 * 0.10) / 4 + 0.5 * (1 - 0.38) + 0.25
    assert case["priority"] == pytest.approx(round(expected, 3))


# ----------------------------------------------------------- mock predictor
def rgb_images(count):
    rng = np.random.default_rng(1)
    return [rng.integers(0, 255, (32, 48, 3), dtype=np.uint8) for _ in range(count)]


def test_mock_is_deterministic_per_image():
    image = rgb_images(1)[0]
    assert MockPredictor().predict(image) == MockPredictor().predict(image.copy())


def test_mock_produces_every_grade_and_both_outcomes():
    predictions = [MockPredictor().predict(image)["prediction"] for image in rgb_images(200)]
    assert {prediction["grade"] for prediction in predictions} == {0, 1, 2, 3, 4}
    assert {prediction["abstained"] for prediction in predictions} == {True, False}


def test_mock_probs_are_valid_and_grade_is_argmax():
    for image in rgb_images(200):
        result = MockPredictor().predict(image)
        prediction = result["prediction"]
        assert result["model"]["mock"] is True
        assert sum(prediction["probs"]) == pytest.approx(1, abs=1e-9)
        assert all(prob > 0 for prob in prediction["probs"])
        assert prediction["probs"].index(max(prediction["probs"])) == prediction["grade"]
        assert prediction["confidence"] == max(prediction["probs"])


def decoded_heatmap(image):
    uri = MockPredictor().predict(image)["evidence"]["heatmap_png"]
    prefix = "data:image/png;base64,"
    assert uri.startswith(prefix)
    png = base64.b64decode(uri[len(prefix):])
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)


def test_mock_heatmap_keeps_small_upload_size_and_has_alpha():
    assert decoded_heatmap(rgb_images(1)[0]).shape == (32, 48, 4)


def test_mock_heatmap_longest_side_is_capped_and_keeps_aspect():
    image = np.zeros((2000, 3000, 3), dtype=np.uint8)
    assert decoded_heatmap(image).shape == (683, 1024, 4)


def test_mock_result_has_the_ml_infer_keys():
    result = MockPredictor().predict(rgb_images(1)[0])
    assert {"prediction", "recommendation", "priority", "evidence", "model"} <= set(result)


def test_mock_evidence_makes_no_gradcam_claim():
    note = MockPredictor().predict(rgb_images(1)[0])["evidence"]["heatmap_note"]
    assert note.startswith("Mock heatmap")


# ------------------------------------------------------------- thresholds
def test_app_refuses_non_derived_artifact_thresholds(tmp_path, monkeypatch):
    (tmp_path / "quality_thresholds.json").write_text('{"derived_from_data": false}')
    monkeypatch.setattr(main, "ARTIFACTS", tmp_path)
    with pytest.raises(ValueError, match="not derived from data"):
        create_app(db_path=tmp_path / "t.db", uploads_dir=tmp_path / "u")


def test_app_falls_back_to_placeholder_with_warning(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(main, "ARTIFACTS", tmp_path)
    create_app(db_path=tmp_path / "t.db", uploads_dir=tmp_path / "u")
    assert "PLACEHOLDER" in caplog.text
