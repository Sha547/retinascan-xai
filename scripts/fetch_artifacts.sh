#!/usr/bin/env bash
# Download the trained model and serving artifacts from the Kaggle run into artifacts/.
# Needs ~/.kaggle/kaggle.json for the account that ran the kernels (sha547).
set -euo pipefail
cd "$(dirname "$0")/.."
KERNEL="${1:-sha547/retinascan-phase2}"
KAGGLE="${KAGGLE:-.venv/bin/kaggle}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
echo "Downloading outputs of $KERNEL (about 50 MB)..."
"$KAGGLE" kernels output "$KERNEL" -p "$tmp" >/dev/null
src="$tmp/artifacts"
mkdir -p artifacts
for f in model.pt train_config.json calibration.json train_index.npz operating_curve.json thumbs.zip quality_thresholds.json splits.csv; do
  if [ -f "$src/$f" ]; then cp "$src/$f" artifacts/; echo "  got $f"; else echo "  MISSING $f"; fi
done
rm -rf artifacts/thumbs   # re-unpacked from thumbs.zip by the API on first start
echo "Done. Start with: scripts/start.sh"
