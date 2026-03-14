# MLOps Validation Bench

This bench provides a steady Python-first workflow for:

- formulating hypotheses
- tracking VOI priors
- running 3+ variants in parallel
- validating outcomes
- exporting a searchable thesis/result graph

## Setup

```bash
cd /workspace/backstage-server-lab
bash scripts/bootstrap.sh
```

## Run bench

```bash
bash scripts/run_validation_bench.sh hypothesis-demo
```

Equivalent raw commands:

```bash
labops formulate \
  --hypothesis-id hypothesis-demo \
  --statement "Wiggle params, improve score" \
  --question "Which parallel variant wins under constraints?" \
  --voi-prior 0.65 \
  --kaggle-ref "playground-series" \
  --paper-ref "https://arxiv.org/abs/1810.04805"

labops run-bench --hypothesis-id hypothesis-demo --config configs/validation_bench.yaml --workers 3
labops validate --min-metric 0.70
labops graph --out artifacts/thesis_graph.json
```

Outputs:

- `artifacts/validation_bench.db`
- `artifacts/thesis_graph.json`

## Kaggle Mashup UI

```bash
bash scripts/run_kaggle_mashup.sh
```

Open:

- `http://<host>:8511`

The UI merges competitions/challenges and datasets in one sortable view.
