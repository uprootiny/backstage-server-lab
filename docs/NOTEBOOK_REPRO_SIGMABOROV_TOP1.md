# Kaggle Notebook Reproduction: `sigmaborov/stanford-rna-3d-folding-top-1-solution`

## What was integrated
- Pulled from Kaggle contest notebooks into:
  - `notebooks/kaggle/sigmaborov-top1/stanford-rna-3d-folding-top-1-solution.ipynb`
- Created a local-executable variant for Vast harness:
  - `notebooks/kaggle/sigmaborov-top1/stanford-rna-3d-folding-top-1-solution.local.ipynb`

## Adaptation strategy
- Disabled Kaggle wheel-install cell for non-Kaggle runtime.
- Forced local test mode to keep run bounded.
- Bound environment variables for local execution:
  - `PROTENIX_CODE_DIR` and `PROTENIX_ROOT_DIR` -> Protenix tree under `/home/user/Sync/Projects/rna_folding/data/qiweiyin/.../Protenix-v1`
  - `TEST_CSV` -> `/home/user/Sync/Projects/rna_folding/data/test_sequences_min1.csv`
  - `SUBMISSION_CSV` -> `artifacts/kaggle_parallel/sigmaborov_submission.csv`

## Reproduction run
- Harness plan:
  - `artifacts/kaggle_parallel/plan_sigmaborov_local.json`
- Ledger run id:
  - `kaggle-parallel-20260314T123902Z`
- Outcome:
  - `job_id=sigmaborov-local-004`
  - `status=ok`
  - `seconds=83.53`

## Produced artifacts
- Executed notebook:
  - `artifacts/kaggle_parallel/executed/sigmaborov-local-004.executed.ipynb`
- Submission:
  - `artifacts/kaggle_parallel/sigmaborov_submission.csv`
- Run log:
  - `logs/sigmaborov-local-004.log`

## Fast replay
```bash
cd /workspace/backstage-server-lab
PYTHONPATH=/workspace/backstage-server-lab/src /venv/main/bin/python -m labops.cli kaggle-parallel-dispatch \
  --plan artifacts/kaggle_parallel/plan_sigmaborov_local.json \
  --workers 1 \
  --ledger artifacts/kaggle_parallel/ledger.jsonl \
  --logs-dir logs/kaggle_parallel \
  --executed-dir artifacts/kaggle_parallel/executed
```

## Key notebook behavior observed
- Local mode executed with one short target batch (`9QZJ` sample in this replay).
- TBM phase covered the sample directly.
- Submission CSV emitted successfully without requiring full Protenix phase for this bounded run.
