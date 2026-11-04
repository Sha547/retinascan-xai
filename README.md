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

Status and build plan: `PROGRESS.md`, `PLAN.md`. Measured results:
`RESULTS.md` (generated from `artifacts/results.json`; never edited by hand).

## Run it (Linux; CPU is enough)

```bash
# 1. Python environment (CPU-only PyTorch, about 300 MB to download)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# 2. Trained model and serving artifacts (about 50 MB) from the Kaggle run.
#    Needs ~/.kaggle/kaggle.json for the Kaggle account that ran the kernels.
scripts/fetch_artifacts.sh

# 3. Start the API (:8000) and the web app (:5173). Ctrl+C stops both.
scripts/start.sh
```

Open http://localhost:5173. Other devices on the same Wi-Fi can use the IP that
`start.sh` prints. Without `artifacts/model.pt`, the API serves a **mock**
predictor, and every response says `model.mock: true`. To force it, run
`PREDICTOR=mock scripts/start.sh`.

| Check | Command |
| ----- | ------- |
| API alive, real model loaded | `curl localhost:8000/api/health` (look for `"mock": false`) |
| Backend and ML tests | `.venv/bin/python -m pytest -q api/tests ml/tests` |
| ML pipeline end to end on synthetic data | `.venv/bin/python ml/tests/smoke_synthetic.py` |
| One image from the command line | `cd ml && ../.venv/bin/python infer.py --artifacts ../artifacts --image IMG.png` |

## Reproduce training and evaluation (Kaggle GPU)

The dataset is about 9.5 GB, so training runs on Kaggle, where APTOS is attached
directly.

```bash
.venv/bin/python kaggle/build_kernel.py --stage full      # train plus evaluate on APTOS (T4, about 15 min)
.venv/bin/kaggle kernels push -p kaggle/kernel
.venv/bin/python kaggle/build_kernel.py --stage phase2 \
  --set ext_dataset=aaryapatel98/indian-diabetic-retinopathy-image-dataset \
  'quality_cmd=["--img_dir","{IMG_DIR}","--splits","{SPLITS}","--out_dir","{OUT}"]'
.venv/bin/kaggle kernels push -p kaggle/kernel             # IDRiD, quality thresholds, degradation, serving check
.venv/bin/python ml/make_results_md.py --artifacts artifacts --out RESULTS.md
```

## Data and attribution

- **APTOS 2019 Blindness Detection** (Kaggle competition data; used under the
  competition rules; images are not redistributed in this repo).
- **IDRiD**: Porwal et al., "Indian Diabetic Retinopathy Image Dataset (IDRiD)",
  IEEE DataPort, 2018, doi:10.21227/H25W98; Porwal et al., *Data* 3(3):25, 2018,
  doi:10.3390/data3030025. CC BY 4.0. Used only as an external test set.
