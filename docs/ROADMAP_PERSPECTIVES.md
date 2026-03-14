# Multi-Perspective Roadmaps

This document defines the same project from different vantage points so strategy and execution stay aligned.

## Perspective A: Research Lead
### Intent
Maximize experimental legibility and insight extraction from RNA notebook ecosystems.

### Vision
Every run is comparable, reproducible, and mapped to biological meaning.

### Nested TODOs
1. `A1` Canonical Representation Layer
1. `A1.1` Enforce `SequenceRecord`, `StructureRecord`, `RunRecord` output for all ingests.
1. `A1.2` Add representation conversion checks (`dot_bracket <-> contact_map <-> coordinates`).
1. `A1.3` Tag each run with `validation_spec`.
1. `A2` Interpretation Surfaces
1. `A2.1` Expand compare view to metric + provenance + representation deltas.
1. `A2.2` Add residue-level structure delta output for two-run comparisons.
1. `A2.3` Add failure mode tags (helix closure, loop drift, confidence collapse).
1. `A3` Hypothesis + VOI
1. `A3.1` Persist VOI decomposition fields per proposal.
1. `A3.2` Add run-to-hypothesis evidence linking.
1. `A3.3` Auto-suggest next runs by VOI/cost frontier.

## Perspective B: Platform Engineer
### Intent
Operate the GPU lab as a durable, repeatable, low-friction runtime.

### Vision
Deploy, execute, recover, and scale without manual firefighting.

### Nested TODOs
1. `B1` Deploy Reliability
1. `B1.1` Create single command Vast deploy script with retries and health checks.
1. `B1.2` Add rollback behavior on failed deploy.
1. `B1.3` Ensure all long-running services write bounded logs.
1. `B2` Data Durability
1. `B2.1` Add daily backup + checksum workflow.
1. `B2.2` Define artifact retention and cleanup policy.
1. `B2.3` Add restore drill script and run monthly.
1. `B3` Execution Fabric
1. `B3.1` Promote notebook runner into generic job fabric (ingest/eval/graph/cache jobs).
1. `B3.2` Add status transitions `queued|running|completed|failed|stale|superseded`.
1. `B3.3` Export run-fabric metrics to Prometheus.

## Perspective C: Product + UX
### Intent
Make complex RNA ML operations feel like coherent scientific instruments.

### Vision
Users move from raw artifacts to decisions in minutes, not hours.

### Nested TODOs
1. `C1` Observatory IA
1. `C1.1` Keep stable instrument naming: Pipeline Observatory, Submission Ledger, Run Fabric, VOI Compass, Operator Trace.
1. `C1.2` Add persistent right-hand context rail in all views.
1. `C1.3` Add evidence strip with latest artifacts/errors/notes.
1. `C2` Garden as Learning Surface
1. `C2.1` Bind plant morphology to real registry metrics.
1. `C2.2` Support grow-from-paste into persistent catalog entries.
1. `C2.3` Link each plant to compare + run details.
1. `C3` Operator Ergonomics
1. `C3.1` Add quick-action snippets with copy and execute hints.
1. `C3.2` Add first-run onboarding checklist.
1. `C3.3` Add “what changed since last session” summary.

## Perspective D: MLOps Governance
### Intent
Guarantee traceability, reproducibility, and change safety as scope grows.

### Vision
Every output is attributable to code+config+data lineage.

### Nested TODOs
1. `D1` Reproducibility Contracts
1. `D1.1` Require run manifests with code revision, config hash, dataset hash.
1. `D1.2` Stamp artifacts with deterministic IDs.
1. `D1.3` Add reproducibility verification command.
1. `D2` CI/CD
1. `D2.1` Add CI matrix for lint + unit + CLI smoke.
1. `D2.2` Add release workflow for point releases and changelog.
1. `D2.3` Add deploy smoke to Vast target with guarded secrets.
1. `D3` Security and Secrets
1. `D3.1` Restrict token scopes and rotate on cadence.
1. `D3.2` Enforce secret scanning in CI.
1. `D3.3` Add documented incident response for key leakage.
