# Deploying Seekr

Everything needed to run Seekr on a server or a Kubernetes cluster. Start with
the two facts that determine every other choice.

## 1. The database decides the shape

Seekr's default database is **SQLite — a single file** at `/data/rip.db`. That
is fine on one machine and wrong on Kubernetes: SQLite is a file, not a server,
and two pods cannot share it. Sharing it would need ReadWriteMany storage (EFS
on AWS), and SQLite's locking is not safe over NFS. The application already
knows this — `serve` forces a single worker when it sees a SQLite URL.

**Use PostgreSQL.** One environment variable switches everything:

```
RIP_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/seekr
```

The driver is in the image, the connection pool already configures itself for
server-backed engines, and a migration script moves an existing corpus across.
This path has been tested end to end against Postgres 16: schema creation, a
full data migration, and identical ranked results on both engines.

Staying on SQLite means exactly one replica, an EBS volume, no horizontal
scaling, and downtime on every rollout — an EBS volume cannot attach to the
outgoing and incoming pod at the same time.

## 2. Authentication is off unless you turn it on

With no `RIP_API_TOKEN` the container starts happily and answers **every**
`/v1` route without credentials. Those routes return evidence-backed profiles
of identifiable people. Treat the token as mandatory, and prefer a deployment
that fails when the secret is missing over one that starts open.

The process prints which mode it is in on the third line of its log.

---

## Try it locally first

Same image, against Postgres, nothing on the host filesystem. If this works,
the application and its database configuration are correct, and anything that
fails afterwards is cluster wiring.

```bash
docker compose -f deploy/docker-compose.yml up --build
```

Then `http://localhost:8000/ui`, token `local-dev-token`. Verified: the UI
serves, `/v1` returns 401 without the token, and the app creates its own 23
tables on an empty Postgres volume.

```bash
docker compose -f deploy/docker-compose.yml down -v
```

## Moving an existing corpus to Postgres

Never copy a live `.db` file — an un-checkpointed WAL sits beside it and
copying the pieces separately produces a torn read. Take a snapshot:

```bash
python -c "import sqlite3; sqlite3.connect('rip.db').execute('VACUUM INTO ?', ('seed.db',))"
```

```bash
RIP_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/seekr \
  python backend/scripts/migrate_to_postgres.py seed.db
```

Idempotent per table, and it does not touch the source, so an interrupted run
resumes by re-running and ingestion can keep writing to SQLite while the read
API is switched over.

> `backend/scripts/` is excluded by `.dockerignore`, so this script is **not**
> in the image. Run it from a checkout.

## Kubernetes

```bash
kubectl kustomize deploy/k8s        # render and read before applying
```

| File | What it is |
|---|---|
| `deployment.yaml` | 2 replicas, probes, hardened pod, resource requests |
| `service.yaml` | ClusterIP on port 80 → container 8000 |
| `ingress.yaml` | AWS Load Balancer Controller; every account-specific value marked `REPLACE` |
| `secret.example.yaml` | Template only — **not** in `kustomization.yaml`, deliberately |
| `cronjob-nightly.yaml` | The nightly pipeline, plus a Sunday reparse |
| `poddisruptionbudget.yaml` | Keeps one replica through a node drain |
| `hpa.yaml` | CPU-based, 2–6 replicas; needs metrics-server and Postgres |

Three things to know before applying:

**The Dockerfile's `HEALTHCHECK` does nothing here.** Kubernetes ignores it —
it only works under Docker and Compose. The probes in `deployment.yaml` are
what matter. They use `GET /`, which needs no token and reads no tables, so it
reports the process rather than the data.

**Create the Secret out of band.** `secret.example.yaml` is a template with a
placeholder token, left out of `kustomization.yaml` on purpose so that
applying the directory cannot start the API wide open. The command to create
the real one is in that file's header.

**Version requirements.** `CronJob.spec.timeZone` needs Kubernetes 1.27+;
remove it on older clusters and the schedule falls back to the controller's
zone (usually UTC). The HPA uses `autoscaling/v2` (1.23+).

### Not validated against a cluster

These manifests were written by hand and rendered with `kubectl kustomize`,
which confirms they parse and that the Service, Deployment and PodDisruptionBudget
selectors all match the pod labels. They have **not** been applied to a real
API server, so field-level typos would not have been caught. Run this first:

```bash
kubectl apply -k deploy/k8s --dry-run=server
```

## What is not here

- **Registry and CI.** No pipeline builds or pushes the image; no ECR
  repository is defined.
- **TLS certificate.** The ingress references an ACM ARN that does not exist yet.
- **Backups.** RDS snapshots are a console/IaC concern, but this database is
  the entire product — nothing regenerates it.
- **Observability.** The app logs to stdout and exposes no metrics endpoint.

## Scaling note

Search has not been tested beyond ~60 people. Text matching uses
`LIKE '%term%'`, which cannot use a B-tree index — a growing corpus will need
trigram indexes or full-text search. Not a deployment blocker, but it is the
next real engineering problem and worth knowing before load arrives.
