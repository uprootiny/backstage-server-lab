# Meaningful Results Runbook

This runbook is the minimum methodical path to produce **real, inspectable outcomes** on the Vast GPU instance.

## Preconditions

- SSH access works:
  - `ssh -i ~/.ssh/gpu_orchestra_ed25519 -p 19636 root@175.155.64.231`
- Repo exists on instance at `/workspace/backstage-server-lab`
- Python env exists at `/venv/main/bin/python`

## 1) Doctor First (Ground Reality)

Run before any workload:

```bash
cd /workspace/backstage-server-lab
AUTO_HEAL=1 bash scripts/doctor_harness.sh
```

Outputs:
- `docs/STACK_DOCTOR_LATEST.md`

This report verifies:
- required repo pieces
- local/public service reachability
- harness readiness (CLI + Kaggle)
- ledger health (`job_end_ok`, `job_end_failed`)
- GPU snapshot

## 2) Surface Web UIs

Core URLs expected on this instance:
- Jupyter: `https://175.155.64.231:19808`
- TensorBoard: `http://175.155.64.231:19448`
- Research library: `http://175.155.64.231:19121`
- Syncthing: `http://175.155.64.231:19753`
- Reserved open surface: `http://175.155.64.231:19842`

If a surface is down, rerun:

```bash
AUTO_HEAL=1 bash scripts/doctor_harness.sh
```

## 3) Dispatch Several Dozen Pipeline Runs

Default dispatch is 36 jobs, worker cap 4:

```bash
cd /workspace/backstage-server-lab
WORKERS=4 JOBS=36 TIMEOUT_MIN=35 bash scripts/dispatch_rna_bulk.sh
```

Artifacts:
- plan: `artifacts/kaggle_parallel/plan_bulk_methodical.json`
- ledger: `artifacts/kaggle_parallel/ledger.jsonl`
- executed notebooks: `artifacts/kaggle_parallel/executed/*.executed.ipynb`
- logs: `logs/kaggle_parallel/*.log`

## 4) Live Kaggle Top-12 RNA Teardown

```bash
cd /workspace/backstage-server-lab
TOP_N=12 bash scripts/teardown_kaggle_rna_top12.sh
```

Outputs:
- `docs/KAGGLE_RNA_TOP12_TEARDOWN.md`
- `docs/KAGGLE_RNA_TOP12_TEARDOWN.json`
- pulled notebooks under `notebooks/kaggle/live_teardown/`

## 5) Post-run Verification

```bash
AUTO_HEAL=0 bash scripts/doctor_harness.sh
PYTHONPATH=/workspace/backstage-server-lab/src /venv/main/bin/python -m labops.cli kaggle-parallel-status --ledger artifacts/kaggle_parallel/ledger.jsonl
```

Use these as acceptance checks:
- doctor report has no missing required pieces
- public surfaces return `UP`
- ledger has growing `job_end_ok`
- failures are explainable from logs

## Constraints and Capacity Defaults

- GPU: 1x RTX 4080 SUPER (32GB)
- safe worker default: `WORKERS=4`
- notebook timeout default: `35 min`
- retry policy: max 2 attempts with backoff

Raise workers only if:
- GPU utilization is below target and memory headroom remains stable
- failed jobs are not timeout/OOM bound
