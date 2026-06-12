#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# update_and_push.sh — run the full data pipeline and push to GitHub
#
# Schedule: intended to run every 6 hours via cron.
#
# Behaviour: only produces stdout (and notifies) when data.json
# actually changes. Silent no-op runs = zero output = no spam.
#
# Git auth (pick ONE, set in .env):
#   A) SSH deploy key (repo-scoped, most secure)
#      SIG_DEPLOY_KEY=~/.ssh/sig-deploy
#   B) HTTPS fine-grained PAT
#      SIG_PAT_FILE=~/.github-tokens/shouldigetgas
#   C) Default SSH key (from ~/.ssh/config)
#      (leave both vars empty)
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

# Determine repo root:
# When run from ~/.hermes/scripts/ via cron, dirname "$0"/.. points to ~/.hermes (wrong).
# Fall back to the cron workdir (pwd at script start — set by cronjob config).
SCRIPT_REPO="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
if [[ -f "${SCRIPT_REPO}/backend/price_collector.py" ]]; then
    REPO="$SCRIPT_REPO"
elif [[ -f "$(pwd)/backend/price_collector.py" ]]; then
    REPO="$(pwd)"
else
    # Walk up from CWD looking for the marker file
    REPO=""
    _dir="$(pwd)"
    while [[ "$_dir" != "/" ]]; do
        if [[ -f "$_dir/backend/price_collector.py" ]]; then
            REPO="$_dir"
            break
        fi
        _dir="$(dirname "$_dir")"
    done
    if [[ -z "$REPO" ]]; then
        echo "ERROR: could not find repo root (backend/price_collector.py not found)" >&2
        exit 1
    fi
fi
cd "$REPO"

# ── Safety: only ever operate on main ─────────────────────────────
# The push step below targets a fixed branch; assert up front that we are on it
# so an accidental invocation from a feature branch can't push the wrong ref.
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "ERROR: refusing to run on branch '${CURRENT_BRANCH}' — this script only updates 'main'." >&2
    exit 1
fi

# ── Load env (API keys + optional auth config) ────────────────────
set -a
source .env 2>/dev/null || true
set +a

SIG_DEPLOY_KEY="${SIG_DEPLOY_KEY:-}"
SIG_PAT_FILE="${SIG_PAT_FILE:-}"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }

# ── Step 1: Price collection ──────────────────────────────────────
log "Running price collector…"
python backend/price_collector.py

# ── Step 2: Analytics pipeline ────────────────────────────────────
log "Running analytics pipeline…"
python backend/snapshot.py

# ── Step 3: Commit & push if changed ──────────────────────────────
if git diff --quiet -- frontend/data/data.json; then
    exit 0   # silent exit — nothing changed
fi

TIMESTAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
log "data.json changed — committing and pushing…"

git add frontend/data/data.json
git commit --no-gpg-sign -m "chore(data): auto-update gas prices and analysis - ${TIMESTAMP}"

# ── Configure git auth for this push ──────────────────────────────
PUSH_REMOTE="origin"
if [[ -n "$SIG_DEPLOY_KEY" && -f "$SIG_DEPLOY_KEY" ]]; then
    log "Using SSH deploy key: ${SIG_DEPLOY_KEY}"
    export GIT_SSH_COMMAND="ssh -i ${SIG_DEPLOY_KEY} -o IdentitiesOnly=yes"
elif [[ -n "$SIG_PAT_FILE" && -f "$SIG_PAT_FILE" ]]; then
    TOKEN="$(cat "$SIG_PAT_FILE" | tr -d '[:space:]')"
    log "Using HTTPS PAT (${#TOKEN} chars)"
    REPO_OWNER="tahmidul612"
    REPO_NAME="shouldigetgas"
    # Temporary remote so the token never appears in logs or git config
    git remote add push-tmp "https://x-access-token:${TOKEN}@github.com/${REPO_OWNER}/${REPO_NAME}.git"
    PUSH_REMOTE="push-tmp"
else
    log "Using default SSH key (from ~/.ssh/config)"
fi

# ── Push ──────────────────────────────────────────────────────────
git push "$PUSH_REMOTE" "$CURRENT_BRANCH"

# Clean up temporary PAT remote
if [[ "$PUSH_REMOTE" == "push-tmp" ]]; then
    git remote remove push-tmp
fi

log "Pushed update ${TIMESTAMP}"
