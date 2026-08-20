#!/usr/bin/env bash
#
# Set up Seekr from a fresh clone: dependencies, web build, database, and a
# graph of people rebuilt from OpenAlex.
#
#   ./setup.sh              # 50,000 people + 150 in full, about 35 minutes
#   ./setup.sh 10000 50     # smaller and quicker, about 10 minutes
#
# The graph is built in two passes, because that is what makes it useful:
#
#   breadth  everyone, with name, affiliation and research topics. Fast,
#            thousands per minute, but it brings no publications.
#   depth    a few hundred fetched individually, which brings their papers,
#            venues and citation counts. About six seconds each.
#
# Skip the second pass and searches still work, but dossiers have nothing to
# say about published output.
#
# Safe to re-run. It skips work that is already done, and the harvest can be
# resumed if it stops.

set -euo pipefail

PEOPLE="${1:-50000}"        # how many people to pull in (breadth)
DEEP="${2:-150}"            # how many of them to fetch in full (depth)
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

# ------------------------------------------------------------------ depth --
if [ -f "$DUMP" ] && [ "$DEEP" -gt 0 ]; then
  say "Fetching the $DEEP most published in full (about 6 seconds each)"
  $PY - "$DUMP" "$DEEP" <<'PYDEEP'
import json, subprocess, sys

dump, want = sys.argv[1], int(sys.argv[2])
rows = [json.loads(line) for line in open(dump)]
# most published first: they carry the most evidence per request, and they
# are the records a dossier looks best on
rows.sort(key=lambda r: -(r.get("works_count") or 0))
ids = [r["id"].rsplit("/", 1)[-1] for r in rows[:want]]

for n, author in enumerate(ids, 1):
    subprocess.run([sys.executable, "-m", "rip.cli", "ingest", "openalex", author],
                   capture_output=True)
    if n % 25 == 0 or n == len(ids):
        print(f"    {n}/{len(ids)}")
PYDEEP
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
from rip.models import Publication, Authorship
pubs = s.scalar(select(func.count()).select_from(Publication))
deep = s.scalar(select(func.count(func.distinct(Authorship.person_id)))) or 0
print(f"    {people:,} people, {ev:,} pieces of evidence, from: {', '.join(sorted(src))}")
print(f"    {pubs:,} publications, attached to {deep:,} of them")
PYEOF

cat <<'NEXT'

    Start it with:

        ./.venv/bin/python -m rip.cli serve

    Then open http://127.0.0.1:8000/ui and paste the token from .env.

NEXT
