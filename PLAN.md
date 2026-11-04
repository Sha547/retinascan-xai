# RetinaScan XAI: build plan

Goal: a genuinely trained DR grading model on APTOS 2019, evaluated honestly
(held-out test and an external dataset), served through a working demo app with
quality gate, calibrated abstention, Grad-CAM, similar cases, triage queue and
referral PDF.

## Lanes and machines

| Lane | Agent | Machine | Owns | Branch |
| ---- | ----- | ------- | ---- | ------ |
| A: ML | Claude | 4050 laptop (drives Kaggle) | `ml/` (except lane B files), `kaggle/`, `artifacts/`, `docs/CONTRACT.md`, `RESULTS.md` | `main` (phase 0), then `lane-a-ml` |
| B: Backend | Claude | 3050 laptop (CPU only; demo machine) | `api/`, `ml/quality.py`, `ml/prepare_external.py`, `ml/tests/test_quality.py`, `docs/EXTERNAL_DATA.md` | `lane-b-backend` |
| C: Frontend | Codex | Mac | `web/` | `lane-c-frontend` |

Shared: `PROGRESS.md` (each lane edits only its own section), `PLAN.md`,
`CLAUDE.md`, `AGENTS.md` (lane A maintains).

**Why Kaggle for training:** the internet connection is about 0.3 to 0.6 MB/s, so
downloading APTOS (about 9.5 GB) locally would take about 10 hours. On Kaggle the
dataset is attached directly and a 16 GB GPU is free. Only small outputs
(weights, JSON, the embedding index, thumbnails) come back.

## Phases

### Phase 0 (lane A): setup. Status in PROGRESS.md.
Repo restructure (`web/`, `ml/`, `api/`), contract plus fixtures, rule files.

### Phase 1: build in parallel
- **A:** `ml/common.py` (preprocessing, model), `ml/make_splits.py` (dedupe
  near-duplicates, seeded stratified 70/15/15 split), `ml/train.py`,
  `ml/evaluate.py` (calibration on val, a single test evaluation, external set),
  `ml/embed.py` (train-split index plus thumbnails), Kaggle kernel runner. Launch training.
- **B:** FastAPI with a mock predictor and the real quality gate, SQLite, tests;
  `quality.py`; external dataset research and `prepare_external.py`.
- **C:** frontend rework against fixtures and the mock API: real quality/retake,
  abstain state, similar cases, lesion claims removed, triage queue with accept/override.

**Gate 1:** `artifacts/model.pt` exists, the mock API tests pass, and the UI works on fixtures.

### Phase 2: make it real
- **A:** evaluation on Kaggle: `results.json`, `calibration.json`,
  `operating_curve.json`, reliability diagram, abstention table, external
  results, quality thresholds (running lane B's `quality.py` on the train split),
  degradation test (blur/darken) on test images.
- **B:** real CPU predictor in `api/inference.py`: model plus calibration,
  Grad-CAM, kNN similar cases from `train_index.npz`.
- **C:** operating-point slider (`/api/operating-curve`), switch to the real API,
  real heatmap in the UI and PDF.

**Gate 2:** a real upload goes through the whole flow, and `results.json` exists.

### Phase 3: verify and package
- **A:** `RESULTS.md` (numbers only from `results.json`), 5 demo cases.
- **Reviewer (Codex, fresh session):** independent audit for leakage, test
  tuning, overclaims and untraceable numbers. Reports only, fixes nothing.
- **B/C:** fix the review findings; one-command start on the 3050; screenshots;
  backup video.

## Things only the user can do
- Kaggle: phone verification (for GPU and internet in notebooks), join the
  APTOS 2019 competition and accept its rules, put `~/.kaggle/kaggle.json` on the 4050.
- Any external-dataset registration.
- Choose the default operating point (is a missed case or a false referral worse?).
- Push and merge branches on GitHub.
