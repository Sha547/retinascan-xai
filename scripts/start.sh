#!/usr/bin/env bash
# Start the RetinaScan XAI demo: API on :8000 and the web app on :5173.
#   scripts/start.sh            real model if artifacts/model.pt exists, otherwise mock
#   PREDICTOR=mock scripts/start.sh
#   LAN=1 scripts/start.sh      also reachable from other devices on this Wi-Fi
# The API has NO login: anyone who can reach it can see case images and post decisions.
# By default it only listens on this machine. Use LAN=1 only on a network you trust.
# Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
HOST=127.0.0.1
[ "${LAN:-0}" = "1" ] && HOST=0.0.0.0
PY="${PY:-.venv/bin/python}"
[ -x "$PY" ] || { echo "No Python venv at .venv. See README: Run it."; exit 1; }
[ -d web/node_modules ] || (cd web && npm install)

if [ -f artifacts/model.pt ]; then echo "Model: $(grep -o '"version": *"[^"]*"' artifacts/train_config.json 2>/dev/null || echo artifacts/model.pt)";
else echo "WARNING: artifacts/model.pt missing, so the API serves the MOCK predictor. Run scripts/fetch_artifacts.sh"; fi
[ -f artifacts/quality_thresholds.json ] || echo "WARNING: artifacts/quality_thresholds.json missing, so placeholder quality thresholds are used"

"$PY" -m uvicorn api.main:app --host "$HOST" --port 8000 &
API=$!
(cd web && npm run dev -- --host "$HOST") &
WEB=$!
trap 'kill $API $WEB 2>/dev/null; wait 2>/dev/null' INT TERM EXIT
for i in $(seq 1 60); do curl -sf localhost:8000/api/health >/dev/null && break; sleep 1; done
echo
echo "API:  http://localhost:8000/api/health"
if [ "$HOST" = "0.0.0.0" ]; then
  echo "App:  http://localhost:5173   (other devices on this Wi-Fi: http://$(hostname -I | awk '{print $1}'):5173)"
  echo "WARNING: LAN mode. The API has no login."
else
  echo "App:  http://localhost:5173   (this machine only; LAN=1 to share on Wi-Fi)"
fi
wait
