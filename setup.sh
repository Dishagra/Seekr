#!/usr/bin/env bash
#
# Set up Seekr from a fresh clone: dependencies, web build, database, and a
# graph of people rebuilt from OpenAlex.
#
#   ./setup.sh              # 50,000 people, about 20 minutes
#   ./setup.sh 10000        # smaller and quicker, about 4 minutes
#
# Safe to re-run. It skips work that is already done, and the harvest can be
# resumed if it stops.

set -euo pipefail

PEOPLE="${1:-50000}"
DUMP="authors.jsonl"

say() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
die() { printf "\n\033[31m%s\033[0m\n" "$1" >&2; exit 1; }

command -v python3 >/dev/null || die "python3 is not installed (need 3.10 or newer)"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
  || die "python3 is older than 3.10"
command -v npm >/dev/null || die "npm is not installed (need Node 20 or newer)"

# ---------------------------------------------------------------- python --
say "Installing the backend"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -e ".[postgres]"
PY="./.venv/bin/python"

# ------------------------------------------------------------------- web --
say "Building the web interface"
( cd web && npm ci --silent && npm run build )

# --------------------------------------------------------------- secrets --
if [ ! -f .env ]; then
  say "Creating .env with a fresh API token"
  TOKEN="$($PY -c 'import secrets; print(secrets.token_urlsafe(24))')"
  cat > .env <<ENV
# The password for this instance. Without it, every /v1 route answers to
# anyone who can reach the server.
RIP_API_TOKEN=$TOKEN

# Optional, and worth having. Without it GitHub allows 60 lookups an hour
# instead of 5,000, and live search will look broken rather than slow.
# GITHUB_TOKEN=

# Optional: an email address, for better rate limits on academic data.
# OPENALEX_MAILTO=
ENV
  chmod 600 .env
  echo "    token: $TOKEN"
else
  echo "    .env already exists, leaving it alone"
fi

# -------------------------------------------------------------- database --
say "Creating the database"
$PY -m rip.cli init-db

HAVE=$($PY - <<'PYEOF'
from rip.db import SessionLocal
from rip.models import Person
from sqlalchemy import select, func
print(SessionLocal().scalar(
    select(func.count()).select_from(Person).where(Person.merged_into.is_(None))) or 0)
PYEOF
)
echo "    the graph currently holds $HAVE people"

if [ "$HAVE" -lt "$PEOPLE" ]; then
  say "Downloading $PEOPLE author records from OpenAlex"
  # works_count:>50 keeps it to people with a real publication history, which
  # is what makes the corpus useful rather than merely large
  [ -f "$DUMP" ] || $PY -m rip.cli harvest openalex \
      --out "$DUMP" --limit "$PEOPLE" --filter "works_count:>50"

  say "Loading them into the graph (this is the slow part)"
  $PY -m rip.cli bulk-ingest openalex --file "$DUMP"
else
  echo "    already have enough people, skipping the harvest"
fi

# a few well-known engineers, so the graph is not purely academic
say "Adding a handful of people from GitHub"
for who in torvalds gvanrossum yyx990803; do
  $PY -m rip.cli ingest github "$who" 2>/dev/null || echo "    skipped $who"
done

say "Done"
$PY - <<'PYEOF'
from rip.db import SessionLocal
from rip.models import Person, Evidence, SourceRecord
from sqlalchemy import select, func
s = SessionLocal()
people = s.scalar(select(func.count()).select_from(Person).where(Person.merged_into.is_(None)))
ev = s.scalar(select(func.count()).select_from(Evidence))
src = [r[0] for r in s.execute(select(SourceRecord.source).distinct())]
print(f"    {people:,} people, {ev:,} pieces of evidence, from: {', '.join(sorted(src))}")
PYEOF

cat <<'NEXT'

    Start it with:

        ./.venv/bin/python -m rip.cli serve

    Then open http://127.0.0.1:8000/ui and paste the token from .env.

NEXT
