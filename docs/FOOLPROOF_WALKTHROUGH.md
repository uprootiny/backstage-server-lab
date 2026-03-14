# Foolproof Walkthrough

This walkthrough is built for repeatability under real constraints.

## A. Baseline Reality Check

```bash
cd /workspace/backstage-server-lab
AUTO_HEAL=1 bash scripts/doctor_harness.sh
```

Expected output artifact:
- `docs/STACK_DOCTOR_LATEST.md`

Proceed only if:
- required pieces are present
- `python_cli_ready: 1`

## B. Algorithmic Coherence Check

```bash
cd /workspace/backstage-server-lab
bash scripts/integration_coherence_checks.sh
```

Expected outputs:
- `docs/INTEGRATION_COHERENCE_CHECKS.md`
- `docs/RNA_PIPELINE_ANALYTICS.md`
- `reports/rna_pipeline_analytics.json`

## C. Multi-run ML Dispatch (Dozens)

```bash
cd /workspace/backstage-server-lab
WORKERS=4 JOBS=36 TIMEOUT_MIN=35 bash scripts/dispatch_rna_bulk.sh
```

Expected outputs:
- `artifacts/kaggle_parallel/plan_bulk_methodical.json`
- `artifacts/kaggle_parallel/ledger.jsonl`
- `artifacts/kaggle_parallel/executed/*.executed.ipynb`

## D. Analytic Teardown (Top 12 Kaggle RNA notebooks)

```bash
cd /workspace/backstage-server-lab
TOP_N=12 bash scripts/teardown_kaggle_rna_top12.sh
```

Expected outputs:
- `docs/KAGGLE_RNA_TOP12_TEARDOWN.md`
- `docs/KAGGLE_RNA_TOP12_TEARDOWN.json`
- `notebooks/kaggle/live_teardown/*`

## E. Live URLs (current Vast mapping)

- Jupyter: `https://175.155.64.231:19808`
- TensorBoard: `http://175.155.64.231:19448`
- Research library: `http://175.155.64.231:19121`
- Syncthing: `http://175.155.64.231:19753`
- Open slot: `http://175.155.64.231:19842`

## F. Definition of "Meaningful Result"

A run is meaningful only if all are true:
- doctor report generated and no critical missing pieces
- at least one successful `job_end` in ledger for current run window
- executed notebook artifact exists and is non-empty
- pipeline analytics invariants pass
