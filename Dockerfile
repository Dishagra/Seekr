# Seekr — one image serving the API and the UI on port 8000.
#
# The UI is built from source here rather than copied from the committed
# bundle in frontend/, so what ships is always what web/ says it is.

# ---------------------------------------------------------------- web build --
FROM node:22-alpine AS web

WORKDIR /build

# Dependencies first: this layer is rebuilt only when the lockfile moves, so
# editing a component does not reinstall node_modules.
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
# vite.config.ts writes to ../frontend and prefixes asset URLs with /static/,
# which is exactly what the FastAPI app serves. Output lands at /frontend.
RUN npm run build


# ------------------------------------------------------------------ runtime --
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies come from pyproject.toml so there is one list, not two. The
# install is editable on purpose: rip/api.py locates the UI relative to its own
# file (parents[2]/"frontend"), so the package has to stay at /app/backend/rip
# for /ui and /static to resolve. A regular install would move it into
# site-packages and the app would look for the UI next to the Python stdlib.
COPY pyproject.toml ./
COPY backend/ ./backend/
# The postgres extra is included because the deploy target is not SQLite: a
# container that cannot open RIP_DATABASE_URL is not a deployable container.
RUN pip install -e ".[postgres]"

COPY --from=web /frontend/ ./frontend/

# SQLite lives on a volume — a container filesystem is disposable and this file
# is the graph. Four slashes: sqlite:/// + an absolute /data/rip.db.
ENV RIP_DATABASE_URL=sqlite:////data/rip.db
VOLUME ["/data"]

# Run as a normal user. The UID is fixed so a host bind-mount can be chowned to
# match: `chown -R 10001:10001 ./data` on the host before the first start.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin seekr \
 && mkdir -p /data \
 && chown -R seekr:seekr /data /app
USER seekr

EXPOSE 8000

# `/` is unauthenticated and touches no tables, so it reports the process is up
# without depending on the graph being populated. No curl in a slim image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request as u,sys; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/', timeout=4).status == 200 else 1)"]

# 0.0.0.0, not the CLI's 127.0.0.1 default — a loopback bind inside a container
# is unreachable from outside it. The schema is created on startup, so there is
# no separate init step.
CMD ["python", "-m", "rip.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
