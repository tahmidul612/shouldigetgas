#!/usr/bin/env bash
# Cron wrapper: run analytics pipeline and write data.json.
# Add to crontab:
#   0 */6 * * * /path/to/shouldigetgas/scripts/run_analytics.sh >> /var/log/shouldigetgas/analytics.log 2>&1
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
. "$REPO/.venv/bin/activate"
exec python backend/snapshot.py "$@"
