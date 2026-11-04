"""Build the similar-case index from TRAINING-split images only.

Writes to --out:
  train_index.npz   emb (N x D float16, L2-normalised pooled features), id_code, grade
  thumbs/<id>.jpg   256 px preprocessed images shown as "similar cases"

Validation and test images are never put in the index, so the app can never show
a test image (or its label) as evidence.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch

from common import load_checkpoint, make_dataset


@torch.no_grad()
def embed(model, ids, cache_dir, device, bs=32, workers=4):
    ds = make_dataset(ids, [0] * len(ids), cache_dir, train=False)
    dl = torch.utils.data.DataLoader(ds, batch_size=bs, shuffle=False, num_workers=workers)
    feats = []
    for x, _ in dl:
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
            f = model.forward_head(model.forward_features(x.to(device)), pre_logits=True)
        feats.append(torch.nn.functional.normalize(f.float(), dim=1).cpu())
    return torch.cat(feats).numpy()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--splits", required=True)
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--thumb", type=int, default=256)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, _ = load_checkpoint(args.ckpt, device)
    df = pd.read_csv(args.splits)
    tr = df[df.split == "train"].reset_index(drop=True)
    assert set(tr.split) == {"train"}

    emb = embed(model, tr.id_code, args.cache_dir, device, workers=args.workers)
    out = Path(args.out)
    (out / "thumbs").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "train_index.npz", emb=emb.astype(np.float16),
                        id_code=np.array(tr.id_code.tolist(), dtype="U"),  # unicode, loads without pickle
                        grade=tr.diagnosis.values.astype(np.int8))
    for id_code in tr.id_code:
        img = cv2.imread(str(Path(args.cache_dir) / f"{id_code}.png"))
        cv2.imwrite(str(out / "thumbs" / f"{id_code}.jpg"),
                    cv2.resize(img, (args.thumb, args.thumb), interpolation=cv2.INTER_AREA),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"index: {emb.shape[0]} train images, dim {emb.shape[1]}; thumbs in {out / 'thumbs'}")


if __name__ == "__main__":
    main()
