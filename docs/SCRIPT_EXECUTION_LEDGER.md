# Script Execution Ledger

- generated_at: 2026-03-14T03:01:23Z
- host: hyle.hyperstitious.org
- policy: each newly added observability script executed successfully three times

## Summary

| Script | Successful runs |
|---|---:|
| scripts/deploy_observability_fallback.sh | 3 |
| scripts/probe_live_endpoints.sh | 3 |
| scripts/setup_repo_observability.sh | 3 |
| scripts/start_repo_observability.sh | 3 |
| scripts/stop_repo_observability.sh | 3 |

## Run Index

| Timestamp (UTC) | Script | Run | Exit code |
|---|---|---:|---:|
| 2026-03-14T02:59:39Z | scripts/setup_repo_observability.sh | 1 | 0 |
| 2026-03-14T02:59:45Z | scripts/setup_repo_observability.sh | 2 | 0 |
| 2026-03-14T02:59:50Z | scripts/setup_repo_observability.sh | 3 | 0 |
| 2026-03-14T02:59:56Z | scripts/start_repo_observability.sh | 1 | 0 |
| 2026-03-14T03:00:03Z | scripts/start_repo_observability.sh | 2 | 0 |
| 2026-03-14T03:00:09Z | scripts/start_repo_observability.sh | 3 | 0 |
| 2026-03-14T03:00:15Z | scripts/probe_live_endpoints.sh | 1 | 0 |
| 2026-03-14T03:00:20Z | scripts/probe_live_endpoints.sh | 2 | 0 |
| 2026-03-14T03:00:26Z | scripts/probe_live_endpoints.sh | 3 | 0 |
| 2026-03-14T03:00:38Z | scripts/deploy_observability_fallback.sh | 1 | 0 |
| 2026-03-14T03:00:49Z | scripts/deploy_observability_fallback.sh | 2 | 0 |
| 2026-03-14T03:01:01Z | scripts/deploy_observability_fallback.sh | 3 | 0 |
| 2026-03-14T03:01:01Z | scripts/stop_repo_observability.sh | 1 | 0 |
| 2026-03-14T03:01:01Z | scripts/stop_repo_observability.sh | 2 | 0 |
| 2026-03-14T03:01:01Z | scripts/stop_repo_observability.sh | 3 | 0 |

## Key excerpts

### setup_repo_observability.sh

```text
docker daemon not accessible from this user; switching to probe-only fallback
curl: (7) Failed to connect to 127.0.0.1 port 9090 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 9171 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 1111 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 6006 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 8511 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 8522 after 0 ms: Connection refused
curl: (6) Could not resolve host: consistency-personnel-draft-ordering.trycloudflare.com
curl: (6) Could not resolve host: luther-identification-room-export.trycloudflare.com
live_endpoints_report=/home/uprootiny/backstage-server-lab/docs/LIVE_ENDPOINTS.md
# Live Endpoints

- generated_at: 2026-03-14T02:59:33Z

| Surface | URL | Status | HTTP | Latency(s) |
|---|---|---|---:|---:|
| Grafana Local | http://127.0.0.1:3000 | UP | 404 | 0.001038 |
| Prometheus Local | http://127.0.0.1:9090/-/ready | DOWN | 000 | 0.000204000 0 |
| GitHub Exporter Local | http://127.0.0.1:9171/metrics | DOWN | 000 | 0.000247000 0 |
| MLflow Local | http://127.0.0.1:1111 | DOWN | 000 | 0.000258000 0 |
| TensorBoard Local | http://127.0.0.1:6006 | DOWN | 000 | 0.000238000 0 |
| Kaggle Mashup Local | http://127.0.0.1:8511 | DOWN | 000 | 0.000216000 0 |
| RNA Bridge Local | http://127.0.0.1:19999/index.json | UP | 200 | 0.002902 |
| RNA Workbench Local | http://127.0.0.1:8522/rna_workbench.html | DOWN | 000 | 0.000268000 0 |
```

### start_repo_observability.sh

```text
docker daemon not accessible from this user; probe-only fallback
curl: (7) Failed to connect to 127.0.0.1 port 9090 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 9171 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 1111 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 6006 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 8511 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 8522 after 0 ms: Connection refused
curl: (6) Could not resolve host: consistency-personnel-draft-ordering.trycloudflare.com
curl: (6) Could not resolve host: luther-identification-room-export.trycloudflare.com
live_endpoints_report=/home/uprootiny/backstage-server-lab/docs/LIVE_ENDPOINTS.md
# Live Endpoints

- generated_at: 2026-03-14T02:59:50Z

| Surface | URL | Status | HTTP | Latency(s) |
|---|---|---|---:|---:|
| Grafana Local | http://127.0.0.1:3000 | UP | 404 | 0.001683 |
| Prometheus Local | http://127.0.0.1:9090/-/ready | DOWN | 000 | 0.000280000 0 |
| GitHub Exporter Local | http://127.0.0.1:9171/metrics | DOWN | 000 | 0.000238000 0 |
| MLflow Local | http://127.0.0.1:1111 | DOWN | 000 | 0.000444000 0 |
| TensorBoard Local | http://127.0.0.1:6006 | DOWN | 000 | 0.000476000 0 |
| Kaggle Mashup Local | http://127.0.0.1:8511 | DOWN | 000 | 0.000259000 0 |
| RNA Bridge Local | http://127.0.0.1:19999/index.json | UP | 200 | 0.003158 |
| RNA Workbench Local | http://127.0.0.1:8522/rna_workbench.html | DOWN | 000 | 0.000274000 0 |
```

### probe_live_endpoints.sh

```text
curl: (7) Failed to connect to 127.0.0.1 port 9090 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 9171 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 1111 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 6006 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 8511 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 8522 after 0 ms: Connection refused
curl: (6) Could not resolve host: consistency-personnel-draft-ordering.trycloudflare.com
curl: (6) Could not resolve host: luther-identification-room-export.trycloudflare.com
live_endpoints_report=/home/uprootiny/backstage-server-lab/docs/LIVE_ENDPOINTS.md
# Live Endpoints

- generated_at: 2026-03-14T03:00:09Z

| Surface | URL | Status | HTTP | Latency(s) |
|---|---|---|---:|---:|
| Grafana Local | http://127.0.0.1:3000 | UP | 404 | 0.001144 |
| Prometheus Local | http://127.0.0.1:9090/-/ready | DOWN | 000 | 0.000257000 0 |
| GitHub Exporter Local | http://127.0.0.1:9171/metrics | DOWN | 000 | 0.000268000 0 |
| MLflow Local | http://127.0.0.1:1111 | DOWN | 000 | 0.000264000 0 |
| TensorBoard Local | http://127.0.0.1:6006 | DOWN | 000 | 0.000277000 0 |
| Kaggle Mashup Local | http://127.0.0.1:8511 | DOWN | 000 | 0.000275000 0 |
| RNA Bridge Local | http://127.0.0.1:19999/index.json | UP | 200 | 0.003309 |
| RNA Workbench Local | http://127.0.0.1:8522/rna_workbench.html | DOWN | 000 | 0.000242000 0 |
| Grafana Remote | http://173.212.203.211:19300 | UP | 200 | 0.011537 |
```

### deploy_observability_fallback.sh

```text
deploy mode: local
docker daemon not accessible from this user; switching to probe-only fallback
curl: (7) Failed to connect to 127.0.0.1 port 9090 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 9171 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 1111 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 6006 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 8511 after 0 ms: Connection refused
curl: (7) Failed to connect to 127.0.0.1 port 8522 after 0 ms: Connection refused
curl: (6) Could not resolve host: consistency-personnel-draft-ordering.trycloudflare.com
curl: (6) Could not resolve host: luther-identification-room-export.trycloudflare.com
live_endpoints_report=/home/uprootiny/backstage-server-lab/docs/LIVE_ENDPOINTS.md
# Live Endpoints

- generated_at: 2026-03-14T03:00:26Z

| Surface | URL | Status | HTTP | Latency(s) |
|---|---|---|---:|---:|
| Grafana Local | http://127.0.0.1:3000 | UP | 404 | 0.001662 |
| Prometheus Local | http://127.0.0.1:9090/-/ready | DOWN | 000 | 0.000264000 0 |
| GitHub Exporter Local | http://127.0.0.1:9171/metrics | DOWN | 000 | 0.000235000 0 |
| MLflow Local | http://127.0.0.1:1111 | DOWN | 000 | 0.000253000 0 |
| TensorBoard Local | http://127.0.0.1:6006 | DOWN | 000 | 0.000211000 0 |
| Kaggle Mashup Local | http://127.0.0.1:8511 | DOWN | 000 | 0.000277000 0 |
| RNA Bridge Local | http://127.0.0.1:19999/index.json | UP | 200 | 0.002468 |
```

### stop_repo_observability.sh

```text
docker daemon not accessible from this user; nothing to stop
```

