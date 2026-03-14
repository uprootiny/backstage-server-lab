# Completion Ledgers

Completion ledgers are append-only records proving what was run, what changed, what passed, and what failed.

## File Locations
1. `artifacts/ledgers/completion_ledger.jsonl`
1. `artifacts/ledgers/release_ledger.jsonl`

## Completion Event Schema
```json
{
  "ts": "2026-03-14T04:00:00Z",
  "kind": "completion",
  "run_id": "run_2026_03_14_001",
  "task_id": "B1.1",
  "status": "completed",
  "repo_rev": "e56bd91",
  "artifacts": [
    "artifacts/rna_predictions/run_2026_03_14_001/prediction.pdb",
    "artifacts/kaggle_parallel/ledger.jsonl"
  ],
  "checks": {
    "lint": "pass",
    "cli_smoke": "pass",
    "deploy_health": "pass"
  },
  "notes": "observatory launch verified"
}
```

## Release Event Schema
```json
{
  "ts": "2026-03-14T04:05:00Z",
  "kind": "release",
  "version": "0.1.1",
  "repo_rev": "e56bd91",
  "scope": "observatory/run-fabric/seed-catalogue",
  "validation_summary": {
    "commands_run": 7,
    "passed": 6,
    "failed": 1
  }
}
```

## Minimal Writer Pattern
```bash
mkdir -p artifacts/ledgers
printf '%s\n' '{"ts":"2026-03-14T04:00:00Z","kind":"completion","status":"completed"}' >> artifacts/ledgers/completion_ledger.jsonl
```
