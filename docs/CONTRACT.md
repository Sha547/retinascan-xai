# RetinaScan XAI: API and artifact contract

This file is the single source of truth shared by the three lanes:

- **Lane A (ML)** produces the artifacts in section 3.
- **Lane B (backend, `api/`)** serves the API in section 2 and reads those artifacts.
- **Lane C (frontend, `web/`)** consumes the API.

Only lane A edits this file. Other lanes write proposed changes under
"Contract change requests" in `PROGRESS.md`.

Example payloads for every response live in `docs/fixtures/`. They are
**fake** (`model.mock = true`) and exist so the frontend can be built without a
running backend.

Contract version: **1.1** (1.1: heatmap size cap; `ml/infer.py` serving API. Non-breaking.)

---

## 1. Domain definitions

| Grade | `grade_label`          | Referable? |
| ----- | ---------------------- | ---------- |
| 0     | `No DR`                | no         |
| 1     | `Mild NPDR`            | no         |
| 2     | `Moderate NPDR`        | yes        |
| 3     | `Severe NPDR`          | yes        |
| 4     | `Proliferative DR`     | yes        |

- **Referable DR** = grade ≥ 2 (moderate or worse). This is the standard screening definition.
- `probs` are **temperature-calibrated** softmax probabilities over grades 0 to 4. They sum to 1.
- `confidence` = `max(probs)`.
- `referable_prob` = `probs[2] + probs[3] + probs[4]`.
- `referable` = `referable_prob >= model.referable_threshold`. This can disagree
  with `grade` (for example, grade 1 is most likely but referable_prob is high). That is
  intended: the referable decision uses a screening operating point.
- `abstained` = `confidence < model.abstain_threshold`. When abstained, the grade is
  "tentative" and the case must be reviewed by a doctor.
- Temperature and both thresholds are fitted on the **validation split only**.
  The test split is never used to choose them.

### Recommendation text (backend generates it, frontend shows it verbatim)

| Condition                         | `recommendation`                                                                 |
| --------------------------------- | -------------------------------------------------------------------------------- |
| quality failed                    | `Image not gradable. Please retake the photo (see reasons).`                     |
| abstained                         | `Model is not confident. Routed to an ophthalmologist for review.`               |
| referable and grade ≥ 3           | `Urgent referral to an ophthalmologist is suggested.`                            |
| referable otherwise               | `Referral to an ophthalmologist is suggested.`                                   |
| not referable                     | `No referable DR suggested by the model. Re-screen as per local protocol.`       |

The order is the order of precedence (first matching row wins).

### Quality reason codes

`too_dark`, `too_bright`, `blurry`, `low_contrast`, `poor_field` (retina not fully
in frame, or not a fundus image), `glare`. Each reason has a human-readable,
actionable `message`, e.g. `"Image too dark: increase illumination and retake."`

### Triage priority (heuristic, not clinically validated)

```
priority = referable_prob + 0.5 * (1 - confidence) + (0.25 if abstained else 0)
```

Rounded to 3 decimals. Quality-failed cases have `priority = null` and status
`retake`; they are not in the doctor queue.

---

## 2. HTTP API (lane B serves, lane C consumes)

Base path `/api`. JSON everywhere except uploads and images. Timestamps are ISO
8601 UTC (`2026-11-05T10:15:00Z`).

### Errors

Any 4xx/5xx returns:

```json
{ "error": { "code": "unsupported_media_type", "message": "Upload a JPEG or PNG image." } }
```

Codes: `bad_request` (400), `not_found` (404), `payload_too_large` (413, limit 15 MB),
`unsupported_media_type` (415), `validation_error` (422), `model_unavailable` (503),
`internal` (500).

### `GET /api/health`

```json
{ "status": "ok", "contract_version": 1, "model": { "version": "mock-0", "mock": true, "loaded": true } }
```

### `POST /api/analyse`

`multipart/form-data` fields:

- `image` (required): JPEG or PNG.
- `patient_id` (optional): string. If missing, the backend generates `PHC-<year>-<5 digits>`.
- `eye` (optional): `left` | `right` | `unknown` (default `unknown`).

Returns **201** with a `Case` object (below). A quality failure is **not** an
error: it returns 201 with `status: "retake"`, `quality.ok: false`,
`prediction: null`, `evidence: null`.

### `GET /api/cases?status=pending|reviewed|retake|all&limit=50`

- `pending`: status `pending`, sorted by `priority` desc, then `created_at` asc.
- `reviewed`: status `accepted` or `overridden`, sorted by latest decision time desc.
- `retake`: status `retake`, sorted by `created_at` desc.
- `all`: everything, sorted by `created_at` desc.
- Default `status=pending`, default `limit=50`, max 200.

```json
{ "cases": [ CaseSummary, ... ], "total": 12 }
```

### `GET /api/cases/{case_id}`

Returns the full `Case` object, including `decisions`.

### `POST /api/cases/{case_id}/decision`

```json
{ "action": "accept", "reviewer": "Dr. Rao", "note": "" }
{ "action": "override", "final_grade": 3, "reviewer": "Dr. Rao", "note": "Venous beading seen." }
```

- `reviewer` is required and must be non-empty.
- `final_grade` (0 to 4) is required for `override` and ignored for `accept`.
- Allowed on cases with status `pending`, `accepted` or `overridden` (a later
  decision supersedes; every decision is kept in the log). Not allowed on `retake` (409, code `bad_request`).
- `accept` sets status `accepted` and `final_grade = prediction.grade`.
- `override` sets status `overridden` and `final_grade = final_grade`.
- Returns the updated full `Case`.

### `GET /api/cases/{case_id}/image`

Returns the original uploaded image bytes.

### `GET /api/similar/{id_code}.jpg`

Returns the thumbnail of a training-split image used as a similar case.

### `GET /api/operating-curve`

Returns `artifacts/operating_curve.json` (section 3) as is. Used by the
operating-point slider.

---

## 3. Objects

### `Case`

```json
{
  "case_id": "c_20261105_7f3a9b",
  "patient_id": "PHC-2026-00042",
  "eye": "left",
  "created_at": "2026-11-05T10:15:00Z",
  "status": "pending",
  "image_url": "/api/cases/c_20261105_7f3a9b/image",
  "quality": {
    "ok": true,
    "metrics": { "sharpness": 182.4, "brightness": 96.1, "contrast": 41.7, "field_coverage": 0.71, "glare_fraction": 0.002 },
    "reasons": []
  },
  "prediction": {
    "grade": 2,
    "grade_label": "Moderate NPDR",
    "probs": [0.03, 0.09, 0.71, 0.12, 0.05],
    "confidence": 0.71,
    "abstained": false,
    "referable": true,
    "referable_prob": 0.88
  },
  "recommendation": "Referral to an ophthalmologist is suggested.",
  "evidence": {
    "heatmap_png": "data:image/png;base64,....",
    "heatmap_note": "Grad-CAM: image regions that most influenced the predicted grade. Coarse; not lesion detection.",
    "similar": [
      { "id_code": "a1b2c3d4e5f6", "grade": 2, "grade_label": "Moderate NPDR", "distance": 0.21, "image_url": "/api/similar/a1b2c3d4e5f6.jpg" }
    ]
  },
  "priority": 0.995,
  "final_grade": null,
  "decisions": [],
  "model": {
    "version": "effnet-b0-exp1",
    "mock": false,
    "temperature": 1.37,
    "abstain_threshold": 0.55,
    "referable_threshold": 0.31,
    "calibrated_on": "validation"
  },
  "disclaimer": "Research prototype, not clinically validated. Final decision must be made by a qualified ophthalmologist."
}
```

- `status`: `pending` | `retake` | `accepted` | `overridden`.
- `heatmap_png` is a PNG data URI with alpha, ready to overlay. It has the **same
  aspect ratio and alignment as the uploaded image**, with its longest side capped
  at 1024 px; scale it to the displayed image size. (Contract v1.1)
- `similar` has exactly 3 items when a prediction exists. All are training-split images.
- `decisions`: list of `Decision`, oldest first.

### `CaseSummary`

```json
{
  "case_id": "c_20261105_7f3a9b",
  "patient_id": "PHC-2026-00042",
  "eye": "left",
  "created_at": "2026-11-05T10:15:00Z",
  "status": "pending",
  "image_url": "/api/cases/c_20261105_7f3a9b/image",
  "quality_ok": true,
  "grade": 2,
  "grade_label": "Moderate NPDR",
  "confidence": 0.71,
  "abstained": false,
  "referable": true,
  "priority": 0.995,
  "final_grade": null,
  "mock": false
}
```

Fields from `prediction` are `null` when the quality check failed.

### `Decision`

```json
{ "decision_id": 7, "case_id": "c_20261105_7f3a9b", "action": "override", "final_grade": 3,
  "reviewer": "Dr. Rao", "note": "Venous beading seen.", "created_at": "2026-11-05T11:02:00Z" }
```

---

## 4. Artifacts (lane A produces, lane B reads)

Produced by the Kaggle notebook and placed in `artifacts/`. Weights, the
embedding index and thumbnails are **gitignored** and transferred by downloading
the Kaggle output. Small JSON files are committed.

| File                          | Content                                                                                   |
| ----------------------------- | ----------------------------------------------------------------------------------------- |
| `model.pt`                    | `{"state_dict", "arch", "img_size", "num_classes": 5, "preprocess": "v1", "version"}`     |
| `calibration.json`            | see below                                                                                 |
| `operating_curve.json`        | see below                                                                                 |
| `results.json`                | all measured metrics (lane A only; the only source for reported numbers)                  |
| `train_index.npz`             | `emb` (N×D float16, L2-normalised), `id_code` (N), `grade` (N); **train split only**      |
| `thumbs/{id_code}.jpg`        | 256 px preprocessed training-split images for similar cases                               |
| `quality_thresholds.json`     | quality-gate thresholds derived from the training split                                   |
| `splits.csv`                  | `id_code, diagnosis, split (train/val/test), dup_group`                                   |

### `calibration.json`

```json
{
  "temperature": 1.37,
  "abstain_threshold": 0.55,
  "referable_threshold": 0.31,
  "fitted_on": "validation",
  "abstain_rule": "abstain if max calibrated prob < abstain_threshold",
  "referable_rule": "referable if p2+p3+p4 >= referable_threshold",
  "target_val_coverage": 0.85,
  "target_val_sensitivity": 0.90
}
```

### `operating_curve.json`

Computed on the **validation** split with calibrated probabilities, for the
referable decision.

```json
{
  "source": "validation",
  "n": 550,
  "n_positive": 270,
  "positive_class": "referable (grade >= 2)",
  "default_threshold": 0.31,
  "mock": false,
  "points": [
    { "threshold": 0.05, "sensitivity": 0.99, "specificity": 0.62, "referral_rate": 0.69 }
  ]
}
```

`points` are sorted by `threshold` ascending, about 50 to 100 of them.

### Preprocessing (must be identical in training and serving)

`ml/common.py` is the single implementation: `crop_retina` → resize to `img_size`
→ (optional CLAHE, flag in `model.pt["preprocess"]`) → ImageNet normalisation.
Lane B must import it, not re-implement it.

### Serving: `ml/infer.py` (lane A provides, lane B wraps)

```python
from infer import RetinaModel, recommendation, priority
m = RetinaModel("artifacts")          # needs model.pt, calibration.json, train_index.npz
out = m.predict(rgb_uint8_array)      # run ml/quality.py first; only call this if quality is ok
# out = {"prediction", "recommendation", "priority", "evidence", "model", "latency_ms"}
```

`prediction`, `recommendation`, `priority`, `evidence` and `model` are already in
the shapes in section 3; the backend adds case_id, patient_id, eye, created_at,
status, image_url, quality, final_grade, decisions and disclaimer. Use
`recommendation(None)` and `priority(None)` for quality failures. Do not
re-implement calibration, thresholds, Grad-CAM or retrieval in `api/`.
