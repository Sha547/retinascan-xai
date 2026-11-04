"""Verify APTOS, cache preprocessed images, find near-duplicates, write a leak-free split.

Steps
1. Check train.csv has id_code/diagnosis and every id has a readable image.
2. Preprocess every image once (crop retina, resize, CLAHE) into --cache_dir.
3. Hash each preprocessed image (dHash) and group near-duplicates (Hamming
   distance <= --dup_dist). APTOS is known to contain duplicate images, some
   with different labels; a duplicate in train and its twin in test would leak.
4. Stratified *group* split 70/15/15 with a fixed seed: a duplicate group never
   spans two splits.

Outputs (in --out_dir): splits.csv (id_code, diagnosis, split, dup_group),
data_report.json (class counts, unreadable ids, duplicate stats).

The split is made before any training or tuning and is never changed afterwards.
"""
from __future__ import annotations

import argparse
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from common import dhash, load_rgb, preprocess, save_json

_ARGS = None


def _find_image(img_dir: Path, id_code: str):
    for ext in (".png", ".jpg", ".jpeg", ".tif"):
        p = img_dir / f"{id_code}{ext}"
        if p.exists():
            return p
    return None


def _work(item):
    id_code, src = item
    out = Path(_ARGS.cache_dir) / f"{id_code}.png"
    try:
        if out.exists():
            img = cv2.cvtColor(cv2.imread(str(out)), cv2.COLOR_BGR2RGB)
            # Hash on the cached (already preprocessed) image.
            return id_code, dhash(img), None
        raw = load_rgb(src)
        img, _ = preprocess(raw, _ARGS.size, clahe=not _ARGS.no_clahe)
        cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        return id_code, dhash(img), None
    except Exception as e:  # noqa: BLE001 - report every failure, keep going
        return id_code, None, f"{type(e).__name__}: {e}"


def _init(args):
    global _ARGS
    _ARGS = args


def group_duplicates(hashes: np.ndarray, max_dist: int) -> np.ndarray:
    """Union-find over pairs with Hamming distance <= max_dist. Returns group ids.

    hashes: (n, n_bytes) uint8 packed bit hashes.
    """
    n = len(hashes)
    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        x = np.bitwise_xor(hashes[i], hashes[i + 1:])
        d = np.unpackbits(x, axis=1).sum(axis=1)
        for j in np.nonzero(d <= max_dist)[0]:
            a, b = find(i), find(i + 1 + int(j))
            if a != b:
                parent[b] = a
    roots = np.array([find(i) for i in range(n)])
    _, groups = np.unique(roots, return_inverse=True)
    return groups


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, help="APTOS train.csv")
    ap.add_argument("--img_dir", required=True, help="APTOS train_images/")
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--no_clahe", action="store_true")
    ap.add_argument("--dup_dist", type=int, default=20,
                    help="max Hamming distance (of 256 bits) between dHashes to call two images duplicates")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="use only the first N rows (smoke test)")
    args = ap.parse_args()

    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.csv)
    missing_cols = {"id_code", "diagnosis"} - set(df.columns)
    if missing_cols:
        raise SystemExit(f"train.csv missing columns: {missing_cols}")
    if args.limit:
        df = df.head(args.limit).copy()
    if not df["diagnosis"].isin(range(5)).all():
        raise SystemExit("diagnosis values outside 0..4")
    if df["id_code"].duplicated().any():
        raise SystemExit("duplicate id_code rows in train.csv")

    img_dir = Path(args.img_dir)
    items, no_file = [], []
    for id_code in df["id_code"]:
        p = _find_image(img_dir, id_code)
        (items.append((id_code, p)) if p else no_file.append(id_code))
    print(f"rows={len(df)} with_image={len(items)} missing_file={len(no_file)}", flush=True)

    hashes, unreadable = {}, {}
    with Pool(args.workers, initializer=_init, initargs=(args,)) as pool:
        for k, (id_code, h, err) in enumerate(pool.imap_unordered(_work, items, chunksize=8), 1):
            if err:
                unreadable[id_code] = err
            else:
                hashes[id_code] = h
            if k % 500 == 0:
                print(f"  preprocessed {k}/{len(items)}", flush=True)

    good = df[df["id_code"].isin(hashes)].reset_index(drop=True)
    hv = np.stack([hashes[i] for i in good["id_code"]])
    good["dup_group"] = group_duplicates(hv, args.dup_dist)

    sizes = good.groupby("dup_group")["id_code"].transform("size")
    largest = int(sizes.max())
    print(f"largest duplicate group: {largest} images", flush=True)
    if largest > max(10, 0.02 * len(good)):
        raise SystemExit(f"a duplicate group has {largest} images: the hash threshold (--dup_dist "
                         f"{args.dup_dist}) is merging unrelated images. Lower it and rerun.")
    dup_groups = good[sizes > 1].groupby("dup_group")
    conflicts = [g for g, d in dup_groups if d["diagnosis"].nunique() > 1]

    # 20 folds -> 14 train / 3 val / 3 test = 70/15/15, groups kept intact.
    sgkf = StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=args.seed)
    fold = np.empty(len(good), dtype=int)
    for f, (_, idx) in enumerate(sgkf.split(good, good["diagnosis"], good["dup_group"])):
        fold[idx] = f
    good["split"] = np.where(fold < 14, "train", np.where(fold < 17, "val", "test"))

    # Leakage check: no duplicate group may appear in two splits.
    spans = good.groupby("dup_group")["split"].nunique()
    assert (spans == 1).all(), "duplicate group spans splits"

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    good[["id_code", "diagnosis", "split", "dup_group"]].to_csv(out / "splits.csv", index=False)

    counts = {s: good[good.split == s]["diagnosis"].value_counts().sort_index().to_dict()
              for s in ("train", "val", "test")}
    report = {
        "n_rows_csv": int(len(df)),
        "n_used": int(len(good)),
        "missing_file": no_file,
        "unreadable": unreadable,
        "class_counts_all": good["diagnosis"].value_counts().sort_index().to_dict(),
        "class_counts_by_split": counts,
        "split_sizes": good["split"].value_counts().to_dict(),
        "duplicates": {
            "dhash_max_distance": args.dup_dist,
            "n_groups_with_duplicates": int(dup_groups.ngroups),
            "n_images_in_duplicate_groups": int((sizes > 1).sum()),
            "n_groups_with_conflicting_labels": len(conflicts),
            "note": "Duplicate groups are kept within one split. Conflicting-label groups are kept as is.",
        },
        "preprocess": {"size": args.size, "clahe": not args.no_clahe},
        "seed": args.seed,
    }
    save_json(report, out / "data_report.json")
    print(f"split sizes: {report['split_sizes']}")
    print(f"class counts: {report['class_counts_all']}")
    print(f"duplicates: {report['duplicates']}")
    print(f"unreadable: {len(unreadable)} missing: {len(no_file)}")


if __name__ == "__main__":
    main()
