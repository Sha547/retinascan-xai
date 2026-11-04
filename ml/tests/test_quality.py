import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import quality  # noqa: E402


def fake_fundus(size=800, radius_ratio=0.46, seed=0, center=None):
    """Orange-red disc on black with vessels, a pale optic disc and fine texture."""
    rng = np.random.default_rng(seed)
    image = np.zeros((size, size, 3), dtype=np.uint8)
    center = center or (size // 2, size // 2)
    radius = int(size * radius_ratio)
    disc = np.zeros((size, size), dtype=np.uint8)
    cv2.circle(disc, center, radius, 255, -1)

    yy, xx = np.mgrid[0:size, 0:size]
    falloff = 1 - 0.35 * np.hypot(xx - center[0], yy - center[1]) / radius
    retina = np.stack([30 * falloff, 75 * falloff, 170 * falloff], axis=2)
    retina += rng.normal(0, 5, retina.shape)
    image = np.where(disc[..., None] > 0, np.clip(retina, 0, 255), 0).astype(np.uint8)

    for _ in range(40):
        start = (center[0] + int(rng.integers(-radius, radius)), center[1] + int(rng.integers(-radius, radius)))
        end = (center[0] + int(rng.integers(-radius, radius)), center[1] + int(rng.integers(-radius, radius)))
        cv2.line(image, start, end, (15, 25, 95), int(rng.integers(1, 4)))
    cv2.circle(image, (center[0] + radius // 3, center[1]), radius // 7, (120, 170, 225), -1)
    image[disc == 0] = 0
    return image


@pytest.fixture(scope="module")
def clean():
    return fake_fundus()


@pytest.fixture(scope="module")
def thresholds(clean):
    base = quality.compute_metrics(clean)
    return {
        "sharpness_min": base["sharpness"] * 0.4,
        "brightness_min": base["brightness"] * 0.6,
        "brightness_max": base["brightness"] * 1.6,
        "contrast_min": base["contrast"] * 0.5,
        "coverage_min": base["field_coverage"] * 0.6,
        "glare_max": base["glare_fraction"] + 0.02,
    }


def codes(result):
    return {reason["code"] for reason in result["reasons"]}


def test_clean_image_passes(clean, thresholds):
    result = quality.check(clean, thresholds)
    assert result["ok"] is True
    assert result["reasons"] == []


def test_result_shape_is_json_safe(clean, thresholds):
    result = quality.check(cv2.GaussianBlur(clean, (0, 0), 8), thresholds)
    decoded = json.loads(json.dumps(result))
    assert set(decoded) == {"ok", "metrics", "reasons"}
    assert set(decoded["metrics"]) == set(quality.METRIC_KEYS)
    assert all(set(reason) == {"code", "message"} for reason in decoded["reasons"])


def test_blurry(clean, thresholds):
    result = quality.check(cv2.GaussianBlur(clean, (0, 0), 8), thresholds)
    assert not result["ok"]
    assert "blurry" in codes(result)


def test_too_dark(clean, thresholds):
    result = quality.check((clean * 0.35).astype(np.uint8), thresholds)
    assert not result["ok"]
    assert "too_dark" in codes(result)
    assert "increase illumination" in result["reasons"][0]["message"]


def test_too_bright(clean, thresholds):
    bright = np.clip(clean.astype(np.float32) * 2.5, 0, 255).astype(np.uint8)
    assert "too_bright" in codes(quality.check(bright, thresholds))


def test_low_contrast(clean, thresholds):
    mask = quality.retina_mask(clean) > 0
    flat = clean.astype(np.float32)
    mean = flat[mask].mean(axis=0)
    flat[mask] = mean + (flat[mask] - mean) * 0.2
    assert "low_contrast" in codes(quality.check(flat.astype(np.uint8), thresholds))


def test_poor_field_when_retina_is_pushed_out_of_frame(thresholds):
    shifted = fake_fundus(center=(40, 400))
    result = quality.check(shifted, thresholds)
    assert "poor_field" in codes(result)


def test_glare(clean, thresholds):
    glared = clean.copy()
    cv2.circle(glared, (300, 300), 110, (255, 255, 255), -1)
    assert "glare" in codes(quality.check(glared, thresholds))


def test_black_frame_is_poor_field(thresholds):
    result = quality.check(np.zeros((400, 400, 3), dtype=np.uint8), thresholds)
    assert result["ok"] is False
    assert codes(result) == {"poor_field"}
    assert result["reasons"][0]["message"] == quality.NO_RETINA_MESSAGE


def test_reason_codes_are_the_contract_codes():
    assert set(quality.MESSAGES) == {"too_dark", "too_bright", "blurry", "low_contrast", "poor_field", "glare"}
    assert all(message.endswith("retake.") for message in quality.MESSAGES.values())


def test_sharpness_is_comparable_across_resolutions(clean):
    large = cv2.resize(clean, (2400, 2400), interpolation=cv2.INTER_CUBIC)
    small = quality.compute_metrics(clean)["sharpness"]
    big = quality.compute_metrics(large)["sharpness"]
    assert big == pytest.approx(small, rel=0.5)


def test_rim_does_not_dominate_sharpness():
    smooth = np.zeros((800, 800, 3), dtype=np.uint8)
    cv2.circle(smooth, (400, 400), 360, (40, 80, 170), -1)
    assert quality.compute_metrics(smooth)["sharpness"] < 1


def test_crop_retina_removes_black_border(clean):
    padded = cv2.copyMakeBorder(clean, 100, 100, 300, 300, cv2.BORDER_CONSTANT)
    cropped = quality.crop_retina(padded)
    assert cropped.shape[0] < padded.shape[0]
    assert cropped.shape[1] < padded.shape[1]


@pytest.mark.parametrize("converted", ["gray", "bgra"])
def test_accepts_gray_and_alpha(clean, thresholds, converted):
    code = cv2.COLOR_BGR2GRAY if converted == "gray" else cv2.COLOR_BGR2BGRA
    assert "ok" in quality.check(cv2.cvtColor(clean, code), thresholds)


@pytest.mark.parametrize("bad", [np.zeros((0, 0, 3), np.uint8), np.zeros((8, 8, 3), np.float32), None])
def test_rejects_non_images(bad, thresholds):
    with pytest.raises(ValueError):
        quality.check(bad, thresholds)


def test_missing_threshold_key_raises(clean):
    with pytest.raises(ValueError, match="missing keys"):
        quality.check(clean, {"sharpness_min": 1})


def metric_row(split, value):
    return {
        "split": split,
        "retina_found": "1.0",
        "sharpness": value,
        "brightness": value,
        "contrast": value,
        "field_coverage": value,
        "glare_fraction": value,
    }


def test_thresholds_ignore_non_train_rows():
    train = [metric_row("train", value) for value in range(10, 111)]
    clean_result = quality.derive_thresholds(train)
    polluted = train + [metric_row("test", -1e6), metric_row("val", 1e6)]
    assert quality.derive_thresholds(polluted) == clean_result


def test_thresholds_use_requested_percentiles():
    rows = [metric_row("train", value) for value in range(0, 101)]
    result = quality.derive_thresholds(rows, low_pct=2, high_pct=98)
    assert result["sharpness_min"] == pytest.approx(2)
    assert result["glare_max"] == pytest.approx(98)
    assert result["derived_from_data"] is True


def test_thresholds_skip_train_rows_without_retina():
    rows = [metric_row("train", value) for value in range(10, 111)]
    rows.append({**metric_row("train", 0), "retina_found": "0.0"})
    result = quality.derive_thresholds(rows)
    assert result["n_train_rows"] == 102
    assert result["n_train_used"] == 101


def test_thresholds_need_train_rows():
    with pytest.raises(ValueError, match="no usable train rows"):
        quality.derive_thresholds([metric_row("test", 1)])


def test_placeholder_is_marked_and_refused_by_default():
    path = Path(quality.__file__).parent / "quality_thresholds.placeholder.json"
    assert json.loads(path.read_text())["derived_from_data"] is False
    with pytest.raises(ValueError, match="not derived from data"):
        quality.load_thresholds(path)
    loaded = quality.load_thresholds(path, allow_placeholder=True)
    assert set(quality.THRESHOLD_KEYS) <= set(loaded)


def test_cli_end_to_end(tmp_path, capsys):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    rows = []
    for index in range(6):
        split = "train" if index < 4 else "test"
        cv2.imwrite(str(img_dir / f"img{index}.png"), fake_fundus(size=300, seed=index))
        rows.append({"id_code": f"img{index}", "diagnosis": 0, "split": split})
    rows.append({"id_code": "gone", "diagnosis": 0, "split": "train"})
    splits = tmp_path / "splits.csv"
    with open(splits, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id_code", "diagnosis", "split"])
        writer.writeheader()
        writer.writerows(rows)

    out = tmp_path / "out"
    assert quality.main(["--img_dir", str(img_dir), "--splits", str(splits), "--out_dir", str(out)]) == 0

    with open(out / "quality_stats.csv", newline="") as handle:
        stats = list(csv.DictReader(handle))
    assert len(stats) == 7
    assert {row["status"] for row in stats} == {"ok", "missing"}

    derived = quality.load_thresholds(out / "quality_thresholds.json")
    assert derived["n_train_used"] == 4
    assert derived["n_unreadable_all_splits"] == 1
    assert "missing or unreadable" in capsys.readouterr().err
