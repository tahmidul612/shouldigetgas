#!/usr/bin/env bash
# Cron wrapper: run analytics pipeline and write data.json.
# Add to crontab:
#   0 */6 * * * /path/to/shouldigetgas/scripts/run_analytics.sh >> /var/log/shouldigetgas/analytics.log 2>&1
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
PYTHON="$REPO/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: venv Python not found at $PYTHON — run 'python -m venv .venv && pip install -r backend/requirements.txt' first." >&2
    exit 1
fi
exec "$PYTHON" backend/snapshot.py "$@"
