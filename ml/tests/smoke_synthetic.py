"""CPU smoke test of the full ML chain on synthetic fundus-like images.

  .venv/bin/python ml/tests/smoke_synthetic.py

Generates 150 fake images (plus planted exact and near duplicates), then runs
prepare_data -> train (1 epoch, no pretrained weights, 64 px) -> evaluate -> embed
and checks the outputs. It proves the code runs end to end; the numbers mean nothing.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ML = Path(__file__).resolve().parent.parent


def fake_fundus(rng, grade, size=200):
    img = np.zeros((size, int(size * 1.3), 3), np.uint8)
    cy, cx, r = size // 2, int(size * 0.65), int(size * 0.45)
    cv2.circle(img, (cx, cy), r, (int(rng.integers(150, 200)), int(rng.integers(60, 90)), 20), -1)
    for _ in range(grade * 6 + int(rng.integers(0, 4))):   # "lesions" scale with grade
        a, d = rng.uniform(0, 2 * np.pi), rng.uniform(0, r * 0.8)
        cv2.circle(img, (int(cx + d * np.cos(a)), int(cy + d * np.sin(a))), int(rng.integers(2, 5)),
                   (90, 20, 10), -1)
    noise = rng.integers(0, 40, img.shape, dtype=np.uint8)
    return cv2.GaussianBlur(cv2.add(img, noise), (0, 0), 1.0)  # real photos are smooth, not per-pixel noise


def run(*args):
    print("$", " ".join(map(str, args)), flush=True)
    subprocess.run([sys.executable, *map(str, args)], cwd=ML, check=True)


def main():
    rng = np.random.default_rng(0)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        imgs = tmp / "train_images"
        imgs.mkdir()
        rows = []
        for i in range(150):
            g = i % 5
            cv2.imwrite(str(imgs / f"img{i:04d}.png"), cv2.cvtColor(fake_fundus(rng, g), cv2.COLOR_RGB2BGR))
            rows.append((f"img{i:04d}", g))
        # planted duplicates: exact copy, and a resized copy with a conflicting label
        src = cv2.imread(str(imgs / "img0003.png"))
        cv2.imwrite(str(imgs / "dupA.png"), src)
        cv2.imwrite(str(imgs / "dupB.png"), cv2.resize(src, None, fx=1.5, fy=1.5))
        rows += [("dupA", 3), ("dupB", 2)]
        pd.DataFrame(rows, columns=["id_code", "diagnosis"]).to_csv(tmp / "train.csv", index=False)
        # a corrupt file must be reported, not crash the run
        (imgs / "broken.png").write_bytes(b"not an image")
        pd.concat([pd.read_csv(tmp / "train.csv"), pd.DataFrame([("broken", 0)], columns=["id_code", "diagnosis"])]
                  ).to_csv(tmp / "train.csv", index=False)

        art, cache, run_dir = tmp / "art", tmp / "cache", tmp / "run"
        run("prepare_data.py", "--csv", tmp / "train.csv", "--img_dir", imgs, "--cache_dir", cache,
            "--out_dir", art, "--size", 64, "--workers", 2)
        rep = json.loads((art / "data_report.json").read_text())
        sp = pd.read_csv(art / "splits.csv")
        assert "broken" in rep["unreadable"], "corrupt image not reported"
        g = sp.set_index("id_code").dup_group
        assert g["img0003"] == g["dupA"] == g["dupB"], "planted duplicates not grouped"
        assert sp.groupby("dup_group").split.nunique().max() == 1, "duplicate group spans splits"
        assert rep["duplicates"]["n_groups_with_conflicting_labels"] >= 1

        run("train.py", "--splits", art / "splits.csv", "--cache_dir", cache, "--out", run_dir, "--size", 64,
            "--epochs", 1, "--bs", 8, "--workers", 0, "--no_pretrained")
        run("evaluate.py", "--ckpt", run_dir / "best.pt", "--splits", art / "splits.csv", "--cache_dir", cache,
            "--out", art, "--workers", 0, "--no_ci",
            "--ext_csv", tmp / "train.csv", "--ext_dir", imgs, "--ext_name", "fake_external",
            "--ext_cache", tmp / "ext_cache")
        run("embed.py", "--ckpt", run_dir / "best.pt", "--splits", art / "splits.csv", "--cache_dir", cache,
            "--out", art, "--workers", 0)

        res = json.loads((art / "results.json").read_text())
        cal = json.loads((art / "calibration.json").read_text())
        curve = json.loads((art / "operating_curve.json").read_text())
        idx = np.load(art / "train_index.npz")
        assert cal["fitted_on"] == "validation" and cal["temperature"] > 0
        assert res["test"]["n"] == int((sp.split == "test").sum())
        assert res["external"] is not None and res["external_drop"] is not None
        assert len(curve["points"]) == 99
        assert set(idx["id_code"]) == set(sp[sp.split == "train"].id_code), "index must be train-only"
        assert (art / "reliability.png").exists() and (art / "abstention_test.csv").exists()
        print("\nSMOKE TEST PASSED (pipeline runs end to end; metrics on synthetic data are meaningless)")


if __name__ == "__main__":
    main()
