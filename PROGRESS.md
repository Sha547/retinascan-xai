# Progress log

Each lane edits only its own section. Newest entries at the top of each section.
Format: `- [YYYY-MM-DD HH:MM] DONE|RUNNING|FAILED|BLOCKED: what`

## Lane A: ML (Claude, 4050)

- [2026-11-05] DONE: synthetic CPU smoke test passes end to end (`ml/tests/smoke_synthetic.py`). It found and fixed 2 bugs: an over-merging duplicate hash (95/153 images merged) and a pickle-only `train_index.npz`.
- [2026-11-05] DONE: ML pipeline on branch `lane-a-ml`: `ml/common.py`, `prepare_data.py`, `train.py`, `evaluate.py`, `embed.py`, `kaggle/build_kernel.py`. Local venv at `.venv` (CPU torch, Kaggle CLI 2.2.5).
- [2026-11-05 02:35] DONE: full training plus evaluation (`effnet-b0-512-exp1`, Kaggle `sha547/retinascan-full`). Best val QWK 0.906 (epoch 11), so no rerun was needed. Test results are in `artifacts/results.json` (QWK 0.891, referable sens 0.924 / spec 0.916, AUC 0.976, ECE 0.103->0.040, abstention 12.5%, acc graded 0.858 vs 0.808). Data: 3662 images, 0 unreadable; 131 near-duplicate groups (270 images, 37 with conflicting labels) kept within one split. Weights, index and thumbs are in `kaggle/out/full/artifacts/` (gitignored); fetch with `kaggle kernels output sha547/retinascan-full`.
- [2026-11-05 02:30] DONE: `ml/infer.py` (serving API for lane B), `degrade_test.py`, `check_serving.py`, Phase 2 Kaggle runner. Contract v1.1 pushed to main.
- [2026-11-05] WAITING on lane B: `ml/quality.py` CLI args, `ml/prepare_external.py`, IDRiD Kaggle slug, so Phase 2 can run on Kaggle.
- [2026-11-05 02:12] DONE: Kaggle smoke run passed (300 images, T4 GPU, all artifacts produced; model.pt and the index load on local CPU). Its metrics are not results.
- [2026-11-05 02:07] DONE: Kaggle token set up (user sha547); APTOS competition joined.

- [2026-11-05] DONE: Phase 0 restructure: UI moved to `web/`; `ml/`, `api/`, `kaggle/`, `artifacts/` created; `docs/CONTRACT.md` v1 plus fake fixtures in `docs/fixtures/`; `CLAUDE.md`, `AGENTS.md`, `PLAN.md`, root `.gitignore`.
- [2026-11-05] BLOCKED (user): the 4050 needs a reboot to load the NVIDIA driver (installed; still on kernel 7.0.0-30). Not needed for Kaggle training.
- [2026-11-05] NOTE: no system pip on the 4050; the project venv `.venv` was created with a standalone `uv` (no sudo).
- NOTE: the internet is about 0.3 MB/s on the 4050, so training and evaluation run on Kaggle, not locally.

## Lane B: Backend (Claude, 3050)

- [2026-11-05 03:38] BLOCKED (user): Phase 2 steps 3 to 5 (`RealPredictor`, real-predictor test, CPU latency) have not started. `artifacts/model.pt`, `artifacts/train_index.npz` and `artifacts/thumbs/` are not on this machine. `~/Downloads/retinascan_model.zip` is 12 KB of old scripts with no weights.
- [2026-11-05 03:38] DONE: `ml/common.py` and `ml/infer.py` taken unedited from `origin/lane-a-ml`. `ml/quality.py` now uses `from common import crop_retina`; the stand-in is deleted. Tests pass, still on synthetic images only.
- [2026-11-05 03:38] NOTE for lane A: `ml/quality.py` and `ml/prepare_external.py` are on `lane-b-backend`. Get them with `git checkout origin/lane-b-backend -- ml/quality.py ml/prepare_external.py`. `quality.py` imports `common`, so both must sit in the same folder (`build_kernel.py` already packs `ml/*.py` together).
- [2026-11-05 03:38] NOTE for lane A: thresholds command (reads `split == "train"` rows only for the thresholds, writes `quality_thresholds.json` and `quality_stats.csv` to `--out_dir`):
  `python quality.py --img_dir <APTOS train_images> --splits <artifacts/splits.csv> --out_dir <artifacts>`
  Optional, with defaults: `--low_pct 1.0 --high_pct 99.0 --workers 4`. Do not change the percentiles based on test or external results.
- [2026-11-05 03:38] NOTE for lane A: IDRiD Kaggle slug: `aaryapatel98/indian-diabetic-retinopathy-image-dataset`. Attach it to the phase 2 kernel. Both settings together for `build_kernel.py`:
  `python kaggle/build_kernel.py --stage phase2 --set ext_dataset=aaryapatel98/indian-diabetic-retinopathy-image-dataset 'quality_cmd=["--img_dir","{IMG_DIR}","--splits","{SPLITS}","--out_dir","{OUT}"]'`
  Please copy `quality_thresholds.json` to this machine with the other artifacts. The API uses placeholder thresholds and logs a warning until then.
- DONE: contract v1.1 applied: heatmap longest side capped at 1024, and `Predictor.predict()` returns the same keys as `ml/infer.py`. Phase 2 removes `recommendation_for` and `priority_for` from `api/` in favour of the `infer` versions.
- [2026-11-05 02:28] DONE: Stage 2 pushed on `lane-b-backend`: FastAPI service with every contract endpoint, `MockPredictor`, real quality gate, SQLite cases and append-only decisions, triage queue, upload validation. Tests pass for `api/` and `ml/tests/`. Checked on a real server over the LAN with synthetic images.
- [2026-11-05 02:28] NOTE for lane C: run from the repo root with `uvicorn api.main:app --host 0.0.0.0 --port 8000`, then use `http://192.168.2.190:8000` (`hostname -I`; it can change if this laptop reconnects). CORS is open to all origins. The server only runs while it is started here.
- [2026-11-05 02:28] NOTE for lane A: IDRiD slug, folder layout and commands are at the top of `docs/EXTERNAL_DATA.md`. Messidor-2 is skipped (user decision), so `prepare_external.py` is IDRiD only. Its output works with `evaluate.py --ext_csv/--ext_dir`.
- [2026-11-05 02:28] NOTE: very dark images that fall below the retina mask report `poor_field` ("No retina found"), not `too_dark`. Revisit on real images.
- [2026-11-05 02:28] NOT VERIFIED: the quality gate has only run on synthetic images. Placeholder thresholds are hand-picked, not derived from data.

## Lane C: Frontend (Codex, Mac)

- [2026-11-05 03:51] DONE: Fixed preview startup behind a failed proxy: non-envelope 502/504 health failures now show the fallback notice and use fixtures; genuine API envelopes retain their messages. Added Open fixture demo on the connection error screen. Eight API tests pass. Dependencies are now present; npm run build passes and npm run lint passes without warnings. Queue loading resets moved to user events to clear the lint warning.
- [2026-11-05 03:51] BLOCKED: starting Vite inside this agent session fails with listen EPERM on 127.0.0.1:5173. The user can keep their own Terminal dev server running and open its URL with ?demo=1. Browser/PDF visual verification remains outstanding.

- [2026-11-05 03:45] DONE: Phase 1 frontend implementation in web/: contract API/error handling and proxy; exact fixture copies and fallback notice; multipart upload; actual quality/retake state; abstention and five-grade probabilities; aligned PNG overlay/split view; similar-case strip; doctor queue and accept/override history; server-backed screening history; Case-based jsPDF with model version/reviewer decisions/disclaimer. Removed scripted model metrics and lesion claims. README updated; no heavy dependencies added.
- [2026-11-05 03:45] DONE: 7 dependency-free API tests pass, covering fixture fidelity, queue ordering, decisions and validation, empty queue, network-only fallback, malformed/HTTP errors, live multipart and image/error handling. All 18 source JS/JSX files parse; 39 relative imports resolve. All 9 fixture copies match their source bytes. Text contrast and keyboard focus improved; git diff --check passes.
- [2026-11-05 03:45] BLOCKED: npm install cannot resolve registry.npmjs.org (online and cache-only attempts failed). npm run build and npm run lint were attempted but cannot start (vite/oxlint missing). Browser flow, phone/desktop rendering and actual PDF output have NOT been verified. Phase 1 is not yet signed off.
- [2026-11-05 03:45] BLOCKED: Lane B now publishes http://192.168.2.190:8000 on lane-b-backend; GET /api/health from this Mac failed to connect. Live integration remains unverified. Use VITE_API_PROXY=http://192.168.2.190:8000 when reachable; default remains localhost:8000 for Linux.
- [2026-11-05 03:45] BLOCKED: git push -u origin lane-c-frontend failed because github.com cannot resolve from the shell; connector access is read-only. Work is committed locally only. After restoring access: install dependencies, run build/lint and the README walkthrough on fixtures and the live API, then push this branch. Never push to main.
- [2026-11-05 03:45] NOTE: Checked remote contract v1.1 update (PNG heatmap longest side capped at 1024). Existing viewer/report scale by aspect ratio and alignment, so no schema change is needed. docs/CONTRACT.md remains untouched. Summary-only fixture gap is under Contract change requests.

- [2026-11-05 02:40] RUNNING: Phase 1 API layer and exact fixture copies implemented; working on evidence, queue and PDF integration in web/.
- [2026-11-05 02:40] BLOCKED: shell DNS cannot resolve github.com or registry.npmjs.org. Retrieved the exact main snapshot through the read-only GitHub connector and recovered original commit 9be5338 on lane-c-frontend. npm install (online and cache-only) failed; build/lint and push remain unverified. No backend LAN IP is published in Lane B yet.

## Contract change requests

- [2026-11-05, Lane C] Please supply full Case fixtures for c_20261105_a10004 and c_20261105_a10005. They appear in cases_all/pending but have no matching detail payload. Frontend demo shows their provided summary values and labels missing probabilities, recommendation and evidence as unavailable; no values are invented. No API schema change requested.

## Review findings (Phase 3)

_(none yet)_
