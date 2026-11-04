"""Where does Grad-CAM point? Measures how much heatmap weight sits on the retina's rim.

For each test image (model input space, after preprocessing):
  - retina mask = pixels brighter than the black surround
  - rim = retina pixels within `--rim` (fraction of the retina radius) of its edge
  - rim_share = Grad-CAM weight on the rim / weight inside the retina
  - rim_area  = rim pixels / retina pixels (what rim_share would be if the
                heatmap were spread uniformly)
  - outside_share = Grad-CAM weight outside the retina / total weight
  - peak_on_rim = the hottest heatmap pixel lies on the rim or outside the retina

A rim_share far above rim_area means the model leans on the image border (an
artefact or a dataset shortcut), not on lesions. Measurement only: nothing is
fitted. Also exports chosen images as small JPEGs for the demo (--export_ids).

Writes cam_audit.json and cam_audit.csv in --out.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from common import GRADE_LABELS, load_rgb, preprocess, retina_mask, save_json
from infer import RetinaModel


def gradcam_input_space(m: RetinaModel, img_pre: np.ndarray) -> np.ndarray:
    import torch
    from common import to_tensor_array
    x = torch.from_numpy(to_tensor_array(img_pre))[None].to(m.device)
    with torch.enable_grad():
        f = m.model.forward_features(x)
        f.retain_grad()
        lg = m.model.forward_head(f)
        m.model.zero_grad(set_to_none=True)
        lg[0, int(lg.argmax())].backward()
    g, a = f.grad[0], f.detach()[0]
    cam = torch.relu((g.mean(dim=(1, 2))[:, None, None] * a).sum(0)).cpu().numpy()
    cam = cam / cam.max() if cam.max() > 0 else cam
    return cv2.resize(cam, (img_pre.shape[1], img_pre.shape[0]), interpolation=cv2.INTER_LINEAR)


def find(img_dir, i):
    return next(p for ext in (".png", ".jpg", ".jpeg") if (p := Path(img_dir) / f"{i}{ext}").exists())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--img_dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--rim", type=float, default=0.15, help="rim width as a fraction of the retina radius")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--export_ids", default="", help="comma-separated id_codes to export as demo JPEGs")
    ap.add_argument("--export_side", type=int, default=1024)
    a = ap.parse_args()

    art, out = Path(a.artifacts), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    m = RetinaModel(art)
    df = pd.read_csv(art / "splits.csv").query("split == @a.split").reset_index(drop=True)
    if a.limit:
        df = df.head(a.limit)

    rows = []
    for k, r in enumerate(df.itertuples(), 1):
        img, _ = preprocess(load_rgb(find(a.img_dir, r.id_code)), m.size, clahe=m.clahe)
        cam = gradcam_input_space(m, img)
        mask = retina_mask(img).astype(np.uint8)
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        radius = dist.max()
        rim = (mask > 0) & (dist < a.rim * radius)
        inside = mask > 0
        total, w_in = cam.sum(), cam[inside].sum()
        py, px = np.unravel_index(cam.argmax(), cam.shape)
        rows.append({"id_code": r.id_code, "grade": int(r.diagnosis),
                     "rim_share": float(cam[rim].sum() / max(w_in, 1e-9)),
                     "rim_area": float(rim.sum() / max(inside.sum(), 1)),
                     "outside_share": float((total - w_in) / max(total, 1e-9)),
                     "peak_on_rim": bool(rim[py, px] or not inside[py, px])})
        if k % 100 == 0:
            print(f"  {k}/{len(df)}", flush=True)

    d = pd.DataFrame(rows)
    d.to_csv(out / "cam_audit.csv", index=False)
    summ = lambda x: {"n": int(len(x)), "rim_share_mean": float(x.rim_share.mean()),
                      "rim_area_mean": float(x.rim_area.mean()),
                      "rim_share_over_area": float(x.rim_share.mean() / x.rim_area.mean()),
                      "outside_share_mean": float(x.outside_share.mean()),
                      "peak_on_rim_rate": float(x.peak_on_rim.mean())}
    res = {"split": a.split, "rim_fraction_of_radius": a.rim,
           "note": "Grad-CAM for the predicted grade, in model-input space; measurement only",
           "all": summ(d), "by_true_grade": {GRADE_LABELS[g]: summ(x) for g, x in d.groupby("grade")}}
    save_json(res, out / "cam_audit.json")
    print(res["all"], flush=True)

    if a.export_ids:
        ex = out / "demo_images"
        ex.mkdir(exist_ok=True)
        for i in a.export_ids.split(","):
            im = cv2.imread(str(find(a.img_dir, i)))
            s = a.export_side / max(im.shape[:2])
            if s < 1:
                im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(ex / f"{i}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"exported {len(a.export_ids.split(','))} demo images", flush=True)


if __name__ == "__main__":
    main()
