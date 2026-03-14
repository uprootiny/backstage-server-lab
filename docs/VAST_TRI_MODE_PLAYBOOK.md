# Vast Tri-Mode Playbook (Explicit)

This playbook treats one Vast instance as:
1. A dumb Jupyter notebook runner.
2. A bespoke experiment management system.
3. A novel DevOps proving ground.

All three modes share one state layer and one event stream.

## 0. Baseline Assumptions

1. Vast instance is running and visible via CLI.
2. SSH key is attached to instance.
3. `VASTIAPIKEY` exists locally with mode `600`.
4. Repo is available at `https://github.com/uprootiny/backstage-server-lab`.

## 1. Canonical Control Plane Commands

```bash
# auth
uvx --from vastai vastai set api-key "$(tr -d '\r\n' < ~/VASTIAPIKEY)"

# status
uvx --from vastai vastai show instances --raw \
| jq '.[0] | {id,actual_status,public_ipaddr,ssh_host,ssh_port,ports}'

# direct ssh (from mapped port)
ssh -i ~/.ssh/gpu_orchestra_ed25519 -o IdentitiesOnly=yes -p 19636 root@175.155.64.231

# proxy ssh (from vast metadata)
ssh -i ~/.ssh/gpu_orchestra_ed25519 -o IdentitiesOnly=yes -p 17406 root@ssh8.vast.ai
```

## 2. Shared State Layer (Mandatory)

All modes must write to:
1. `artifacts/notebook_submission_registry.jsonl`
2. `artifacts/kaggle_parallel/ledger.jsonl`
3. `artifacts/operator_events.jsonl`
4. `artifacts/ledgers/completion_ledger.jsonl`
5. `artifacts/ledgers/release_ledger.jsonl`

Rule:
1. If an action does not emit state, it is not considered complete.

## 3. Mode A: Dumb Notebook Runner

### Intent
Fast ad-hoc execution, minimum ceremony.

### Start
```bash
# on instance
cd /workspace
mkdir -p work
cd work
jupyter lab --ip 0.0.0.0 --port 8080 --no-browser --allow-root
```

### Required Post-Run Capture
```bash
# register outputs into state layer
cd /workspace/backstage-server-lab
make submission-profile INPUT=/path/to/submission.csv
make submission-register NOTEBOOK=user/notebook INPUT=/path/to/submission.csv MARK=candidate BREADCRUMB="ad-hoc notebook run"
```

### Failure Policy
1. Kernel fails: capture traceback to `logs/notebook_failures.log`.
2. Missing python binary: use `python3` explicitly, do not rely on `python`.

## 4. Mode B: Bespoke Experiment Management System

### Intent
Turn runs into reproducible experiment fabric.

### Start
```bash
cd /workspace/backstage-server-lab
bash scripts/bootstrap.sh
bash scripts/up.sh
```

### Execute
```bash
# run plan and capture fabric state
make kaggle-parallel-init PROFILE=three NOTEBOOKS_DIR=notebooks/starters
make kaggle-parallel-dispatch WORKERS=3
make kaggle-parallel-status
make kaggle-parallel-reruns MIN_VOI=0.05 LIMIT=10
```

### Validate
```bash
labops run experiments/exp1.yaml --workers 3
labops validate --min-metric 0.70
labops graph --out artifacts/thesis_graph.json
```

### Interpretation Loop
1. Compare 2 runs in Submission Ledger.
2. Record deltas (metric/representation/provenance).
3. Link to hypothesis and VOI decision.

## 5. Mode C: Radical DevOps Foray

### Intent
Treat runtime as an engineering laboratory for deploy/recovery/observability.

### Start Observability
```bash
make obs-setup
make obs-probe
```

### Dashboard Targets
1. `observability/grafana/dashboards/rna_observatory_operations.json`
2. `observability/grafana/dashboards/rna_scoring_quality.json`

### Recovery Drills
```bash
# backup
mkdir -p /workspace/backups
tar -czf /workspace/backups/rna_$(date -u +%Y%m%dT%H%M%SZ).tgz -C /home/user/Sync/Projects rna_folding
sha256sum /workspace/backups/rna_*.tgz > /workspace/backups/SHA256SUMS

# restore test (example path)
mkdir -p /workspace/restore_test
tar -xzf /workspace/backups/<archive>.tgz -C /workspace/restore_test
```

### Deploy Contract
1. Deploy must report health endpoint status.
2. Deploy must emit completion event.
3. Failed deploy must not overwrite previous known-good artifacts.

## 6. Mode Switching Rules

1. Mode A -> B:
1. Register notebook outputs first.
1. Convert outputs to canonical records.
1. Only then dispatch orchestration jobs.
2. Mode B -> C:
1. Enable metrics export.
1. Run dashboard probes.
1. Execute backup + restore drill.
3. Mode C -> A:
1. Keep observability running.
1. Avoid changing production paths during notebook ad-hoc work.

## 7. Daily Operator Loop (Explicit)

```bash
uvx --from vastai vastai show instances --raw | jq '.[0] | {id,actual_status,ports}'
cd /workspace/backstage-server-lab
git pull
bash scripts/up.sh
make kaggle-parallel-status
make submission-list
make obs-probe
```

## 8. Weekly Reliability Loop

1. Rotate API keys/tokens.
2. Run restore drill.
3. Review failed jobs and rerun policy.
4. Review VOI frontier and top candidate runs.
5. Cut point release if stability criteria met.
