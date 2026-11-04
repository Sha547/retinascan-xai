"""Regenerate the FAKE example payloads in docs/fixtures/ (stdlib only).

Every payload here is mock data (model.mock = true). Nothing in this folder is a
measured result. Run:  python3 docs/fixtures/_make_fixtures.py
"""
import base64
import json
import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).parent
LABELS = ["No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR"]
DISCLAIMER = ("Research prototype, not clinically validated. Final decision must be "
              "made by a qualified ophthalmologist.")
HEATMAP_NOTE = ("Grad-CAM: image regions that most influenced the predicted grade. "
                "Coarse; not lesion detection.")
MODEL = {"version": "mock-0", "mock": True, "temperature": 1.0, "abstain_threshold": 0.55,
         "referable_threshold": 0.35, "calibrated_on": "validation"}


def png_rgba(w, h, pixel):
    raw = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(w)) for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def heatmap(cx, cy, r, size=128):
    def px(x, y):
        d = math.hypot(x - cx * size, y - cy * size) / (r * size)
        v = max(0.0, 1.0 - d)
        # warm (red/yellow) at the centre, fading to transparent
        return (255, int(80 + 175 * (1 - v)), 0, int(200 * v))
    return "data:image/png;base64," + base64.b64encode(png_rgba(size, size, px)).decode()


def priority(pred):
    p = pred["referable_prob"] + 0.5 * (1 - pred["confidence"]) + (0.25 if pred["abstained"] else 0)
    return round(p, 3)


def prediction(probs):
    conf = max(probs)
    grade = probs.index(conf)
    ref = round(sum(probs[2:]), 3)
    return {"grade": grade, "grade_label": LABELS[grade], "probs": probs, "confidence": conf,
            "abstained": conf < MODEL["abstain_threshold"],
            "referable": ref >= MODEL["referable_threshold"], "referable_prob": ref}


def recommendation(pred):
    if pred is None:
        return "Image not gradable. Please retake the photo (see reasons)."
    if pred["abstained"]:
        return "Model is not confident. Routed to an ophthalmologist for review."
    if pred["referable"] and pred["grade"] >= 3:
        return "Urgent referral to an ophthalmologist is suggested."
    if pred["referable"]:
        return "Referral to an ophthalmologist is suggested."
    return "No referable DR suggested by the model. Re-screen as per local protocol."


def similar(grades, base):
    return [{"id_code": f"{base}{i}", "grade": g, "grade_label": LABELS[g],
             "distance": round(0.18 + 0.05 * i, 2), "image_url": f"/api/similar/{base}{i}.jpg"}
            for i, g in enumerate(grades)]


def case(case_id, patient, created, probs=None, quality=None, hm=None, sim=None,
         status=None, decisions=(), final_grade=None, eye="left"):
    pred = prediction(probs) if probs else None
    q = quality or {"ok": True, "metrics": {"sharpness": 182.4, "brightness": 96.1, "contrast": 41.7,
                                            "field_coverage": 0.71, "glare_fraction": 0.002},
                    "reasons": []}
    return {
        "case_id": case_id, "patient_id": patient, "eye": eye, "created_at": created,
        "status": status or ("pending" if pred else "retake"),
        "image_url": f"/api/cases/{case_id}/image",
        "quality": q, "prediction": pred, "recommendation": recommendation(pred),
        "evidence": ({"heatmap_png": hm, "heatmap_note": HEATMAP_NOTE, "similar": sim}
                     if pred else None),
        "priority": priority(pred) if pred else None,
        "final_grade": final_grade, "decisions": list(decisions),
        "model": MODEL, "disclaimer": DISCLAIMER,
    }


def summary(c):
    p = c["prediction"] or {}
    return {"case_id": c["case_id"], "patient_id": c["patient_id"], "eye": c["eye"],
            "created_at": c["created_at"], "status": c["status"], "image_url": c["image_url"],
            "quality_ok": c["quality"]["ok"], "grade": p.get("grade"),
            "grade_label": p.get("grade_label"), "confidence": p.get("confidence"),
            "abstained": p.get("abstained"), "referable": p.get("referable"),
            "priority": c["priority"], "final_grade": c["final_grade"], "mock": True}


graded = case("c_20261105_a10001", "PHC-2026-00042", "2026-11-05T10:15:00Z",
              probs=[0.03, 0.09, 0.71, 0.12, 0.05], hm=heatmap(0.45, 0.38, 0.35),
              sim=similar([2, 2, 3], "mockgraded"))
abstained = case("c_20261105_a10002", "PHC-2026-00043", "2026-11-05T10:22:00Z",
                 probs=[0.08, 0.38, 0.33, 0.14, 0.07], hm=heatmap(0.55, 0.5, 0.45),
                 sim=similar([1, 2, 1], "mockabst"), eye="right")
retake = case("c_20261105_a10003", "PHC-2026-00044", "2026-11-05T10:30:00Z",
              quality={"ok": False,
                       "metrics": {"sharpness": 21.3, "brightness": 18.7, "contrast": 9.2,
                                   "field_coverage": 0.64, "glare_fraction": 0.0},
                       "reasons": [
                           {"code": "too_dark", "message": "Image too dark: increase illumination and retake."},
                           {"code": "blurry", "message": "Image is blurry: hold the camera steady, refocus and retake."}]})
severe = case("c_20261105_a10004", "PHC-2026-00045", "2026-11-05T09:58:00Z",
              probs=[0.01, 0.02, 0.10, 0.22, 0.65], hm=heatmap(0.4, 0.45, 0.4),
              sim=similar([4, 4, 3], "mocksevere"))
healthy = case("c_20261105_a10005", "PHC-2026-00046", "2026-11-05T09:40:00Z",
               probs=[0.93, 0.05, 0.01, 0.005, 0.005], hm=heatmap(0.5, 0.5, 0.5),
               sim=similar([0, 0, 0], "mockhealthy"), eye="right")
reviewed = case("c_20261105_a10006", "PHC-2026-00047", "2026-11-05T09:20:00Z",
                probs=[0.10, 0.55, 0.25, 0.07, 0.03], hm=heatmap(0.5, 0.42, 0.4),
                sim=similar([1, 1, 2], "mockrev"), status="overridden", final_grade=2,
                decisions=[{"decision_id": 1, "case_id": "c_20261105_a10006", "action": "override",
                            "final_grade": 2, "reviewer": "Dr. Example",
                            "note": "Mock decision for UI development.",
                            "created_at": "2026-11-05T09:45:00Z"}])

pending = sorted([graded, abstained, severe, healthy], key=lambda c: (-c["priority"], c["created_at"]))

curve_points = []
for i in range(1, 60):
    t = round(i / 60, 3)
    # Smooth, obviously synthetic curve, for UI development only.
    sens = round(1 - t ** 2.2, 3)
    spec = round(min(1.0, 0.45 + 0.6 * t ** 0.7), 3)
    curve_points.append({"threshold": t, "sensitivity": sens, "specificity": spec,
                         "referral_rate": round(0.5 * sens + 0.5 * (1 - spec), 3)})

files = {
    "health.json": {"status": "ok", "contract_version": 1,
                    "model": {"version": "mock-0", "mock": True, "loaded": True}},
    "analyse_graded.json": graded,
    "analyse_abstained.json": abstained,
    "analyse_retake.json": retake,
    "case_reviewed.json": reviewed,
    "case_severe.json": severe,
    "case_healthy.json": healthy,
    "cases_pending.json": {"cases": [summary(c) for c in pending], "total": len(pending)},
    "cases_all.json": {"cases": [summary(c) for c in sorted(
        [graded, abstained, retake, severe, healthy, reviewed],
        key=lambda c: c["created_at"], reverse=True)], "total": 6},
    "operating_curve.json": {"source": "validation", "n": 0, "n_positive": 0,
                             "positive_class": "referable (grade >= 2)",
                             "default_threshold": MODEL["referable_threshold"], "mock": True,
                             "points": curve_points},
    "error_415.json": {"error": {"code": "unsupported_media_type",
                                 "message": "Upload a JPEG or PNG image."}},
}

for name, data in files.items():
    (OUT / name).write_text(json.dumps(data, indent=2) + "\n")
    print("wrote", name)
