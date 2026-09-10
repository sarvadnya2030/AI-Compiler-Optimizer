#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
fi

./.venv/bin/pip install -q -r requirements.txt
exec ./.venv/bin/uvicorn app.main:app --reload --port "${PORT:-8000}"
