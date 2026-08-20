# Deploying Seekr

For whoever is putting this on infrastructure. Everything below was run
against this commit; where something has *not* been verified, it says so.

---

## What you are deploying

One image serving the API and the UI on **port 8000**. The React app in
`web/` is built inside the image, so the container is self-contained — you do
not build the frontend separately.

It needs a **writable database** and a **long-running process**. Most
serverless platforms give neither.

---

## 1. Local check first (5 minutes)

Prove the image before touching a cluster.

```bash
git clone https://github.com/Dishagra/Seekr.git && cd Seekr
docker compose -f deploy/docker-compose.yml up --build
```

Then open <http://localhost:8000/ui>. It will ask for a token — the compose
file sets `RIP_API_TOKEN: local-dev-token`.

This brings up Postgres 16 alongside the API and creates the schema on first
boot. If this works, the image and the database wiring are both correct, and
anything that fails later is cluster wiring rather than the application.

```bash
docker compose -f deploy/docker-compose.yml down -v   # -v also drops the data
```

**Not for production**: the credentials are in that file, which is the one
thing a real deployment must never do.

---

## 2. Build and push the image

```bash
docker build -t <REGISTRY>/seekr:$(git rev-parse --short HEAD) .
docker push  <REGISTRY>/seekr:$(git rev-parse --short HEAD)
```

Build context excludes secrets, databases and the demo film — see
`.dockerignore`. Nothing containing personal data is ever sent to the daemon.

---

## 3. Configuration

Two values have no safe default:

| Variable | Why it matters |
|---|---|
| `RIP_API_TOKEN` | Without it **every `/v1` route answers without credentials**. |
| `RIP_DATABASE_URL` | Without it the app falls back to a SQLite file inside the pod, which is empty and disappears on restart. |

Postgres URL form (the `+psycopg` driver is required):

```
postgresql+psycopg://USER:PASSWORD@HOST:5432/seekr
```

Optional, and only read if present: `GITHUB_TOKEN` (raises GitHub's limit
from 60 to 5,000 requests/hour), `OPENALEX_MAILTO`, `EXA_API_KEY`,
`TAVILY_API_KEY`, `SERPAPI_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`,
`STACKEXCHANGE_KEY`. The full list with comments is in
`deploy/k8s/secret.example.yaml`. None is required to run the service.

---

## 4. Kubernetes

Create the Secret out of band — never `kubectl apply` the template:

```bash
kubectl create namespace seekr
kubectl -n seekr create secret generic seekr \
  --from-literal=RIP_API_TOKEN="$(openssl rand -hex 32)" \
  --from-literal=RIP_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST:5432/seekr' \
  --from-literal=GITHUB_TOKEN='ghp_...' \
  --from-literal=OPENALEX_MAILTO='data@yourdomain.com'
```

Point the manifests at your image and apply:

```bash
cd deploy/k8s
kustomize edit set image ACCOUNT.dkr.ecr.REGION.amazonaws.com/seekr=<REGISTRY>/seekr:<TAG>
kubectl apply -k .
```

`REPLACE_ME` appears **4 times** across the manifests — the image tag in
`kustomization.yaml` and the hostname in `ingress.yaml` are the ones you must
set. Grep for it before applying:

```bash
grep -rn "REPLACE_ME\|REPLACE_seekr" deploy/k8s/
```

What gets created: `namespace`, `deployment`, `service` (ClusterIP :80 →
container :8000), `ingress` (ALB annotations), `hpa`,
`poddisruptionbudget`, and two `cronjob`s — a nightly refresh at 03:00 and a
weekly job at 05:00 Sunday.

The pods run as **non-root with a read-only root filesystem**. That is safe:
the application writes nothing outside the database.

Health probes hit `/`, which is unauthenticated and touches no tables, so a
pod reports ready without depending on the graph being populated.

---

## 5. First run

The schema creates itself on startup — there is no separate migration step.
A fresh database gives you a working but empty graph; populate it with:

```bash
kubectl -n seekr exec deploy/seekr -- python -m rip.cli ingest openalex A5108093963
kubectl -n seekr exec deploy/seekr -- python -m rip.cli ingest github torvalds
```

Or restore an existing graph into Postgres with
`backend/scripts/migrate_to_postgres.py`.

Useful checks:

```bash
python -m rip.cli check-db        # engine, journal mode, queue depths, credentials
python -m rip.cli queue-stats     # discovery backlog
```

---

## 6. Running it without containers

```bash
python -m venv .venv && .venv/bin/pip install -e ".[postgres]"
cd web && npm ci && npm run build && cd ..     # builds into frontend/
.venv/bin/python -m rip.cli serve --host 0.0.0.0 --port 8000
```

`serve` reads `.env` itself and prints what it is serving, whether the
database is writable, and whether the API is open. Python 3.10+; the image
uses 3.12 and Node 22.

---

## Verified, and not

Run against this commit, outside a container, because Docker was not
installed on the machine this was prepared on:

- the web stage builds from a clean `web/` and lands output where the runtime
  stage copies it from
- `pip install -e ".[postgres]"` succeeds on Python 3.12 with only
  `pyproject.toml` and `backend/` present — all the runtime stage copies
- the package then resolves the UI to `<app>/frontend`, the path the image
  puts it at
- the exact `HEALTHCHECK` command returns 0
- `/ui`, `/docs` and `/static` answer 200; `/v1` is 401 without a token and
  200 with one; the schema creates its 23 tables on a blank volume
- every command the nightly CronJob runs exists in the CLI
- all ten manifests parse

**Not verified — run step 1 before trusting it:** the image build itself,
layer caching, `COPY --from=web` across stages, the non-root UID against a
bind-mounted volume, and image size.

**One known gap:** Chrome is not in the image, so `GET
/v1/persons/{id}/dossier.pdf` answers **501** in the container. The HTML
dossier at `/v1/persons/{id}/dossier` always works and prints from a browser.
If PDFs are needed server-side, add Chromium to the runtime stage and set
`CHROME_BINARY`.
