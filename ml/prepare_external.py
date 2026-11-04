"""Turn the IDRiD grading subset into external.csv + images/ for evaluation.

    python prepare_external.py --in_dir IN --out_dir OUT

Writes OUT/external.csv (id_code, diagnosis 0 to 4) and OUT/images/<id_code><ext>.
IN is the IDRiD folder holding "B. Disease Grading" and its two label CSVs. Both
IDRiD splits are used because none of it is seen in training.

Uses the standard library only. Input is treated as untrusted: files are only
read and copied, symlinks are refused, and output names are built from validated
ids. Nothing is written until the labels and images pass every check. See
docs/EXTERNAL_DATA.md for where the expected counts come from.
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import Counter
from pathlib import Path

IMAGE_MAGIC = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".tif": (b"II*\x00", b"MM\x00*"),
    ".tiff": (b"II*\x00", b"MM\x00*"),
}
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")

# Grade counts for grades 0 to 4. A copy with different counts is not the official
# label set, so the run stops rather than producing a quietly wrong evaluation.
EXPECTED_IDRID = {
    "train": {0: 134, 1: 20, 2: 136, 3: 74, 4: 49},
    "test": {0: 34, 1: 5, 2: 32, 3: 19, 4: 13},
}


class PrepareError(Exception):
    pass


def parse_grade(value: str, context: str) -> int:
    text = (value or "").strip()
    if text not in {"0", "1", "2", "3", "4"}:
        raise PrepareError(f"{context}: grade must be 0 to 4, got {value!r}")
    return int(text)


def check_counts(actual: Counter, expected: dict, name: str) -> None:
    if dict(sorted(actual.items())) != expected:
        raise PrepareError(
            f"{name}: grade counts {dict(sorted(actual.items()))} differ from expected {expected}; "
            "this is not the official label set"
        )


def check_image(path: Path) -> None:
    if path.is_symlink():
        raise PrepareError(f"refusing symlink: {path}")
    signatures = IMAGE_MAGIC.get(path.suffix.lower())
    if signatures is None:
        raise PrepareError(f"unexpected image type: {path}")
    with open(path, "rb") as handle:
        header = handle.read(8)
    if not header.startswith(signatures):
        raise PrepareError(f"file content does not match its extension: {path}")


def read_csv(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.reader(handle) if any(cell.strip() for cell in row)]


def find_column(header: list[str], word: str, path: Path) -> int:
    matches = [index for index, name in enumerate(header) if word in name.lower()]
    if len(matches) != 1:
        raise PrepareError(f"{path}: expected one column containing {word!r}, found header {header}")
    return matches[0]


def only_one(paths: list[Path], description: str) -> Path:
    if len(paths) != 1:
        raise PrepareError(f"expected one {description}, found {len(paths)}: {paths[:3]}")
    return paths[0]


def idrid_label_csvs(in_dir: Path) -> list[Path]:
    return [path for path in in_dir.rglob("*.csv") if "Disease Grading" in path.name]


def load_idrid(in_dir: Path) -> list[tuple[str, int, Path]]:
    """IDRiD reuses names across splits (IDRiD_001 is in both), so ids carry the split."""
    labels = idrid_label_csvs(in_dir)
    if not labels:
        raise PrepareError(f"no IDRiD Disease Grading label CSVs under {in_dir}")
    items = []
    for split, csv_word, folder in (("train", "Training", "a. Training Set"), ("test", "Testing", "b. Testing Set")):
        path = only_one([p for p in labels if csv_word in p.name], f"IDRiD {csv_word} label CSV")
        image_dirs = [
            d for d in in_dir.rglob(folder) if d.is_dir() and d.parent.name == "1. Original Images"
            and any("Disease Grading" in part for part in d.parts)
        ]
        image_dir = only_one(image_dirs, f"IDRiD grading image folder {folder!r}")
        images = {p.stem: p for p in image_dir.iterdir() if p.is_file() or p.is_symlink()}

        rows = read_csv(path)
        name_col = find_column(rows[0], "image", path)
        grade_col = find_column(rows[0], "retinopathy", path)
        counts = Counter()
        for row in rows[1:]:
            name = row[name_col].strip()
            grade = parse_grade(row[grade_col], f"{path.name} {name}")
            if name not in images:
                raise PrepareError(f"no image for label {name} in {image_dir}")
            counts[grade] += 1
            items.append((f"idrid_{split}_{name}", grade, images[name]))
        check_counts(counts, EXPECTED_IDRID[split], f"IDRiD {split}")
    return items


def write_output(items: list[tuple[str, int, Path]], out_dir: Path) -> None:
    ids = [id_code for id_code, _, _ in items]
    bad = [id_code for id_code in ids if not SAFE_ID.match(id_code)]
    if bad:
        raise PrepareError(f"unsafe ids: {bad[:3]}")
    if len(set(ids)) != len(ids):
        raise PrepareError("duplicate id_code values")
    for _, _, path in items:
        check_image(path)

    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "external.csv", "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id_code", "diagnosis"])
        for id_code, grade, path in items:
            shutil.copyfile(path, images_dir / f"{id_code}{path.suffix.lower()}")
            writer.writerow([id_code, grade])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--in_dir", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        items = load_idrid(args.in_dir)
        write_output(items, args.out_dir)
    except PrepareError as error:
        print(f"ERROR: {error}")
        return 1
    counts = Counter(grade for _, grade, _ in items)
    print(f"Wrote {len(items)} images to {args.out_dir}; grades {dict(sorted(counts.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
