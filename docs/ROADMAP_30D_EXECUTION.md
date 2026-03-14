# Roadmap: 30-Day Execution

## Objective
Ship a stable RNA observatory loop where runs, artifacts, comparison, and next actions are connected end-to-end.

## Week 1: Stabilize Runtime
1. Harden Vast deploy path with retry and health checks.
2. Ensure `kaggle-mashup` launches on boot and writes to `logs/`.
3. Add deterministic backup task for `/home/user/Sync/Projects/rna_folding`.
4. Validate `labops` commands in clean env via `uv run`.

## Week 2: Data and Registry Contracts
1. Enforce canonical run manifest for every ingestion path.
2. Add dataset profile artifacts for all CSV/Parquet ingests.
3. Require `validation_spec` and `run_id` in registry writes.
4. Add run-to-hypothesis linking command.

## Week 3: Parallel Run Fabric
1. Execute real notebook batches (3 -> 10 -> 12 workers) on GPU node.
2. Persist status transitions: `queued|running|completed|failed|stale|superseded`.
3. Add rerun planner based on VOI + failure type.
4. Expose run fabric metrics to Prometheus.

## Week 4: Interpretation and Prioritization
1. Upgrade compare view with metric/representation/provenance deltas.
2. Add structure-delta drawer for RNA runs.
3. Add VOI decomposition panel (`uncertainty/upside/cost/novelty/relevance/coverage`).
4. Publish daily operator report to `docs/LIVE_ENDPOINTS.md` + `docs/SCRIPT_EXECUTION_LEDGER.md`.

## Exit Criteria
1. One command deploy to Vast works twice in a row.
2. At least 12 runs visible in ledger with artifacts and compare-ready metadata.
3. At least 3 hypothesis decisions backed by explicit VOI reasoning.
