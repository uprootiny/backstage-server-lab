# Backstage Server Lab

A clone-friendly research playground for RNA ML that turns Kaggle notebooks, model outputs, and GPU runs into legible, comparable scientific artifacts.

## What This Repository Is

This is not only a training script collection.
It is a working lab runtime with five integrated surfaces:

1. **Experiment orchestration** (`labops`) for hypothesis-driven runs.
2. **Notebook/result intelligence** for profiling and registering submissions.
3. **RNA visualization surfaces** (workbench + artifact bridge).
4. **Technique recomposition tools** (minimap + composition templates).
5. **Repo observability** (GitHub exporter + Prometheus + Grafana).

## Operator Console (Live)

`kaggle-mashup` now acts as the **Research Observatory landing page** with unified tabs:

1. `Pipeline` (10-stage ingest->normalize->visualize->compare->VOI)
2. `Submission Registry` (breadcrumbed runs + compare-2 diff card)
3. `Parallel Notebooks` (batch/ledger/rerun controls)
4. `VOI Compass` (next-best-parameter guidance)
5. `Operator Log` (live service traces)
6. `Garden` (generative helix morphology map + data contract panel)

Launch:

```bash
make kaggle-mashup
```

Default URL:

```text
http://127.0.0.1:8511
```

## Notebook Showcase (Landing)

Featured starter notebook for RNA geometric generation + dataset export:

- [`notebooks/starters/02_rna_3d_training_filled.ipynb`](notebooks/starters/02_rna_3d_training_filled.ipynb)
- Executed on Vast through the common harness as `nb-filled-ok2`
- Output artifact: `artifacts/kaggle_parallel/rna_3d_training_filled_smoke.npz`

Preview illustration:

![RNA 3D training preview](docs/assets/rna_3d_training_filled_preview.png)

Integrated contest notebook (new):

- `sigmaborov/stanford-rna-3d-folding-top-1-solution` pulled into:
  - [`notebooks/kaggle/sigmaborov-top1/stanford-rna-3d-folding-top-1-solution.ipynb`](notebooks/kaggle/sigmaborov-top1/stanford-rna-3d-folding-top-1-solution.ipynb)
  - local-adapted repro notebook:
    - [`notebooks/kaggle/sigmaborov-top1/stanford-rna-3d-folding-top-1-solution.local.ipynb`](notebooks/kaggle/sigmaborov-top1/stanford-rna-3d-folding-top-1-solution.local.ipynb)
- Reproduced through `kaggle_parallel` as job `sigmaborov-local-004` (`status=ok`)
- Repro note:
  - [`docs/NOTEBOOK_REPRO_SIGMABOROV_TOP1.md`](docs/NOTEBOOK_REPRO_SIGMABOROV_TOP1.md)

## Core Idea

Treat external notebooks as instruments that can be decomposed and recombined:

```text
Kaggle notebook -> profile -> normalize -> register -> visualize -> compare -> compose -> rerun
```

This keeps methods reusable and results explainable.

## Quick Start (GPU Worker)

```bash
git clone https://github.com/uprootiny/backstage-server-lab.git backstage-server-lab
cd backstage-server-lab
bash scripts/bootstrap.sh
make up
make sanity
```

Single-command clone/bootstrap:

```bash
bash scripts/vast_clone_bootstrap.sh https://github.com/uprootiny/backstage-server-lab.git /workspace/backstage-server-lab
```

## Methodical Reliability Loop

For reliable, constraint-aware MLOps (doctor first, then runs):

```bash
cd /workspace/backstage-server-lab

# 1) Reality check (+ optional auto-heal)
AUTO_HEAL=1 bash scripts/doctor_harness.sh

# 2) Algorithmic composition + coherence checks
bash scripts/integration_coherence_checks.sh

# 3) Dispatch several dozen full pipeline runs
WORKERS=4 JOBS=36 TIMEOUT_MIN=35 bash scripts/dispatch_rna_bulk.sh

# 4) Live teardown of top Kaggle RNA notebooks
TOP_N=12 bash scripts/teardown_kaggle_rna_top12.sh
```

Detailed instructions:
- `docs/MEANINGFUL_RESULTS_RUNBOOK.md`
- `docs/FOOLPROOF_WALKTHROUGH.md`
- `docs/ENGINEERING_MEMO_ALGO_COMPOSITION.md`

## Daily Operations

```bash
cd backstage-server-lab
git pull
make up
make kaggle-minimap
make technique-compose IDS=tbm_ensemble,recycling_refinement,confidence_calibration
labops run artifacts/technique_compositions/composed_experiment.yaml --workers 3
make obs-probe
```

## Live URL Surfaces

### Local defaults

- MLflow: `http://127.0.0.1:1111`
- TensorBoard: `http://127.0.0.1:6006`
- Kaggle Mashup: `http://127.0.0.1:8511`
- RNA Artifact Bridge index: `http://127.0.0.1:19999/index.json`
- RNA Workbench: `http://127.0.0.1:8522/rna_workbench.html`
- Grafana: `http://127.0.0.1:3000`
- Prometheus: `http://127.0.0.1:9090`
- GitHub exporter metrics: `http://127.0.0.1:9171/metrics`

### Probed remote surfaces (example)

- MetaOps Grafana: `http://173.212.203.211:19300`
- Vast Jupyter port: `https://175.155.64.231:19808`
- Vast portal tunnel: `https://broadband-petroleum-camera-clear.trycloudflare.com/#/apps`
- Vast Jupyter tunnel: `https://alignment-vacations-abilities-conclusion.trycloudflare.com`
- Vast TensorBoard tunnel: `https://consistency-personnel-draft-ordering.trycloudflare.com`
- Vast Syncthing tunnel: `https://luther-identification-room-export.trycloudflare.com`

Generate a fresh live status report:

```bash
make obs-probe
```

Output:

- `docs/LIVE_ENDPOINTS.md`

## Observability (GitHub -> Prometheus -> Grafana)

Bring up stack:

```bash
make obs-setup
```

Stop stack:

```bash
make obs-down
```

Includes provisioned dashboard:

- `observability/grafana/dashboards/backstage_repo_observability.json`

Detailed runbook:

- `docs/REPO_OBSERVABILITY.md`

### Fallback deployment tracks

Use this if local path is unavailable:

```bash
bash scripts/deploy_observability_fallback.sh auto
```

Modes:

- `local` (docker compose on current machine)
- `vast` (sync + deploy on remote Vast host via `VAST_HOST`)
- `actions` (GitHub Actions smoke fallback)

## Validation Bench (Hypothesis-Driven)

Run a bench:

```bash
bash scripts/run_validation_bench.sh hypothesis-demo
```

Core commands:

```bash
labops formulate --hypothesis-id h1 --statement "..." --question "..." --voi-prior 0.7
labops run-bench --hypothesis-id h1 --config configs/validation_bench.yaml --workers 3
labops validate --min-metric 0.70
labops graph --out artifacts/thesis_graph.json
```

## Kaggle Notebook Mass Study + Technique Recomposition

Build minimap:

```bash
make kaggle-minimap
```

View techniques:

```bash
make technique-list
```

Compose known tricks into an executable plan:

```bash
make technique-compose IDS=tbm_ensemble,pairwise_distogram_head,recycling_refinement,confidence_calibration,family_dropout_validation
```

Outputs:

- `artifacts/kaggle_rna_notebooks_minimap.json`
- `docs/KAGGLE_RNA_NOTEBOOK_MINIMAP.md`
- `artifacts/technique_compositions/latest.yaml`
- `artifacts/technique_compositions/composed_experiment.yaml`

## Submission Intelligence Layer

Profile a submission format:

```bash
make submission-profile INPUT=/path/to/submission.csv
```

Register a notebook submission with breadcrumbs/marking:

```bash
make submission-register NOTEBOOK=user/notebook INPUT=/path/to/submission.csv MARK=review BREADCRUMB="candidate for ensemble+recycling"
```

List registry:

```bash
make submission-list
```

This keeps a durable trail at:

- `artifacts/notebook_submission_registry.jsonl`

Parallel execution loop:

```bash
make kaggle-parallel-init PROFILE=three NOTEBOOKS_DIR=notebooks/starters
make kaggle-parallel-dispatch WORKERS=3
make kaggle-parallel-status
make kaggle-parallel-reruns MIN_VOI=0.05 LIMIT=10
```

<<<<<<< HEAD
=======
Technique-matrix baselines (technique recombination + parameter perturbations + validation loop):

```bash
# plan only (inspect first)
make rna-technique-matrix-plan MAX_JOBS=20

# run matrix + validate in one pass
make rna-technique-matrix MAX_JOBS=20 WORKERS=3

# optional: force heavy techniques onto a faster notebook during smoke runs
make rna-technique-matrix MAX_JOBS=9 WORKERS=2 \
  NOTEBOOK_OVERRIDES='high_score_pragmatic=notebooks/starters/03_rna_eval_workbench_bridge.ipynb'

# regenerate validation report for a specific run id
make rna-technique-validate RUN_ID=kaggle-parallel-20260314T174604Z
```

Outputs:
- `artifacts/kaggle_parallel/plan_rna_technique_matrix.json`
- `artifacts/kaggle_parallel/rna_technique_matrix_manifest.json`
- `reports/rna_technique_matrix_validation.json`
- `docs/RNA_TECHNIQUE_MATRIX_VALIDATION.md`

>>>>>>> origin/main
Interactive/common harness for external repos + paramsets:

```bash
make notebook-pull
make notebook-interactive
make notebook-clickthrough
```

Outputs:
- `artifacts/notebook_sources/index.json`
- `artifacts/kaggle_parallel/plan.json`
- `artifacts/kaggle_parallel/ledger.jsonl`

Extract any notebook into a standalone pipeline contract:

```bash
make notebook-extract NOTEBOOK=notebooks/starters/02_rna_3d_training_filled.ipynb
```

Outputs:
- `artifacts/notebook_pipelines/<notebook-stem>/manifest.json`
- `artifacts/notebook_pipelines/<notebook-stem>/pipeline.yaml`
- `artifacts/notebook_pipelines/<notebook-stem>/run.sh`

## RNA Workbench + Bridge

Start artifact bridge:

```bash
make rna-bridge
```

Start viewer:

```bash
make rna-workbench
```

Register an existing PDB prediction quickly:

```bash
make rna-register PDB=/path/to/prediction.pdb RUN_ID=exp42 SEQUENCE=AUGC MODEL=baseline-v1
```

Universal ingest (pdb/csv/json/npy/npz):

```bash
make rna-ingest INPUT=/path/result.csv RUN_ID=exp42 SEQUENCE=AUGCUA MODEL=my-model
```

## Reading Tracks

- RNA playground system design: `docs/READING_TRACK_RNA_PLAYGROUND.md`
- Validation bench details: `docs/MLOPS_VALIDATION_BENCH.md`
- Kaggle RNA catalogue notes: `docs/KAGGLE_RNA_CATALOGUE.md`
- Vast worker operations: `docs/GPU_WORKER_OPERATIONS.md`
- Vast tri-mode operations: `docs/VAST_TRI_MODE_PLAYBOOK.md`
- Vast instance operating model: `docs/VAST_INSTANCE_OPERATING_MODEL.md`
- Repo observability runbook: `docs/REPO_OBSERVABILITY.md`
- Dashboard layouts: `docs/DASHBOARD_LAYOUTS.md`
- Metrics catalog: `docs/METRICS_CATALOG.md`
- Scoring model: `docs/SCORING_MODEL.md`
- Completion ledgers: `docs/COMPLETION_LEDGERS.md`
- Multi-perspective roadmaps: `docs/ROADMAP_PERSPECTIVES.md`
- 30-day execution roadmap: `docs/ROADMAP_30D_EXECUTION.md`
- RNA research summaries: `docs/RNA_RESEARCH_SUMMARIES.md`
- Script execution evidence: `docs/SCRIPT_EXECUTION_LEDGER.md`

## Dependency Policy

- Python runtime and package execution should use `uv`/`uvx` consistently.
- Repo commands assume `.venv` created via `uv venv` and hydrated with `uv pip`.
- Exporter container also uses `uv run` to avoid mixed package managers.

<<<<<<< HEAD
=======
## CI Instrumentation

Generate safe (presence-only) CI token/secret and Vast CLI instrumentation reports:

```bash
make ci-secrets-instrument
make ci-vast-instrument
```

Automated workflow:
- `.github/workflows/ci-instrumentation.yml`

>>>>>>> origin/main
## Layout

- `src/labops/` experiment + ingestion + CLI
- `scripts/` operations, launchers, probes
- `observability/` exporter + Prometheus + Grafana as code
- `catalogue/` technique and model metadata
- `docs/` runbooks and reading tracks
- `artifacts/` generated outputs

## Notes

- If the instance has no attached volume, local state is ephemeral.
- Sync critical artifacts frequently (`make sync DEST=user@host:/path`).
- Keep token files and `.env` out of git.
