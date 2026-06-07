#!/usr/bin/env bash
# Cron wrapper: collect gas prices for all regions.
# Add to crontab:
#   */30 * * * * /path/to/shouldigetgas/scripts/run_collector.sh >> /var/log/shouldigetgas/collector.log 2>&1
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
. "$REPO/.venv/bin/activate"
exec python backend/price_collector.py "$@"
