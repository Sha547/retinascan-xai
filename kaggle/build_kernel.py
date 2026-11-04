"""Generate a self-contained Kaggle kernel (kaggle/kernel/) that embeds ml/*.py.

  python kaggle/build_kernel.py --stage smoke     # ~300 images, 2 epochs: checks the pipeline
  python kaggle/build_kernel.py --stage full      # full training run
  kaggle kernels push -p kaggle/kernel
  kaggle kernels status <user>/retinascan-<stage>
  kaggle kernels output <user>/retinascan-<stage> -p kaggle/out/<stage>

The Kaggle username comes from ~/.kaggle/kaggle.json (or $KAGGLE_USERNAME).
"""
import argparse
import base64
import io
import json
import os
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGES = {
    "smoke": {"limit": 300, "train_limit": 0, "epochs": 2, "size": 384, "bs": 16, "no_ci": True},
    "full": {"limit": 0, "train_limit": 0, "epochs": 15, "size": 512, "bs": 16, "no_ci": False},
    # Phase 2: no training. Uses the output of kernel `from_kernel` as input.
    "phase2": {"from_kernel": "retinascan-full", "ext_dataset": "", "ext_name": "IDRiD",
               "quality_cmd": []},
}
DEFAULTS = {"arch": "efficientnet_b0", "clahe": True, "lr": 3e-4, "workers": 4,
            "target_sens": 0.90, "target_coverage": 0.85}


def username():
    if os.environ.get("KAGGLE_USERNAME"):
        return os.environ["KAGGLE_USERNAME"]
    p = Path.home() / ".kaggle" / "kaggle.json"
    if not p.exists():
        raise SystemExit("~/.kaggle/kaggle.json not found: create an API token on kaggle.com (Settings -> API).")
    return json.loads(p.read_text())["username"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=STAGES, required=True)
    ap.add_argument("--set", nargs="*", default=[], help="override config, e.g. --set arch=efficientnet_b3 epochs=20")
    a = ap.parse_args()

    cfg = {**DEFAULTS, **STAGES[a.stage]}
    for kv in a.set:
        k, v = kv.split("=", 1)
        cur = cfg.get(k)
        if isinstance(cur, bool):
            cfg[k] = v.lower() in ("1", "true", "yes")
        elif isinstance(cur, list):
            cfg[k] = json.loads(v)  # e.g. quality_cmd='["--img_dir","{IMG_DIR}"]'
        elif cur is not None:
            cfg[k] = type(cur)(v)
        else:
            cfg[k] = v
    cfg.setdefault("version", f"{cfg['arch']}-{a.stage}")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in sorted((ROOT / "ml").glob("*.py")):
            tar.add(p, arcname=p.name)
    code = base64.b64encode(buf.getvalue()).decode()

    tpl_name = "phase2_template.py" if a.stage == "phase2" else "kernel_template.py"
    tpl = (ROOT / "kaggle" / tpl_name).read_text()
    script = (tpl.replace("__STAGE__", a.stage).replace("__CONFIG__", json.dumps(cfg))
              .replace("__CODE_B64__", code))
    out = ROOT / "kaggle" / "kernel"
    out.mkdir(exist_ok=True)
    (out / "run.py").write_text(script)
    slug = f"retinascan-{a.stage}"
    meta = {
        "id": f"{username()}/{slug}",
        "title": slug,
        "code_file": "run.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,  # timm downloads ImageNet weights
        "dataset_sources": [cfg["ext_dataset"]] if cfg.get("ext_dataset") else [],
        "competition_sources": ["aptos2019-blindness-detection"],
        "kernel_sources": [f"{username()}/{cfg['from_kernel']}"] if a.stage == "phase2" else [],
    }
    (out / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    print(f"built {out}/run.py ({len(script) // 1024} KB) for {meta['id']} with config {cfg}")


if __name__ == "__main__":
    main()
