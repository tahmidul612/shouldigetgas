#!/usr/bin/env bash
# Cron wrapper: run analytics pipeline and write data.json.
# Add to crontab:
#   0 */6 * * * /path/to/shouldigetgas/scripts/run_analytics.sh >> /var/log/shouldigetgas/analytics.log 2>&1
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
source "$REPO/.env" 2>/dev/null || true
cd "$REPO"
exec python backend/snapshot.py "$@"
