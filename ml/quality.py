"""Image quality gate for colour fundus photographs.

Only needs cv2, numpy, the standard library and ml/common.py (which must sit next
to this file), so the same code runs inside the API and inside a Kaggle notebook.
Using common.crop_retina means metrics are taken on the crop the model sees.

Library use:
    thresholds = load_thresholds("quality_thresholds.json")
    result = check(bgr_image, thresholds)
    # {"ok": bool, "metrics": {...}, "reasons": [{"code": str, "message": str}]}

CLI use (Kaggle, derives thresholds from split == "train" rows only):
    python quality.py --img_dir IMAGES --splits splits.csv --out_dir OUT

This gate measures capture quality only. It says nothing about disease.

Known limit: field_coverage is the retina's share of the frame, so it catches a
retina that is small or pushed out of frame. A tight crop that fills the frame
scores high and is not caught.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from common import crop_retina

# Images are downscaled to this longest side before masking. It only bounds cost.
WORK_SIDE = 1024
# The retina crop is resized to this longest side before any metric is taken.
# Laplacian variance depends on resolution, and sources range from ~640 px to
# ~4300 px wide, so without this one threshold could not cover them all.
METRIC_SIDE = 512
# Fundus backgrounds are near-black but JPEG noise keeps them slightly above 0.
BACKGROUND_LEVEL = 10
# A blob below this share of the frame is not treated as a retina.
MIN_RETINA_FRACTION = 0.02
# Erosion as a share of the crop side. Keeps the hard retina/background edge out
# of the sharpness and contrast numbers.
RIM_FRACTION = 0.03
# Glare pixels are blown out (high value) and washed out (low saturation), which
# separates them from the normal orange-red retina.
GLARE_MIN_VALUE = 245
GLARE_MAX_SATURATION = 40

# 1st/99th percentile rather than the 2nd/98th. The train images were all graded
# by clinicians, so they are treated as gradable and the gate should only reject
# what falls outside nearly all of them. Each limit rejects about 1% of train, and
# with six limits the union is up to ~6%; the 2nd/98th would double that and start
# blocking ordinary images. Actual union rate is written to the thresholds file.
DEFAULT_LOW_PCT = 1.0
DEFAULT_HIGH_PCT = 99.0

THRESHOLD_KEYS = (
    "sharpness_min",
    "brightness_min",
    "brightness_max",
    "contrast_min",
    "coverage_min",
    "glare_max",
)
METRIC_KEYS = ("sharpness", "brightness", "contrast", "field_coverage", "glare_fraction")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".PNG", ".JPG", ".JPEG", ".TIF", ".TIFF")

# Codes and wording follow docs/CONTRACT.md ("Quality reason codes").
MESSAGES = {
    "too_dark": "Image too dark: increase illumination and retake.",
    "too_bright": "Image too bright: reduce illumination and retake.",
    "blurry": "Image is blurry: hold the camera steady, refocus and retake.",
    "low_contrast": "Contrast too low: clean the lens and retake.",
    "poor_field": "Retina not fully in frame: recentre the eye and retake.",
    "glare": "Too much glare: realign the camera to remove reflections and retake.",
}
NO_RETINA_MESSAGE = "No retina found: check that this is a fundus photo and retake."


def _to_bgr(image: np.ndarray) -> np.ndarray:
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("image must be a non-empty numpy array")
    if image.dtype != np.uint8:
        raise ValueError(f"image must be uint8, got {image.dtype}")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 1:
        return cv2.cvtColor(image[:, :, 0], cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 3:
        return image
    if image.ndim == 3 and image.shape[2] == 4:
        return np.ascontiguousarray(image[:, :, :3])
    raise ValueError(f"unsupported image shape {image.shape}")


def _resize_longest(image: np.ndarray, side: int, upscale: bool) -> np.ndarray:
    height, width = image.shape[:2]
    scale = side / max(height, width)
    if scale == 1 or (scale > 1 and not upscale):
        return image
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    return cv2.resize(image, size, interpolation=interpolation)


def retina_mask(image: np.ndarray) -> np.ndarray:
    """Filled uint8 mask (0 or 255) of the largest bright region, or all zeros."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = (gray > BACKGROUND_LEVEL).astype(np.uint8) * 255
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros(gray.shape, dtype=np.uint8)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        cv2.drawContours(mask, [largest], -1, 255, thickness=cv2.FILLED)
    return mask


def compute_metrics(image: np.ndarray) -> dict:
    """Quality metrics for one image. All values are plain floats.

    retina_found is 0.0 when no retina-sized region exists; the rest are then 0.0.
    """
    bgr = _resize_longest(_to_bgr(image), WORK_SIDE, upscale=False)
    coverage = float(np.count_nonzero(retina_mask(bgr))) / (bgr.shape[0] * bgr.shape[1])
    if coverage < MIN_RETINA_FRACTION:
        return {"retina_found": 0.0, **{key: 0.0 for key in METRIC_KEYS}, "field_coverage": coverage}

    # common.crop_retina works in RGB and pads to a square. The padding is black, so
    # retina_mask() below keeps it out of every metric.
    square, _ = crop_retina(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    crop = _resize_longest(cv2.cvtColor(square, cv2.COLOR_RGB2BGR), METRIC_SIDE, upscale=True)
    mask = retina_mask(crop)
    rim = max(3, int(RIM_FRACTION * max(crop.shape[:2]))) | 1
    # The retina touches the edge of the crop's bounding box. erode()
    # treats outside-the-array as foreground by default, which would keep that rim.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (rim, rim))
    inner = cv2.erode(mask, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0) > 0
    if not inner.any():
        inner = mask > 0

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # The green channel carries most retinal detail, so sharpness is measured there.
    laplacian = cv2.Laplacian(crop[:, :, 1], cv2.CV_64F)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    glare = (hsv[:, :, 2] >= GLARE_MIN_VALUE) & (hsv[:, :, 1] <= GLARE_MAX_SATURATION)

    return {
        "retina_found": 1.0,
        "sharpness": float(laplacian[inner].var()),
        "brightness": float(gray[inner].mean()),
        "contrast": float(gray[inner].std()),
        "field_coverage": coverage,
        "glare_fraction": float(glare[inner].mean()),
    }


def _reason(code: str, message: str | None = None) -> dict:
    return {"code": code, "message": message or MESSAGES[code]}


def check(image: np.ndarray, thresholds: dict) -> dict:
    """Run the gate. Raises ValueError for arrays that are not images."""
    missing = [key for key in THRESHOLD_KEYS if key not in thresholds]
    if missing:
        raise ValueError(f"thresholds missing keys: {missing}")

    computed = compute_metrics(image)
    metrics = {key: computed[key] for key in METRIC_KEYS}
    if not computed["retina_found"]:
        return {"ok": False, "metrics": metrics, "reasons": [_reason("poor_field", NO_RETINA_MESSAGE)]}

    failed = []
    if metrics["brightness"] < thresholds["brightness_min"]:
        failed.append("too_dark")
    if metrics["brightness"] > thresholds["brightness_max"]:
        failed.append("too_bright")
    if metrics["sharpness"] < thresholds["sharpness_min"]:
        failed.append("blurry")
    if metrics["contrast"] < thresholds["contrast_min"]:
        failed.append("low_contrast")
    if metrics["field_coverage"] < thresholds["coverage_min"]:
        failed.append("poor_field")
    if metrics["glare_fraction"] > thresholds["glare_max"]:
        failed.append("glare")
    return {"ok": not failed, "metrics": metrics, "reasons": [_reason(code) for code in failed]}


def load_thresholds(path: str | Path, allow_placeholder: bool = False) -> dict:
    """Load thresholds, refusing the placeholder file unless explicitly allowed."""
    thresholds = json.loads(Path(path).read_text())
    if not thresholds.get("derived_from_data") and not allow_placeholder:
        raise ValueError(f"{path} is not derived from data; pass allow_placeholder=True to use it")
    return thresholds


def derive_thresholds(
    rows: list[dict], low_pct: float = DEFAULT_LOW_PCT, high_pct: float = DEFAULT_HIGH_PCT
) -> dict:
    """Thresholds from rows with split == "train". Every other split is ignored."""
    train = [row for row in rows if row["split"] == "train"]
    usable = [row for row in train if float(row["retina_found"])]
    if not usable:
        raise ValueError("no usable train rows to derive thresholds from")

    def column(key: str) -> np.ndarray:
        return np.array([float(row[key]) for row in usable])

    thresholds = {
        "derived_from_data": True,
        "source": "train split only",
        "low_percentile": low_pct,
        "high_percentile": high_pct,
        "n_train_rows": len(train),
        "n_train_used": len(usable),
        "sharpness_min": float(np.percentile(column("sharpness"), low_pct)),
        "brightness_min": float(np.percentile(column("brightness"), low_pct)),
        "brightness_max": float(np.percentile(column("brightness"), high_pct)),
        "contrast_min": float(np.percentile(column("contrast"), low_pct)),
        "coverage_min": float(np.percentile(column("field_coverage"), low_pct)),
        "glare_max": float(np.percentile(column("glare_fraction"), high_pct)),
    }
    rejected = (
        (column("sharpness") < thresholds["sharpness_min"])
        | (column("brightness") < thresholds["brightness_min"])
        | (column("brightness") > thresholds["brightness_max"])
        | (column("contrast") < thresholds["contrast_min"])
        | (column("field_coverage") < thresholds["coverage_min"])
        | (column("glare_fraction") > thresholds["glare_max"])
    )
    thresholds["train_reject_rate"] = float(rejected.mean())
    return thresholds


def _find_image(img_dir: Path, id_code: str) -> Path | None:
    for suffix in ("", *IMAGE_SUFFIXES):
        candidate = img_dir / f"{id_code}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _stats_row(img_dir: Path, row: dict) -> dict:
    out = {"id_code": row["id_code"], "diagnosis": row["diagnosis"], "split": row["split"]}
    path = _find_image(img_dir, row["id_code"])
    image = cv2.imread(str(path), cv2.IMREAD_COLOR) if path else None
    if image is None:
        return {**out, "status": "missing" if path is None else "unreadable"}
    return {**out, "status": "ok", **compute_metrics(image)}


def build_stats(img_dir: Path, splits_csv: Path, workers: int) -> tuple[list[dict], list[dict]]:
    """Returns (rows with metrics, rows that could not be read)."""
    with open(splits_csv, newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"id_code", "diagnosis", "split"}
    if not rows or not required <= set(rows[0]):
        raise ValueError(f"{splits_csv} needs rows with columns {sorted(required)}")
    # cv2 releases the GIL while decoding, so threads are enough here.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda row: _stats_row(img_dir, row), rows))
    return (
        [row for row in results if row["status"] == "ok"],
        [row for row in results if row["status"] != "ok"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive quality thresholds from train-split images.")
    parser.add_argument("--img_dir", type=Path, required=True)
    parser.add_argument("--splits", type=Path, required=True, help="CSV with id_code, diagnosis, split")
    parser.add_argument("--out_dir", type=Path, default=Path("."))
    parser.add_argument("--low_pct", type=float, default=DEFAULT_LOW_PCT)
    parser.add_argument("--high_pct", type=float, default=DEFAULT_HIGH_PCT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    good, bad = build_stats(args.img_dir, args.splits, args.workers)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    columns = ["id_code", "diagnosis", "split", "status", "retina_found", *METRIC_KEYS]
    with open(args.out_dir / "quality_stats.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, restval="")
        writer.writeheader()
        writer.writerows(good + bad)

    thresholds = derive_thresholds(good, args.low_pct, args.high_pct)
    thresholds["n_unreadable_all_splits"] = len(bad)
    (args.out_dir / "quality_thresholds.json").write_text(json.dumps(thresholds, indent=2) + "\n")

    print(json.dumps(thresholds, indent=2))
    if bad:
        print(f"WARNING: {len(bad)} images missing or unreadable, e.g. {bad[0]['id_code']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
