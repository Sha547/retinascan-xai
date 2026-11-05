"""Record REAL model outputs for the bundled sample photos (offline demo on static hosts).

  .venv/bin/python scripts/record_samples.py [--api http://127.0.0.1:8000]

Needs the API running with the real model (`"mock": false`). Uploads every photo listed in
web/public/samples/samples.csv to /api/analyse and writes web/public/samples/recorded.json:
the exact API responses, so a site without a model (e.g. Vercel) can replay genuine outputs
of the named model version. Re-run this whenever the model or the contract changes.

Photos are IDRiD official test-set images (CC BY 4.0, see ATTRIBUTION.txt). IDRiD was never
used for training. The "degraded" sample is a synthetically darkened and blurred copy.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "web" / "public" / "samples"
LABELS = ["No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.api, timeout=120)
    health = c.get("/api/health").json()
    if health["model"]["mock"]:
        raise SystemExit("The API is serving the MOCK predictor; start it with the real model first.")

    records = []
    for row in csv.DictReader(open(SAMPLES / "samples.csv")):
        f = SAMPLES / row["file"]
        sid = f.stem
        r = c.post("/api/analyse", files={"image": (f.name, f.read_bytes(), "image/jpeg")},
                   data={"patient_id": f"SAMPLE-{row['idrid_image']}{'-DEGRADED' if row['degraded'] == '1' else ''}",
                         "eye": "unknown"})
        r.raise_for_status()
        case = r.json()
        g = int(row["official_grade"])
        records.append({
            "id": sid,
            "file": row["file"],
            "official_grade": g,
            "label": f"{row['idrid_image']}{' (degraded copy)' if row['degraded'] == '1' else ''}",
            "caption": (f"Synthetically darkened and blurred copy; official grade {g} ({LABELS[g]})"
                        if row["degraded"] == "1" else f"Official grade {g} ({LABELS[g]})"),
            "case": case,
        })
        p = case["prediction"]
        print(f"{sid:32s} official {g} -> status {case['status']:8s} "
              + (f"model {p['grade']} conf {p['confidence']:.3f} abstained {p['abstained']} referable {p['referable']}"
                 if p else "reasons " + ",".join(x["code"] for x in case["quality"]["reasons"])))

    out = {"recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "model": health["model"], "api_contract_version": health["contract_version"],
           "note": "Exact responses of the real model API for these photos. Similar-case images are "
                   "APTOS training images, which are not redistributed; only their ids, grades and "
                   "distances are kept.",
           "samples": records}
    (SAMPLES / "recorded.json").write_text(json.dumps(out) + "\n")
    print(f"wrote {SAMPLES / 'recorded.json'} ({(SAMPLES / 'recorded.json').stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
