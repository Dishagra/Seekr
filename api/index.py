"""Vercel entrypoint: serves the read API against the bundled SQLite snapshot.

Ingestion runs locally/on a worker, not here; redeploying ships a fresh
snapshot. Set RIP_DATABASE_URL to a Postgres URL to outgrow this.
"""

import os

_here = os.path.dirname(os.path.abspath(__file__))
for candidate in (
    os.path.join(_here, "..", "data", "rip.db"),
    os.path.join(_here, "data", "rip.db"),
    "/var/task/data/rip.db",
):
    candidate = os.path.abspath(candidate)
    if os.path.exists(candidate):
        os.environ.setdefault(
            "RIP_DATABASE_URL", f"sqlite:///file:{candidate}?mode=ro&uri=true"
        )
        break

from rip.api import app  # noqa: E402, F401
