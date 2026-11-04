# Progress log

Each lane edits only its own section. Newest entries at the top of each section.
Format: `- [YYYY-MM-DD HH:MM] DONE|RUNNING|FAILED|BLOCKED: what`

## Lane A: ML (Claude, 4050)

- [2026-11-05] DONE: Phase 0 restructure: UI moved to `web/`; `ml/`, `api/`, `kaggle/`, `artifacts/` created; `docs/CONTRACT.md` v1 plus fake fixtures in `docs/fixtures/`; `CLAUDE.md`, `AGENTS.md`, `PLAN.md`, root `.gitignore`.
- [2026-11-05] BLOCKED (user): Kaggle not set up yet (`~/.kaggle/kaggle.json` missing; needs phone verification plus APTOS competition rules accepted).
- [2026-11-05] BLOCKED (user): the 4050 needs a reboot to load the NVIDIA driver (installed; still on kernel 7.0.0-30). Not needed for Kaggle training.
- [2026-11-05] NOTE: local pip/venv missing on the 4050 (`sudo apt install -y python3-pip python3-venv`). Code is syntax-checked locally and run on Kaggle.
- NOTE: the internet is about 0.3 MB/s on the 4050, so training and evaluation run on Kaggle, not locally.

## Lane B: Backend (Claude, 3050)

- [2026-11-05 02:28] DONE: Stage 2 pushed on `lane-b-backend`: FastAPI service with every contract endpoint, `MockPredictor`, real quality gate, SQLite cases and append-only decisions, triage queue, upload validation. Tests pass for `api/` and `ml/tests/`. Checked on a real server over the LAN with synthetic images.
- [2026-11-05 02:28] NOTE for lane C: run from the repo root with `uvicorn api.main:app --host 0.0.0.0 --port 8000`, then use `http://192.168.2.190:8000` (`hostname -I`; it can change if this laptop reconnects). CORS is open to all origins. The server only runs while it is started here.
- [2026-11-05 02:28] NOTE for lane A: IDRiD slug, folder layout and commands are at the top of `docs/EXTERNAL_DATA.md`. Messidor-2 is skipped (user decision), so `prepare_external.py` is IDRiD only. Its output works with `evaluate.py --ext_csv/--ext_dir`.
- [2026-11-05 02:28] NOTE for lane A: run `ml/quality.py` on the train split and put `quality_thresholds.json` in `artifacts/`. The API uses the placeholder thresholds and logs a warning until that file exists.
- [2026-11-05 02:28] TODO after `lane-a-ml` merges into main: `ml/quality.py` must switch from its stand-in to `from common import crop_retina`. This is not only an import change: `common.crop_retina` takes RGB and returns `(square, box)`, while the stand-in takes BGR and returns the crop. Regenerate `quality_thresholds.json` after the switch, because thresholds are only valid for the crop that produced them.
- [2026-11-05 02:28] NOTE: very dark images that fall below the retina mask report `poor_field` ("No retina found"), not `too_dark`. Revisit on real images.
- [2026-11-05 02:28] NOT VERIFIED: the quality gate has only run on synthetic images. Placeholder thresholds are hand-picked, not derived from data.

## Lane C: Frontend (Codex, Mac)

_(not started)_

## Contract change requests

- [2026-11-05 02:28] Lane B: section 3 `Case` example has `priority: 0.995`, but section 1's formula gives 1.025 for those values (0.88 + 0.5 * 0.29). The fixture has 1.025. The API follows the formula; please correct the example.
- [2026-11-05 02:28] Lane B: `heatmap_note` under the mock says "Mock heatmap for development. Not Grad-CAM and not derived from image content.", because the fixture's Grad-CAM wording would be false for fake output. Please confirm the mock may differ. The real predictor will use the contract wording.
- [2026-11-05 02:28] Lane B: the Errors list has no 409 (the decision section uses it, with code `bad_request`) and does not cover image dimensions. The API returns 400 `bad_request` above 60 megapixels, to stop tiny files that decode to gigabytes. Please add both.
- [2026-11-05 02:28] Lane B: `quality_thresholds.json` has no documented shape. Proposed keys: `derived_from_data`, `sharpness_min`, `brightness_min`, `brightness_max`, `contrast_min`, `coverage_min`, `glare_max`, plus provenance fields written by `ml/quality.py`.
- [2026-11-05 02:28] Lane B: please add `ml/tests/test_prepare_external.py` and `ml/quality_thresholds.placeholder.json` to lane B's paths in `PLAN.md`.
- [2026-11-05 02:28] Lane B: `.gitignore` has `.venv/`, which does not match the symlinked `.venv` that the lane B setup uses. Changing it to `.venv` would cover both. Excluded locally for now.

## Review findings (Phase 3)

_(none yet)_
