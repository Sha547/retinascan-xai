"""Check that serving (infer.py on a raw image) matches evaluation and the index.

1. Probability parity: for validation images, RetinaModel.predict(raw) must give
   the same calibrated probabilities as predictions_val.csv from evaluate.py
   (same preprocessing, same temperature). Small fp16-vs-fp32 noise is allowed.
2. Self-retrieval: a raw training image must find itself as its top similar case,
   which proves the index rows are aligned and serving embeddings match.
3. The index contains no validation or test image.

Writes serving_check.json in --out; exits non-zero if a check fails.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from common import load_rgb, save_json
from infer import RetinaModel


def find(img_dir, i):
    return next(p for ext in (".png", ".jpg", ".jpeg") if (p := Path(img_dir) / f"{i}{ext}").exists())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--artifacts", required=True, help="dir with model.pt, calibration.json, train_index.npz, "
                    "predictions_val.csv, splits.csv")
    ap.add_argument("--img_dir", required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    art = Path(a.artifacts)
    m = RetinaModel(art)
    sp = pd.read_csv(art / "splits.csv")
    pv = pd.read_csv(art / "predictions_val.csv").head(a.n)

    diffs, agree = [], 0
    for _, r in pv.iterrows():
        out = m.predict(load_rgb(find(a.img_dir, r.id_code)), with_evidence=False)
        p = np.array(out["prediction"]["probs"])
        ref = r[[f"p{k}" for k in range(5)]].values.astype(float)
        diffs.append(float(np.abs(p - ref).max()))
        agree += int(p.argmax() == ref.argmax())

    tr = sp[sp.split == "train"].head(a.n)
    self_top1 = 0
    for i in tr.id_code:
        sim = m.predict(load_rgb(find(a.img_dir, i)))["evidence"]["similar"]
        self_top1 += int(sim[0]["id_code"] == i)

    held_out = set(sp[sp.split != "train"].id_code)
    leaked = sorted(held_out & set(map(str, m.index_ids)))

    res = {
        "prob_parity": {"n": len(diffs), "max_abs_diff": max(diffs), "median_abs_diff": float(np.median(diffs)),
                        "argmax_agreement": agree / len(diffs)},
        "self_retrieval_top1": {"n": len(tr), "rate": self_top1 / len(tr)},
        "index_contains_val_or_test": len(leaked),
    }
    res["passed"] = bool(res["prob_parity"]["max_abs_diff"] < 0.02 and res["prob_parity"]["argmax_agreement"] >= 0.98
                         and res["self_retrieval_top1"]["rate"] >= 0.95 and not leaked)
    save_json(res, Path(a.out) / "serving_check.json")
    print(res, flush=True)
    sys.exit(0 if res["passed"] else 1)


if __name__ == "__main__":
    main()
