#!/usr/bin/env bash
# One-command dev startup: runs backend and frontend together.
# Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

trap 'kill 0' EXIT

./scripts/start_backend.sh &
./scripts/start_frontend.sh &
wait
