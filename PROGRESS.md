# Progress log

Each lane edits only its own section. Newest entries at the top of each section.
Format: `- [YYYY-MM-DD HH:MM] DONE|RUNNING|FAILED|BLOCKED: what`

## Lane A: ML (Claude, 4050)

- [2026-11-05] DONE: synthetic CPU smoke test passes end to end (`ml/tests/smoke_synthetic.py`). It found and fixed 2 bugs: an over-merging duplicate hash (95/153 images merged) and a pickle-only `train_index.npz`.
- [2026-11-05] DONE: ML pipeline on branch `lane-a-ml`: `ml/common.py`, `prepare_data.py`, `train.py`, `evaluate.py`, `embed.py`, `kaggle/build_kernel.py`. Local venv at `.venv` (CPU torch, Kaggle CLI 2.2.5).
- [2026-11-05 02:20] RUNNING: full training on Kaggle (`sha547/retinascan-full`): effnet-b0, 512px, 15 epochs, bs 16, T4. Version `effnet-b0-512-exp1`.
- [2026-11-05 02:12] DONE: Kaggle smoke run passed (300 images, T4 GPU, all artifacts produced; model.pt and the index load on local CPU). Its metrics are not results.
- [2026-11-05 02:07] DONE: Kaggle token set up (user sha547); APTOS competition joined.

- [2026-11-05] DONE: Phase 0 restructure: UI moved to `web/`; `ml/`, `api/`, `kaggle/`, `artifacts/` created; `docs/CONTRACT.md` v1 plus fake fixtures in `docs/fixtures/`; `CLAUDE.md`, `AGENTS.md`, `PLAN.md`, root `.gitignore`.
- [2026-11-05] BLOCKED (user): Kaggle not set up yet (`~/.kaggle/kaggle.json` missing; needs phone verification plus APTOS competition rules accepted).
- [2026-11-05] BLOCKED (user): the 4050 needs a reboot to load the NVIDIA driver (installed; still on kernel 7.0.0-30). Not needed for Kaggle training.
- [2026-11-05] NOTE: local pip/venv missing on the 4050 (`sudo apt install -y python3-pip python3-venv`). Code is syntax-checked locally and run on Kaggle.
- NOTE: the internet is about 0.3 MB/s on the 4050, so training and evaluation run on Kaggle, not locally.

## Lane B: Backend (Claude, 3050)

_(not started)_

## Lane C: Frontend (Codex, Mac)

_(not started)_

## Contract change requests

_(none)_

## Review findings (Phase 3)

_(none yet)_
