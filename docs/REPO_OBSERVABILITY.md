# Repo Observability: GitHub + Prometheus + Grafana

This stack instruments repository activity as operational telemetry and keeps it in the same runtime as your RNA research playground.

## What this gives you

- repository health metrics in real time
- PR/issue/workflow movement trends
- release cadence + contributor activity
- one-click panel access in Grafana
- consistent deployment path across local, Vast, and CI fallback tracks

## Stack

```text
GitHub API -> github_exporter.py -> Prometheus -> Grafana
```

Files:

- `observability/github_exporter.py`
- `observability/prometheus/prometheus.yml`
- `observability/grafana/provisioning/datasources/prometheus.yml`
- `observability/grafana/provisioning/dashboards/dashboards.yml`
- `observability/grafana/dashboards/backstage_repo_observability.json`
- `observability/docker-compose.yml`

## Dependency policy

- Python dependency execution is done with `uv`/`uvx`.
- Exporter container runs with `uv run --with requests --with prometheus-client`.
- Repo CLI and scripts use `.venv` managed via `uv`.

## Config

Copy `.env.example` to `.env` and fill these at minimum:

```bash
GITHUB_REPOSITORY=uprootiny/backstage-server-lab
GITHUB_TOKEN=<fine-grained token, recommended>
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<strong-password>
```

Token scopes (recommended):

- repository metadata
- issues
- pull requests
- actions

If `GITHUB_TOKEN` is omitted, the exporter still runs in anonymous mode with lower API rate limits.

## Launch tracks (fallback order)

### Track A: Local Docker (preferred)

```bash
make obs-setup
```

Equivalent:

```bash
bash scripts/setup_repo_observability.sh
```

URLs:

- Grafana: `http://127.0.0.1:3000`
- Prometheus: `http://127.0.0.1:9090`
- Exporter: `http://127.0.0.1:9171/metrics`

If Docker daemon access is unavailable for the current user, setup falls back to probe-only mode and still emits a live endpoint report (`docs/LIVE_ENDPOINTS.md`).

### Track B: Vast instance (remote shell)

On the Vast instance:

```bash
cd /workspace/backstage-server-lab
cp .env.example .env
# fill GITHUB_TOKEN/GRAFANA_ADMIN_PASSWORD
make obs-setup
```

Then expose ports in Vast:

- `3000` Grafana
- `9090` Prometheus
- `9171` exporter

### Track C: GitHub Actions fallback

Use workflow `.github/workflows/observability-smoke.yml` to run a non-interactive smoke check of exporter and Prometheus queries when local/Vast deployment is unavailable.

## Runtime operations

Bring up / down:

```bash
make obs-up
make obs-down
```

Probe endpoints and generate live URL report:

```bash
make obs-probe
```

Report output:

- `docs/LIVE_ENDPOINTS.md`

## Dashboard contents

`Backstage Repo Observability` dashboard includes:

- `github_repo_up`
- stars/forks/subscribers
- open issues/open PRs
- contributors/releases
- commits in last 24h
- workflow runs total
- workflow runs last 7d
- workflow failures last 7d
- GitHub API rate-limit remaining/reset

## Extending telemetry

Add server metrics by scraping node exporter in Prometheus:

```yaml
scrape_configs:
  - job_name: node
    static_configs:
      - targets: ["node-exporter:9100"]
```

Add RNA pipeline metrics by exporting from `labops` jobs and scraping an internal metrics endpoint.

## Common failure modes

- `github_repo_up = 0`: token invalid, API denied, or rate-limited.
- Grafana panel no-data: Prometheus scrape target mismatch or exporter down.
- stale numbers: poll interval too long (`GITHUB_EXPORTER_POLL_SECONDS`).

## Security notes

- never commit `.env`
- use fine-grained token with minimum scopes
- rotate tokens periodically
- change default Grafana admin password immediately

## Free-stack compatibility

When GPU budget is tight, keep this stack on a low-cost/free CPU host and target only GitHub + lightweight exporter.
This keeps observability available while expensive GPU jobs are paused or moved.
