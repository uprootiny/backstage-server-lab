# Backstage Server Lab

A clone-friendly, single-node ML/dev workspace optimized for Vast.ai Jupyter boxes and SSH-driven operations.

## Design goals

- one-command bootstrap on a fresh GPU worker
- reproducible Python/toolchain via `mise` + `uv`
- comfy terminal/Jupyter setup (`tmux`, sensible defaults, aliases)
- minimal MLOps spine (MLflow + TensorBoard + run logs)
- explicit durability hooks (artifact sync)

## Quick start (on Vast / Jupyter terminal)

```bash
git clone https://github.com/uprootiny/backstage-server-lab.git backstage-server-lab
cd backstage-server-lab
bash scripts/bootstrap.sh
make up
make sanity
```

Single-command clone + bootstrap:

```bash
bash scripts/vast_clone_bootstrap.sh https://github.com/uprootiny/backstage-server-lab.git /workspace/backstage-server-lab
```

## Daily workflow

```bash
cd backstage-server-lab
make up
make train-stub
make bench
make doctor
make down
```

## Validation Bench (Python + uv/uvx style)

This repo now includes a hypothesis-driven validation bench with:

- 3 variants in parallel
- parameter wiggle exploration
- hypothesis + VOI tracking
- validation gates
- thesis/result graph export with Kaggle/paper references

Run:

```bash
bash scripts/run_validation_bench.sh hypothesis-demo
```

Core commands:

```bash
labops formulate --hypothesis-id hyp-1 --statement "..." --question "..." --voi-prior 0.7 --kaggle-ref playground-series --paper-ref https://arxiv.org/abs/1810.04805
labops run-bench --hypothesis-id hyp-1 --config configs/validation_bench.yaml --workers 3
labops validate --min-metric 0.70
labops graph --out artifacts/thesis_graph.json
```

See: `docs/MLOPS_VALIDATION_BENCH.md`

## Kaggle Mashup UI

A mashup UI to sort/filter competitions/challenges and datasets:

```bash
bash scripts/run_kaggle_mashup.sh
```

Open:

- `http://<host>:8511`

Requires Kaggle auth (`~/.kaggle/kaggle.json` or `KAGGLE_USERNAME` + `KAGGLE_KEY`).

Build structured RNA-focused catalogue (competitions/models/notebooks/datasets):

```bash
make kaggle-catalogue
```

Output:

- `artifacts/kaggle_catalogue.json`

The mashup app can refresh/read this catalogue in the `Structured Catalogue` tab.
If Kaggle auth is missing, the viewer is prepopulated from repo seeds in `data/seeds/`.

## Starter notebook library

Curated local starters are versioned in:

- `notebooks/starters/`
- `notebooks/starters/index.json`

Includes:

- RNA EDA baseline
- RNA 3D training stub
- RNA eval + workbench artifact bridge

## RNA prediction bridge (workbench input path)

Serve prediction artifacts for external workbenches/3D viewers:

```bash
make rna-bridge
make rna-register PDB=/path/to/prediction.pdb RUN_ID=exp42 SEQUENCE=AUGC MODEL=baseline-v1
```

Bridge index:

- `http://<host>:19999/index.json`

Prediction URL shape:

- `http://<host>:19999/<run_id>/prediction.pdb`

Universal ingestion from notebook outputs:

```bash
make rna-ingest INPUT=/path/result.(pdb|csv|json|npy|npz) RUN_ID=exp42 SEQUENCE=AUGCUA MODEL=my-model
```

This normalizes diverse outputs into:

- `artifacts/rna_predictions/<run_id>/prediction.pdb`
- `artifacts/rna_predictions/index.json`

## RNA 3D Workbench

Serve the interactive viewer (quick-load targets, URL fetch, bridge fetch, overlay controls, residue strip, compare panel):

```bash
make rna-workbench
```

Open:

- `http://<host>:8522/rna_workbench.html`

## Layout

- `scripts/` setup and service management
- `src/` training and utility code
- `configs/` experiment configs
- `artifacts/` checkpoints/models/tb logs
- `logs/` service and run logs
- `docs/` operational notes

## Notes

- If the Vast instance has no attached volume, treat local state as ephemeral.
- Use `make sync DEST=user@host:/path/backup` frequently.
- Operator runbook: `docs/GPU_WORKER_OPERATIONS.md`
- Connectivity report: `docs/CONNECTION_DOCTOR.md` via `make doctor`
