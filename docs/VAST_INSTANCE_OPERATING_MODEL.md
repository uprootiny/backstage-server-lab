# Vast Instance Operating Model

The same instance is operated in three concurrent modes.

## Mode A: Dumb Notebook Runner
Intent:
1. Fast ad-hoc execution for Kaggle/Jupyter workflows.

Requirements:
1. Jupyter available on startup.
1. Minimal dependency friction.
1. Easy file ingress/egress.

Guardrails:
1. Capture notebook outputs into artifacts.
1. Do not treat notebook output as final without normalization.

## Mode B: Bespoke Experiment Management System
Intent:
1. Convert ad-hoc runs into reproducible tracked experiments.

Requirements:
1. `labops` as orchestration CLI.
1. Run manifests, registry writes, validation specs.
1. Compare and VOI surfaces active.

Guardrails:
1. Every run must produce manifest + artifacts.
1. Every decision must link to evidence and validation split.

## Mode C: Radical DevOps Foray
Intent:
1. Treat the instance as a proving ground for deploy/recovery/observability patterns.

Requirements:
1. Automated deploy and health checks.
1. Prometheus + Grafana + event stream.
1. Backup/restore drills.

Guardrails:
1. No secret leakage in logs.
1. Keep rollback path for every deploy.
1. CI/CD and runtime checks must be visible in dashboards.

## Shared Contract Across All Modes
1. State layer is append-only and queryable (`artifacts/*`, ledgers, manifests).
1. Execution layer emits typed events.
1. Interpretation and prioritization use the same run IDs.
1. Observability spans both infrastructure and scientific quality.
