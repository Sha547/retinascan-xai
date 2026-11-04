import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import prepare_external as pe  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0fake"
SMALL_IDRID = {"train": {0: 2, 1: 1, 2: 1, 3: 1, 4: 1}, "test": {0: 1, 1: 1, 2: 1, 3: 1, 4: 1}}


@pytest.fixture(autouse=True)
def small_expected(monkeypatch):
    monkeypatch.setattr(pe, "EXPECTED_IDRID", SMALL_IDRID)


def expand(counts):
    return [grade for grade, count in counts.items() for _ in range(count)]


def make_idrid(root):
    """Same shape as the Kaggle mirror, including the percent-encoded outer folder."""
    base = root / "B.%20Disease%20Grading" / "B. Disease Grading"
    truth = base / "2. Groundtruths"
    truth.mkdir(parents=True)
    for split, folder, csv_name in (
        ("train", "a. Training Set", "a. IDRiD_Disease Grading_Training Labels.csv"),
        ("test", "b. Testing Set", "b. IDRiD_Disease Grading_Testing Labels.csv"),
    ):
        images = base / "1. Original Images" / folder
        images.mkdir(parents=True)
        # A decoy with the same folder names must not be picked up.
        decoy = root / "C. Localization" / "1. Original Images" / folder
        decoy.mkdir(parents=True)
        lines = ["Image name,Retinopathy grade,Risk of macular edema ,,,"]
        for index, grade in enumerate(expand(SMALL_IDRID[split]), start=1):
            name = f"IDRiD_{index:03d}"
            (images / f"{name}.jpg").write_bytes(JPEG)
            lines.append(f"{name},{grade},0,,,")
        (truth / csv_name).write_text("\n".join(lines) + "\n")
    return base


def read_external(out_dir):
    with open(out_dir / "external.csv", newline="") as handle:
        return list(csv.DictReader(handle))


def test_idrid_keeps_both_splits_despite_name_collision(tmp_path):
    make_idrid(tmp_path / "in")
    out = tmp_path / "out"
    assert pe.main(["--in_dir", str(tmp_path / "in"), "--out_dir", str(out)]) == 0
    rows = read_external(out)
    assert len(rows) == 11
    assert {"idrid_train_IDRiD_001", "idrid_test_IDRiD_001"} <= {row["id_code"] for row in rows}
    assert list(rows[0]) == ["id_code", "diagnosis"]
    assert all((out / "images" / f"{row['id_code']}.jpg").is_file() for row in rows)


def test_idrid_wrong_counts_writes_nothing(tmp_path, monkeypatch, capsys):
    make_idrid(tmp_path / "in")
    monkeypatch.setattr(pe, "EXPECTED_IDRID", {**SMALL_IDRID, "test": {0: 5, 1: 0, 2: 0, 3: 0, 4: 0}})
    out = tmp_path / "out"
    assert pe.main(["--in_dir", str(tmp_path / "in"), "--out_dir", str(out)]) == 1
    assert "not the official label set" in capsys.readouterr().out
    assert not out.exists()


def test_idrid_missing_image_fails(tmp_path, capsys):
    base = make_idrid(tmp_path / "in")
    (base / "1. Original Images" / "a. Training Set" / "IDRiD_002.jpg").unlink()
    assert pe.main(["--in_dir", str(tmp_path / "in"), "--out_dir", str(tmp_path / "out")]) == 1
    assert "no image for label IDRiD_002" in capsys.readouterr().out


def test_idrid_bad_grade_fails(tmp_path, capsys):
    base = make_idrid(tmp_path / "in")
    path = base / "2. Groundtruths" / "b. IDRiD_Disease Grading_Testing Labels.csv"
    path.write_text(path.read_text().replace("IDRiD_001,0", "IDRiD_001,7"))
    assert pe.main(["--in_dir", str(tmp_path / "in"), "--out_dir", str(tmp_path / "out")]) == 1
    assert "grade must be 0 to 4" in capsys.readouterr().out


def test_refuses_symlinked_image(tmp_path, capsys):
    base = make_idrid(tmp_path / "in")
    secret = tmp_path / "secret.jpg"
    secret.write_bytes(JPEG)
    target = base / "1. Original Images" / "a. Training Set" / "IDRiD_002.jpg"
    target.unlink()
    target.symlink_to(secret)
    out = tmp_path / "out"
    assert pe.main(["--in_dir", str(tmp_path / "in"), "--out_dir", str(out)]) == 1
    assert "refusing symlink" in capsys.readouterr().out
    assert not out.exists()


def test_refuses_content_that_is_not_an_image(tmp_path, capsys):
    base = make_idrid(tmp_path / "in")
    (base / "1. Original Images" / "a. Training Set" / "IDRiD_002.jpg").write_bytes(b"#!/bin/sh\n")
    assert pe.main(["--in_dir", str(tmp_path / "in"), "--out_dir", str(tmp_path / "out")]) == 1
    assert "does not match its extension" in capsys.readouterr().out


def test_refuses_unsafe_id(tmp_path, capsys):
    base = make_idrid(tmp_path / "in")
    images = base / "1. Original Images" / "a. Training Set"
    (images / "IDRiD_002.jpg").rename(images / "a b.jpg")
    path = base / "2. Groundtruths" / "a. IDRiD_Disease Grading_Training Labels.csv"
    path.write_text(path.read_text().replace("IDRiD_002", "a b"))
    assert pe.main(["--in_dir", str(tmp_path / "in"), "--out_dir", str(tmp_path / "out")]) == 1
    assert "unsafe ids" in capsys.readouterr().out


def test_unknown_input_fails(tmp_path, capsys):
    (tmp_path / "in").mkdir()
    assert pe.main(["--in_dir", str(tmp_path / "in"), "--out_dir", str(tmp_path / "out")]) == 1
    assert "no IDRiD Disease Grading label CSVs" in capsys.readouterr().out


def test_real_expected_counts_match_published_totals():
    # Unpatched values, read from the module source so the fixture does not hide them.
    source = pe.__file__
    namespace = {}
    text = open(source).read()
    block = text[text.index("EXPECTED_IDRID = {") : text.index("class PrepareError")]
    exec(block, namespace)
    assert sum(namespace["EXPECTED_IDRID"]["train"].values()) == 413
    assert sum(namespace["EXPECTED_IDRID"]["test"].values()) == 103
