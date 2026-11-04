"""Preprocess the images of selected splits into a cache dir (never rewrites splits.csv).

  python cache_images.py --splits splits.csv --img_dir train_images --cache_dir /tmp/c --size 512 --which val,test
"""
from __future__ import annotations

import argparse
from multiprocessing import Pool
from pathlib import Path

import cv2
import pandas as pd

from common import load_rgb, preprocess

_A = None


def _init(a):
    global _A
    _A = a


def _work(i):
    out = Path(_A.cache_dir) / f"{i}.png"
    if out.exists():
        return None
    src = next((p for ext in (".png", ".jpg", ".jpeg") if (p := Path(_A.img_dir) / f"{i}{ext}").exists()), None)
    if src is None:
        return i
    img, _ = preprocess(load_rgb(src), _A.size, clahe=not _A.no_clahe)
    cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", required=True)
    ap.add_argument("--img_dir", required=True)
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--no_clahe", action="store_true")
    ap.add_argument("--which", default="val,test")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    Path(a.cache_dir).mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(a.splits)
    ids = df[df.split.isin(a.which.split(","))].id_code.tolist()
    with Pool(a.workers, initializer=_init, initargs=(a,)) as pool:
        missing = [m for m in pool.imap_unordered(_work, ids, chunksize=8) if m]
    print(f"cached {len(ids) - len(missing)} images for splits {a.which}; missing {len(missing)}")
    if missing:
        raise SystemExit(f"missing images: {missing[:5]}")


if __name__ == "__main__":
    main()
