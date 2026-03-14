# Notebook Fabric (Interactive + Reproducible)

This layer turns source repos + notebooks into runnable MLOps jobs with retries, backoff, and dataset cache hints.

## One-click flow

```bash
bash scripts/clickthrough_notebook_fabric.sh
```

This runs:
1. `scripts/pull_notebook_sources.py`
2. `scripts/build_interactive_orchestrator_notebook.py`
3. `labops kaggle-parallel-dispatch --plan artifacts/kaggle_parallel/plan.json`
4. status summary
5. rerun suggestions

## Source manifest

`catalogue/notebook_sources.yaml`

Each source defines:
- `repo_url`
- notebook discovery globs
- artifact globs
- paramset profiles

Outputs:
- `artifacts/notebook_sources/index.json`
- `artifacts/kaggle_parallel/plan.json`

## Interactive notebook

`notebooks/starters/04_interactive_pipeline_orchestrator.ipynb`

It provides button-driven controls to:
- pull repos and regenerate plan
- dispatch the plan with selected worker count

## Parallel harness behavior

`src/labops/kaggle_parallel.py`

Features:
- JSON or YAML plan loading
- configurable retries/backoff per job
- dataset URL cache attempts from plan `datasets`
- ledger events for run/job/cache lifecycle

## Known fallback tiers

- `ok`: notebook executed
- `failed`: notebook executed but returned non-zero
- `missing_notebook`: source notebook path unavailable
- `missing_executor`: nbconvert stack unavailable after auto-install attempt

This allows the run fabric to keep moving and report precise remediation needs.
