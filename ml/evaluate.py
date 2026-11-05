"""Calibrate on validation, then score the held-out test split (and an external set) once.

Fitted on the VALIDATION split only:
  - temperature T (minimises validation NLL)
  - referable threshold on p(grade >= 2), the highest threshold whose validation
    sensitivity is >= --target_sens
  - abstention threshold on max calibrated prob, the validation quantile giving
    about --target_coverage of cases graded

Then applied unchanged to TEST (and EXTERNAL). Nothing here looks at test labels
before every parameter is fixed.

Outputs in --out:
  results.json             every reported number (the only source for RESULTS.md)
  calibration.json         T and thresholds (contract format)
  operating_curve.json     validation sensitivity/specificity vs referable threshold
  abstention_test.csv      coverage table on test (thresholds from val quantiles)
  abstention_external.csv  same for the external set (if given)
  reliability.png          reliability diagrams, before/after temperature scaling
  predictions_{split}.csv  per-image calibrated probabilities (for audits)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import cohen_kappa_score, confusion_matrix, roc_auc_score

from common import (GRADE_LABELS, NUM_CLASSES, REFERABLE_MIN_GRADE, decide, load_checkpoint, load_rgb, make_dataset,
                    preprocess, referable_prob, save_json)

COVERAGES = [1.0, 0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5]


# ------------------------------------------------------------------ inference
@torch.no_grad()
def predict_logits(model, ids, cache_dir, device, bs=32, workers=4):
    ds = make_dataset(ids, [0] * len(ids), cache_dir, train=False)
    dl = torch.utils.data.DataLoader(ds, batch_size=bs, shuffle=False, num_workers=workers)
    out = []
    for x, _ in dl:
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
            out.append(model(x.to(device)).float().cpu())
    return torch.cat(out).numpy()


def cache_external(df, img_dir, cache_dir, size, clahe):
    """Preprocess external images with the exact training preprocessing."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    keep, failed = [], {}
    for id_code in df.id_code:
        out = cache_dir / f"{id_code}.png"
        if not out.exists():
            src = next((p for ext in (".png", ".jpg", ".jpeg", ".tif", ".JPG", ".PNG")
                        if (p := Path(img_dir) / f"{id_code}{ext}").exists()), None)
            try:
                if src is None:
                    raise FileNotFoundError(id_code)
                img, _ = preprocess(load_rgb(src), size, clahe=clahe)
                cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            except Exception as e:  # noqa: BLE001
                failed[id_code] = f"{type(e).__name__}: {e}"
                continue
        keep.append(id_code)
    return df[df.id_code.isin(keep)].reset_index(drop=True), failed


# ---------------------------------------------------------------- calibration
def softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit_temperature(logits, y):
    lg, yt = torch.tensor(logits, dtype=torch.float64), torch.tensor(y)
    log_t = torch.zeros(1, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=200)

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.cross_entropy(lg / log_t.exp(), yt)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.exp().item())


def nll(probs, y):
    return float(-np.log(np.clip(probs[np.arange(len(y)), y], 1e-12, 1)).mean())


def ece(probs, y, n_bins=15):
    conf, pred = probs.max(1), probs.argmax(1)
    bins = np.linspace(0, 1, n_bins + 1)
    total = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return float(total)


def reliability_bins(probs, y, n_bins=15):
    conf, pred = probs.max(1), probs.argmax(1)
    bins = np.linspace(0, 1, n_bins + 1)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            rows.append(((lo + hi) / 2, float(conf[m].mean()), float((pred[m] == y[m]).mean()), int(m.sum())))
    return rows


# -------------------------------------------------------------- thresholds
def referable_threshold_for_sensitivity(p_ref, y_ref, target):
    """Highest threshold t with sensitivity(p_ref >= t) >= target."""
    pos = np.sort(p_ref[y_ref])[::-1]
    if len(pos) == 0:
        return 0.5
    k = int(np.ceil(target * len(pos)))  # need at least k positives at or above t
    return float(pos[min(k, len(pos)) - 1])


def binary_stats(p_ref, y_ref, t):
    pred = p_ref >= t
    tp, fn = int((pred & y_ref).sum()), int((~pred & y_ref).sum())
    tn, fp = int((~pred & ~y_ref).sum()), int((pred & ~y_ref).sum())
    return {"threshold": float(t), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "sensitivity": tp / max(tp + fn, 1), "specificity": tn / max(tn + fp, 1),
            "ppv": tp / max(tp + fp, 1), "npv": tn / max(tn + fn, 1),
            "referral_rate": float(pred.mean())}


# ------------------------------------------------------------------ metrics
def qwk(y, pred):
    if len(np.unique(np.concatenate([y, pred]))) < 2:
        return float("nan")
    return float(cohen_kappa_score(y, pred, weights="quadratic"))


def safe_auc(y_ref, p_ref):
    return float(roc_auc_score(y_ref, p_ref)) if 0 < y_ref.sum() < len(y_ref) else float("nan")


def bootstrap_ci(y, probs, t_ref, n=1000, seed=0):
    rng = np.random.default_rng(seed)
    stats = {"qwk": [], "sensitivity": [], "specificity": [], "auc": [], "accuracy": []}
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        yy, pp = y[i], probs[i]
        pr, yr = referable_prob(pp), yy >= REFERABLE_MIN_GRADE
        b = binary_stats(pr, yr, t_ref)
        stats["qwk"].append(qwk(yy, pp.argmax(1)))
        stats["sensitivity"].append(b["sensitivity"])
        stats["specificity"].append(b["specificity"])
        stats["auc"].append(safe_auc(yr, pr))
        stats["accuracy"].append(float((pp.argmax(1) == yy).mean()))
    return {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in stats.items()}


def evaluate_split(name, logits, y, cal, ci=True):
    p_raw, p_cal = softmax(logits), softmax(logits / cal["temperature"])
    pred = p_cal.argmax(1)  # temperature does not change the argmax
    conf = p_cal.max(1)
    pr, yr = referable_prob(p_cal), y >= REFERABLE_MIN_GRADE
    d = decide(p_cal, cal["abstain_threshold"], cal["referable_threshold"])
    covered = ~d["abstained"]  # same rule as serving: low confidence OR grade/referral conflict
    res = {
        "split": name,
        "n": int(len(y)),
        "class_counts": {GRADE_LABELS[k]: int((y == k).sum()) for k in range(NUM_CLASSES)},
        "grading": {
            "accuracy": float((pred == y).mean()),
            "qwk": qwk(y, pred),
            "confusion_matrix": confusion_matrix(y, pred, labels=list(range(NUM_CLASSES))).tolist(),
            "confusion_matrix_note": "rows = true grade 0..4, columns = predicted grade 0..4",
        },
        "referable": {
            "definition": "grade >= 2",
            "n_positive": int(yr.sum()),
            "auc": safe_auc(yr, pr),
            **binary_stats(pr, yr, cal["referable_threshold"]),
        },
        "calibration": {
            "ece_before": ece(p_raw, y), "ece_after": ece(p_cal, y),
            "nll_before": nll(p_raw, y), "nll_after": nll(p_cal, y),
            "ece_bins": 15,
        },
        "abstention": {
            "threshold": cal["abstain_threshold"],
            "abstention_rate": float(1 - covered.mean()),
            "n_abstained_low_confidence": int((conf < cal["abstain_threshold"]).sum()),
            "n_abstained_conflict_only": int((d["conflict"] & (conf >= cal["abstain_threshold"])).sum()),
            "n_graded": int(covered.sum()),
            "accuracy_overall": float((pred == y).mean()),
            "accuracy_graded": float((pred[covered] == y[covered]).mean()) if covered.any() else float("nan"),
            "qwk_overall": qwk(y, pred),
            "qwk_graded": qwk(y[covered], pred[covered]) if covered.sum() > 1 else float("nan"),
            "referable_sensitivity_graded": (binary_stats(pr[covered], yr[covered], cal["referable_threshold"])
                                             ["sensitivity"] if covered.any() else float("nan")),
        },
    }
    if ci:
        res["bootstrap_95ci"] = bootstrap_ci(y, p_cal, cal["referable_threshold"])
    return res, p_raw, p_cal


def coverage_table(conf_val, logits, y, temperature, referable_threshold):
    p = softmax(logits / temperature)
    pred, conf = p.argmax(1), p.max(1)
    conflict = decide(p, 0.0, referable_threshold)["conflict"]
    rows = []
    for c in COVERAGES:
        t = float(np.quantile(conf_val, 1 - c)) if c < 1 else 0.0
        m = (conf >= t) & ~conflict if c < 1 else np.ones_like(conf, dtype=bool)
        rows.append({"target_val_coverage": c, "threshold_from_val": t,
                     "abstention_rate": float(1 - m.mean()), "n_graded": int(m.sum()),
                     "accuracy_graded": float((pred[m] == y[m]).mean()) if m.any() else None,
                     "qwk_graded": qwk(y[m], pred[m]) if m.sum() > 1 else None})
    return pd.DataFrame(rows)


def gate_subset(name, ids, img_dir, logits, y, cal, thresholds_path):
    """Metrics on the images the deployed quality gate would accept (raw images, BGR)."""
    import quality  # ml/quality.py
    thr = quality.load_thresholds(thresholds_path)
    ok = []
    for i in ids:
        src = next((p for ext in (".png", ".jpg", ".jpeg", ".tif", ".JPG", ".PNG")
                    if (p := Path(img_dir) / f"{i}{ext}").exists()), None)
        img = cv2.imread(str(src)) if src else None
        ok.append(bool(img is not None and quality.check(img, thr)["ok"]))
    ok = np.array(ok)
    out = {"reject_rate": float(1 - ok.mean()), "n_passed": int(ok.sum()), "n": int(len(ok))}
    if ok.sum() > 10:
        r, _, _ = evaluate_split(f"{name} (gate-passed)", logits[ok], y[ok], cal, ci=False)
        out["passed"] = {"qwk": r["grading"]["qwk"], "accuracy": r["grading"]["accuracy"],
                         "referable_sensitivity": r["referable"]["sensitivity"],
                         "referable_specificity": r["referable"]["specificity"],
                         "referable_auc": r["referable"]["auc"],
                         "abstention_rate": r["abstention"]["abstention_rate"]}
    print(f"[{name}] quality gate rejects {out['reject_rate']:.3f}", flush=True)
    return out


def plot_reliability(panels, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(panels), figsize=(4.2 * len(panels), 4.2), squeeze=False)
    for ax, (title, probs, y) in zip(axes[0], panels):
        rows = reliability_bins(probs, y)
        ax.plot([0, 1], [0, 1], "--", color="#999", lw=1)
        if rows:
            _, c, a, n = zip(*rows)
            ax.plot(c, a, "o-", color="#0f766e")
        ax.set_title(f"{title}\nECE={ece(probs, y):.3f}", fontsize=10)
        ax.set_xlabel("confidence")
        ax.set_ylabel("accuracy")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(path, dpi=130)


def files_digest():
    h = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob("*.py")):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--splits", required=True)
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target_sens", type=float, default=0.90)
    ap.add_argument("--target_coverage", type=float, default=0.85)
    ap.add_argument("--ext_csv", default="", help="external csv with id_code,diagnosis (0..4)")
    ap.add_argument("--ext_dir", default="", help="external image folder")
    ap.add_argument("--ext_name", default="external")
    ap.add_argument("--ext_cache", default="", help="cache dir for preprocessed external images")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no_ci", action="store_true")
    ap.add_argument("--calibration", default="", help="reuse this calibration.json (fitted on val) instead of refitting")
    ap.add_argument("--quality_thresholds", default="", help="also report metrics on images the quality gate passes")
    ap.add_argument("--img_dir", default="", help="raw APTOS images (for the quality-gate subset on test)")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model, meta = load_checkpoint(args.ckpt, device)
    df = pd.read_csv(args.splits)
    va, te = df[df.split == "val"].reset_index(drop=True), df[df.split == "test"].reset_index(drop=True)

    # ---- 1. Fit everything on VALIDATION only --------------------------------
    lv = predict_logits(model, va.id_code, args.cache_dir, device, workers=args.workers)
    yv = va.diagnosis.values
    if args.calibration:
        # Reuse parameters fitted earlier on validation (e.g. adding an external set later).
        cal = json.loads(Path(args.calibration).read_text())
        assert cal.get("fitted_on") == "validation", "calibration must come from the validation split"
        temperature = cal["temperature"]
        print(f"[val] reusing calibration from {args.calibration}", flush=True)
    else:
        temperature = fit_temperature(lv, yv)
    pv = softmax(lv / temperature)
    prv, yrv = referable_prob(pv), yv >= REFERABLE_MIN_GRADE
    if not args.calibration:
        cal = {
            "temperature": temperature,
            "abstain_threshold": float(np.quantile(pv.max(1), 1 - args.target_coverage)),
            "referable_threshold": referable_threshold_for_sensitivity(prv, yrv, args.target_sens),
            "fitted_on": "validation",
            "abstain_rule": "abstain if max calibrated prob < abstain_threshold",
            "referable_rule": "referable if p2+p3+p4 >= referable_threshold",
            "target_val_coverage": args.target_coverage,
            "target_val_sensitivity": args.target_sens,
        }
    save_json(cal, out / "calibration.json")
    grid = np.round(np.linspace(0.01, 0.99, 99), 2)
    save_json({"source": "validation", "n": int(len(yv)), "n_positive": int(yrv.sum()),
               "positive_class": "referable (grade >= 2)", "default_threshold": cal["referable_threshold"],
               "mock": False,
               "points": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in binary_stats(prv, yrv, t).items()
                           if k in ("threshold", "sensitivity", "specificity", "referral_rate")} for t in grid]},
              out / "operating_curve.json")
    print(f"[val] T={temperature:.3f} abstain_thr={cal['abstain_threshold']:.3f} "
          f"referable_thr={cal['referable_threshold']:.3f}", flush=True)

    # ---- 2. Apply unchanged to TEST (measurement only, nothing fitted) -------
    val_res, pv_raw, pv_cal = evaluate_split("validation", lv, yv, cal, ci=False)
    lt = predict_logits(model, te.id_code, args.cache_dir, device, workers=args.workers)
    yt = te.diagnosis.values
    test_res, pt_raw, pt_cal = evaluate_split("test", lt, yt, cal, ci=not args.no_ci)
    coverage_table(pv.max(1), lt, yt, temperature, cal["referable_threshold"]).to_csv(
        out / "abstention_test.csv", index=False)
    if args.quality_thresholds and args.img_dir:
        test_res["quality_gate"] = gate_subset("test", te.id_code, args.img_dir, lt, yt, cal,
                                               args.quality_thresholds)
    for name, ids, y, p in (("val", va.id_code, yv, pv_cal), ("test", te.id_code, yt, pt_cal)):
        pd.DataFrame({"id_code": ids, "diagnosis": y, "pred": p.argmax(1), "confidence": p.max(1),
                      "referable_prob": referable_prob(p),
                      **{f"p{k}": p[:, k] for k in range(NUM_CLASSES)}}).to_csv(out / f"predictions_{name}.csv",
                                                                               index=False)
    panels = [("val before T", pv_raw, yv), ("val after T", pv_cal, yv),
              ("test before T", pt_raw, yt), ("test after T", pt_cal, yt)]

    # ---- 3. External set, same fixed parameters -----------------------------
    ext_res, drop = None, None
    if args.ext_csv:
        ed = pd.read_csv(args.ext_csv)
        ed, failed = cache_external(ed, args.ext_dir, Path(args.ext_cache or out / "ext_cache"),
                                    meta["img_size"], meta.get("clahe", True))
        le = predict_logits(model, ed.id_code, args.ext_cache or out / "ext_cache", device, workers=args.workers)
        ye = ed.diagnosis.values
        ext_res, pe_raw, pe_cal = evaluate_split(args.ext_name, le, ye, cal, ci=not args.no_ci)
        ext_res["n_failed_images"] = len(failed)
        coverage_table(pv.max(1), le, ye, temperature, cal["referable_threshold"]).to_csv(
            out / "abstention_external.csv", index=False)
        if args.quality_thresholds:
            ext_res["quality_gate"] = gate_subset(args.ext_name, ed.id_code, args.ext_dir, le, ye, cal,
                                                  args.quality_thresholds)
        panels.append((f"{args.ext_name} after T", pe_cal, ye))
        drop = {
            "note": "test minus external; positive = worse on external",
            "qwk": test_res["grading"]["qwk"] - ext_res["grading"]["qwk"],
            "accuracy": test_res["grading"]["accuracy"] - ext_res["grading"]["accuracy"],
            "referable_auc": test_res["referable"]["auc"] - ext_res["referable"]["auc"],
            "referable_sensitivity": test_res["referable"]["sensitivity"] - ext_res["referable"]["sensitivity"],
            "referable_specificity": test_res["referable"]["specificity"] - ext_res["referable"]["specificity"],
            "ece_after": ext_res["calibration"]["ece_after"] - test_res["calibration"]["ece_after"],
        }
    plot_reliability(panels, out / "reliability.png")

    results = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "code_digest": files_digest(),
        "model": {k: meta.get(k) for k in ("version", "arch", "img_size", "preprocess", "clahe", "epoch", "val_qwk")},
        "protocol": {
            "split": "image-level stratified group split 70/15/15 (near-duplicates grouped); "
                     "APTOS has no patient IDs, so patient-level separation is not possible",
            "fitted_on_validation": ["temperature", "referable_threshold", "abstain_threshold", "model selection"],
            "test_used_for": "measurement only, after every parameter was fixed on validation; never used "
                             "for fitting, thresholds or model selection",
            "abstain_rule": "abstain if max calibrated prob < abstain_threshold OR the grade and the "
                            "referable call disagree (contract v1.2)",
            "tta": False,
        },
        "calibration": cal,
        "validation": val_res,
        "test": test_res,
        "external": ext_res,
        "external_drop": drop,
    }
    save_json(results, out / "results.json")

    t = test_res
    print(f"[test] n={t['n']} QWK={t['grading']['qwk']:.3f} acc={t['grading']['accuracy']:.3f} "
          f"ref sens={t['referable']['sensitivity']:.3f} spec={t['referable']['specificity']:.3f} "
          f"AUC={t['referable']['auc']:.3f} ECE {t['calibration']['ece_before']:.3f}->"
          f"{t['calibration']['ece_after']:.3f} abstain={t['abstention']['abstention_rate']:.3f} "
          f"acc graded={t['abstention']['accuracy_graded']:.3f}", flush=True)
    if ext_res:
        e = ext_res
        print(f"[{args.ext_name}] n={e['n']} QWK={e['grading']['qwk']:.3f} AUC={e['referable']['auc']:.3f} "
              f"sens={e['referable']['sensitivity']:.3f} spec={e['referable']['specificity']:.3f}", flush=True)


if __name__ == "__main__":
    main()
