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

_(not started)_

## Lane C: Frontend (Codex, Mac)

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
