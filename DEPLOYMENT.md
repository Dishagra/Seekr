# How to put Seekr online

Plain-language guide for the team. Every command here was tested against this
version of the code, except where it says otherwise.

---

## What this thing is

Seekr is **one app** that serves both the website and the API on **port
8000**. The whole thing — including the web interface — gets packed into a
single Docker image, so you don't build the website separately.

It needs two things to run:

1. **A database it can write to** (Postgres)
2. **A server that stays running** (not a serverless/lambda platform — those
   shut down between requests, and Seekr needs to stay up)

---

## Step 1 — Try it on your laptop first

Do this before touching any real servers. It takes about five minutes and
tells you whether everything works.

```bash
git clone https://github.com/Dishagra/Seekr.git
cd Seekr
docker compose -f deploy/docker-compose.yml up --build
```

Now open **http://localhost:8000/ui** in a browser.

It will ask for a password. Type: `local-dev-token`

If the site loads and you can search — everything works. Whatever breaks
later is a server-configuration problem, not a problem with the app.

To shut it down and delete the test data:

```bash
docker compose -f deploy/docker-compose.yml down -v
```

⚠️ Don't use this setup for the real deployment. The password is written
inside that file, which is fine for a test on your own machine and not fine
anywhere else.

---

## Step 2 — Build the image and upload it

```bash
docker build -t YOUR-REGISTRY/seekr:v1 .
docker push YOUR-REGISTRY/seekr:v1
```

Replace `YOUR-REGISTRY` with wherever you keep images (ECR, Docker Hub, etc).

Nothing private goes into the image — no passwords, no database, no personal
data. That's already handled.

---

## Step 3 — Set two passwords/settings

These two have no safe default. **The app will not be secure without them.**

**`RIP_API_TOKEN`** — the password for the whole system.
If you don't set it, **anyone can read everything without logging in.**
Generate one with:

```bash
openssl rand -hex 32
```

**`RIP_DATABASE_URL`** — where the database lives.
If you don't set it, Seekr stores data inside the server itself, and
**everything is deleted every time it restarts.**

It must look exactly like this (the `+psycopg` part matters):

```
postgresql+psycopg://username:password@your-database-host:5432/seekr
```

### Optional extras

These aren't required, but each one makes Seekr better at finding people:

- **`GITHUB_TOKEN`** — the most useful one. Takes GitHub from 60 lookups an
  hour to 5,000.
- `OPENALEX_MAILTO` — an email address; gets better rate limits for academic
  data.
- `EXA_API_KEY`, `TAVILY_API_KEY`, and a few others — paid search services.

The full list is in `deploy/k8s/secret.example.yaml`.

---

## Step 4 — Deploy to Kubernetes

First, save the passwords into the cluster:

```bash
kubectl create namespace seekr

kubectl -n seekr create secret generic seekr \
  --from-literal=RIP_API_TOKEN="$(openssl rand -hex 32)" \
  --from-literal=RIP_DATABASE_URL='postgresql+psycopg://user:pass@host:5432/seekr' \
  --from-literal=GITHUB_TOKEN='ghp_...' \
  --from-literal=OPENALEX_MAILTO='you@yourdomain.com'
```

Then point the config at your image and deploy:

```bash
cd deploy/k8s
kustomize edit set image ACCOUNT.dkr.ecr.REGION.amazonaws.com/seekr=YOUR-REGISTRY/seekr:v1
kubectl apply -k .
```

### Before you deploy — find the placeholders

There are **4 spots** with `REPLACE_ME` still in them, plus a website address
to fill in. Check them all:

```bash
grep -rn "REPLACE_ME\|REPLACE_seekr" deploy/k8s/
```

The two that matter: the **image name** (in `kustomization.yaml`) and your
**website address** (in `ingress.yaml`).

### What this creates

The app itself, a web address for it, automatic scaling when busy, and two
scheduled jobs — one nightly at 3am that refreshes data, one weekly on Sunday
at 5am.

---

## Step 5 — First start

**You don't need to set up the database tables.** Seekr creates them itself
the first time it starts — 23 tables.

A brand-new database will be empty. Add some people:

```bash
kubectl -n seekr exec deploy/seekr -- python -m rip.cli ingest github torvalds
```

Or copy an existing database across using
`backend/scripts/migrate_to_postgres.py`.

To check on things:

```bash
python -m rip.cli check-db      # is the database connected and healthy?
python -m rip.cli queue-stats   # how much work is waiting?
```

---

## Running it without Docker

If you'd rather run it directly on a server:

```bash
python -m venv .venv
.venv/bin/pip install -e ".[postgres]"
cd web && npm ci && npm run build && cd ..
.venv/bin/python -m rip.cli serve --host 0.0.0.0 --port 8000
```

Needs Python 3.10 or newer, and Node 22 to build the website.

When it starts, it tells you what database it's using, whether it can write
to it, and whether the API is unprotected — read those three lines.

---

## Two things to know before you start

**1. The image build has not been tested.**
Docker wasn't installed on the machine this was written on, so while
everything *inside* the image was tested another way, the build itself hasn't
been run. That's exactly what Step 1 checks — please do it first.

**2. PDF reports don't work inside the container.**
Seekr can show a person's full profile as a web page anywhere, and that
always works. Turning it into a PDF needs Chrome, which isn't in the image,
so that one button returns an error on the server. Fixing it means adding
Chrome to the image. The web version prints to PDF from any browser in the
meantime.

---

## If something goes wrong

| What you see | What it means |
|---|---|
| Site loads but says "invalid or missing bearer token" | Normal — type the `RIP_API_TOKEN` value into the box. |
| Everything works, but data vanishes on restart | `RIP_DATABASE_URL` isn't set, so it's using temporary storage. |
| No login prompt at all | `RIP_API_TOKEN` isn't set. **The system is open to anyone.** Fix immediately. |
| Searches find nobody | The database is empty. See Step 5. |
| GitHub searches keep failing | `GITHUB_TOKEN` isn't set — you get 60 lookups an hour without it. |
