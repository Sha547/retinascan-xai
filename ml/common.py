"""Shared preprocessing, dataset and model code.

This is the ONLY implementation of preprocessing. Training, evaluation, the
embedding index and the backend all import it, so a served image is processed
exactly like a training image (docs/CONTRACT.md, "Preprocessing").
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import cv2
import numpy as np

GRADE_LABELS = ["No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR"]
NUM_CLASSES = 5
REFERABLE_MIN_GRADE = 2
PREPROCESS_VERSION = "v1"  # bump if crop_retina / preprocess change
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


# --------------------------------------------------------------------------- io
def load_rgb(path) -> np.ndarray:
    """Read an image file as an RGB uint8 array. Raises ValueError if unreadable."""
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"unreadable image: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def decode_rgb(data: bytes) -> np.ndarray:
    """Decode image bytes (an upload) as RGB uint8. Raises ValueError if not an image."""
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not a decodable image")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------- preprocessing
def retina_mask(img: np.ndarray, tol: int = 12) -> np.ndarray:
    """Boolean mask of pixels brighter than the black surround."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return gray > tol


def crop_retina(img: np.ndarray, tol: int = 12, min_frac: float = 0.05):
    """Crop to the retina's bounding box and pad to a centred square.

    Returns (square_rgb, box) where box = (y0, y1, x0, x1, pad_top, pad_left, side)
    maps the square back to the original image (used to align heatmaps).
    If almost nothing is brighter than `tol` (very dark or not a fundus), the
    whole image is used, so the quality gate can reject it downstream.
    """
    h, w = img.shape[:2]
    mask = retina_mask(img, tol)
    if mask.mean() < min_frac:
        y0, y1, x0, x1 = 0, h, 0, w
    else:
        ys = np.where(mask.any(axis=1))[0]
        xs = np.where(mask.any(axis=0))[0]
        y0, y1, x0, x1 = int(ys[0]), int(ys[-1]) + 1, int(xs[0]), int(xs[-1]) + 1
    crop = img[y0:y1, x0:x1]
    ch, cw = crop.shape[:2]
    side = max(ch, cw)
    pad_top, pad_left = (side - ch) // 2, (side - cw) // 2
    square = np.zeros((side, side, 3), dtype=img.dtype)
    square[pad_top:pad_top + ch, pad_left:pad_left + cw] = crop
    return square, (y0, y1, x0, x1, pad_top, pad_left, side)


def apply_clahe(img: np.ndarray, clip: float = 2.0, grid: int = 8) -> np.ndarray:
    """CLAHE on the L channel (LAB), which keeps colour while boosting local contrast."""
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid)).apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)


def preprocess(img: np.ndarray, size: int, clahe: bool = True):
    """Raw RGB -> square, resized (and optionally CLAHE) RGB uint8. Returns (img, box)."""
    square, box = crop_retina(img)
    interp = cv2.INTER_AREA if square.shape[0] > size else cv2.INTER_CUBIC
    out = cv2.resize(square, (size, size), interpolation=interp)
    if clahe:
        out = apply_clahe(out)
    return out, box


def to_tensor_array(img: np.ndarray) -> np.ndarray:
    """uint8 HxWx3 RGB -> float32 3xHxW, ImageNet-normalised (numpy; caller wraps in torch)."""
    x = img.astype(np.float32) / 255.0
    x = (x - IMAGENET_MEAN) / IMAGENET_STD
    return np.ascontiguousarray(x.transpose(2, 0, 1))


def heatmap_to_original(cam: np.ndarray, box, orig_hw) -> np.ndarray:
    """Map a heatmap computed on the preprocessed square back onto the original image.

    cam: HxW float in [0,1] on the model input. Returns orig_h x orig_w float in [0,1]
    (zero outside the retina crop).
    """
    y0, y1, x0, x1, pad_top, pad_left, side = box
    sq = cv2.resize(cam.astype(np.float32), (side, side), interpolation=cv2.INTER_LINEAR)
    ch, cw = y1 - y0, x1 - x0
    out = np.zeros(orig_hw, dtype=np.float32)
    out[y0:y1, x0:x1] = sq[pad_top:pad_top + ch, pad_left:pad_left + cw]
    return out


def dhash(img: np.ndarray, hash_size: int = 16, centre: float = 0.6) -> np.ndarray:
    """Difference hash of the retina's centre, as packed bits (hash_size**2 bits).

    Only the central `centre` fraction of the (square, preprocessed) image is
    hashed: the round retina edge on a black background is shared by every
    fundus photo and would make unrelated images look like duplicates.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
    h, w = gray.shape
    mh, mw = int(h * (1 - centre) / 2), int(w * (1 - centre) / 2)
    core = gray[mh:h - mh, mw:w - mw]
    small = cv2.resize(core, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    return np.packbits((small[:, 1:] > small[:, :-1]).flatten())


# ------------------------------------------------------------------- utilities
def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def referable_prob(probs: np.ndarray) -> np.ndarray:
    return probs[..., REFERABLE_MIN_GRADE:].sum(axis=-1)


def decide(probs: np.ndarray, abstain_threshold: float, referable_threshold: float) -> dict:
    """The single decision rule used by evaluation AND serving (docs/CONTRACT.md section 1).

    probs: (..., 5) calibrated probabilities. Returns arrays of the same leading shape:
      grade      argmax grade
      confidence max probability
      ref_prob   P(grade >= 2)
      referable  ref_prob >= referable_threshold
      conflict   the grade and the referable call disagree (grade >= 2 but not referable,
                 or grade < 2 but referable)
      abstained  confidence < abstain_threshold OR conflict: the case goes to a doctor
    Conflict was added as a safety rule (contract v1.2). It changes no threshold.
    """
    probs = np.asarray(probs)
    grade = probs.argmax(axis=-1)
    confidence = probs.max(axis=-1)
    ref_prob = referable_prob(probs)
    referable = ref_prob >= referable_threshold
    conflict = (grade >= REFERABLE_MIN_GRADE) != referable
    return {"grade": grade, "confidence": confidence, "ref_prob": ref_prob, "referable": referable,
            "conflict": conflict, "abstained": (confidence < abstain_threshold) | conflict}


def triage_priority(probs: np.ndarray, abstained) -> np.ndarray:
    """Heuristic queue order (contract v1.2): referral probability + expected severity +
    uncertainty, plus a bonus when abstained. Not clinically validated."""
    probs = np.asarray(probs)
    expected_grade = (probs * np.arange(probs.shape[-1])).sum(axis=-1)
    return (referable_prob(probs) + 0.5 * expected_grade / 4 + 0.5 * (1 - probs.max(axis=-1))
            + 0.25 * np.asarray(abstained, dtype=float))


def save_json(obj, path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, default=_json_default) + "\n")


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


# ---------------------------------------------------------------- torch parts
def build_model(arch: str, pretrained: bool = True, num_classes: int = NUM_CLASSES):
    import timm
    return timm.create_model(arch, pretrained=pretrained, num_classes=num_classes)


def load_checkpoint(path, device="cpu"):
    """Load model.pt (contract format). Returns (model in eval mode, meta dict)."""
    import torch
    ckpt = torch.load(path, map_location=device, weights_only=False)
    model = build_model(ckpt["arch"], pretrained=False, num_classes=ckpt.get("num_classes", NUM_CLASSES))
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()
    meta = {k: v for k, v in ckpt.items() if k != "state_dict"}
    return model, meta


def make_dataset(ids, labels, cache_dir, train: bool):
    """torch Dataset over preprocessed cache images (`<cache_dir>/<id_code>.png`).

    torch is imported lazily so this module can be used without it (quality gate).
    """
    import torch
    from torch.utils.data import Dataset

    class _DS(Dataset):
        def __init__(self):
            self.ids, self.labels = list(ids), list(labels)
            self.cache_dir = Path(cache_dir)

        def __len__(self):
            return len(self.ids)

        def __getitem__(self, i):
            img = cv2.cvtColor(cv2.imread(str(self.cache_dir / f"{self.ids[i]}.png")), cv2.COLOR_BGR2RGB)
            if train:
                img = augment(img)
            return torch.from_numpy(to_tensor_array(img)), int(self.labels[i])

    return _DS()


def augment(img: np.ndarray) -> np.ndarray:
    """Train-time augmentation: flips, rotation, mild scale, brightness/contrast.

    Fundus images have no canonical orientation, so full rotation is safe.
    """
    if random.random() < 0.5:
        img = img[:, ::-1]
    if random.random() < 0.5:
        img = img[::-1, :]
    h, w = img.shape[:2]
    angle = random.uniform(-180, 180)
    scale = random.uniform(0.95, 1.10)
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    img = cv2.warpAffine(np.ascontiguousarray(img), m, (w, h), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    alpha = random.uniform(0.85, 1.15)   # contrast
    beta = random.uniform(-15, 15)       # brightness
    img = np.clip(img.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)
    return img
