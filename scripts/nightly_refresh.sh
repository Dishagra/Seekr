#!/bin/zsh
# Nightly data refresh: re-fetch stale sources, discover + ingest new leads,
# rebuild the deploy snapshot, redeploy prod. Installed in crontab (03:00).
# Logs: ~/Library/Logs/seekr-refresh.log (override with SEEKR_LOG)
set -uo pipefail

# Resolve the repo from this script's own location so the cron entry works
# wherever the checkout lives.
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="${SEEKR_PYTHON:-$REPO/.venv/bin/python}"
VERCEL="${VERCEL_BIN:-$(command -v vercel || echo vercel)}"
LOG="${SEEKR_LOG:-$HOME/Library/Logs/seekr-refresh.log}"

cd "$REPO" || exit 1
exec >> "$LOG" 2>&1
echo "=== nightly refresh $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# 1. re-fetch sources not observed in 24h (continues past individual failures)
"$PY" -m rip.cli refresh --older-than-hours 24 || echo "refresh had failures (continuing)"

# 2. one discovery hop + a bounded lead drain (keeps growth rate-limit friendly)
LEAD_BATCH="${RIP_LEAD_BATCH:-100}"
"$PY" -m rip.cli discover || echo "discover failed (continuing)"
"$PY" -m rip.cli ingest-leads --limit "$LEAD_BATCH" || echo "lead drain had failures (continuing)"

# 2b. weekly full reparse (Sundays) — picks up parser improvements, no network
if [ "$(date +%u)" = "7" ]; then
  "$PY" -m rip.cli reparse || echo "reparse had failures (continuing)"
fi

# 3. rebuild the read-only snapshot (raw stripped, WAL checkpointed to a plain
#    journal — a WAL database cannot be opened on Vercel's read-only filesystem)
"$PY" scripts/build_snapshot.py || { echo "SNAPSHOT FAILED"; exit 1; }

# 4. redeploy production (env vars already set on the Vercel project)
"$VERCEL" deploy --prod --yes || { echo "DEPLOY FAILED"; exit 1; }

# 5. push queued change events to webhook subscribers (writes happen here, so
#    delivery happens here too — the Vercel deployment is read-only)
"$PY" -m rip.cli deliver-webhooks || echo "webhook delivery had failures"

echo "=== done $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
