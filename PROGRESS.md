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

_(not started)_

## Lane C: Frontend (Codex, Mac)

_(not started)_

## Contract change requests

_(none)_

## Review findings (Phase 3)

_(none yet)_
