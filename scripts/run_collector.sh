#!/usr/bin/env bash
# Cron wrapper: collect gas prices for all regions.
# Add to crontab:
#   */30 * * * * /path/to/shouldigetgas/scripts/run_collector.sh >> /var/log/shouldigetgas/collector.log 2>&1
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
PYTHON="$REPO/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: venv Python not found at $PYTHON — run 'python -m venv .venv && pip install -r backend/requirements.txt' first." >&2
    exit 1
fi
exec "$PYTHON" backend/price_collector.py "$@"
