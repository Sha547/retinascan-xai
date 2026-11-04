# RetinaScan XAI

An explainable, uncertainty-aware diabetic retinopathy screening assistant
prototype: quality gate → calibrated DR grade (0 to 4) with abstention →
Grad-CAM and similar training cases → doctor triage queue → referral PDF.

> **Research prototype, not clinically validated.** It is trained and evaluated
> on public datasets, which are not the same as real primary-health-centre
> images. Final decisions must be made by a qualified ophthalmologist.

| Folder      | What                                                          |
| ----------- | ------------------------------------------------------------- |
| `web/`      | React + Vite frontend                                         |
| `api/`      | FastAPI backend (inference, quality gate, cases, decisions)   |
| `ml/`       | Preprocessing, splits, training, evaluation, quality gate     |
| `kaggle/`   | Kaggle GPU notebook runner (training/evaluation run there)    |
| `artifacts/`| Model outputs (weights are gitignored; JSON is committed)     |
| `docs/`     | `CONTRACT.md` (API and artifact shapes), fixtures, dataset notes |

Status and build plan: `PROGRESS.md`, `PLAN.md`. Measured results (once they
exist): `RESULTS.md`.

Run instructions will be added once the backend and frontend are wired.
