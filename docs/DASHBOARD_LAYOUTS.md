# Dashboard Layouts

## Dashboard 1: RNA Observatory Overview
Intent:
1. Show system health, throughput, and decision flow at a glance.

Layout:
1. Row 1: `GPU Utilization`, `VRAM Usage`, `Run Success Rate`.
1. Row 2: `Queued Jobs`, `Running Jobs`, `Failed Jobs (24h)`.
1. Row 3: `Ingest Throughput`, `Registry Writes`, `VOI Mean`.
1. Row 4: `Operator Events by Kind`, `Anomalies`.

## Dashboard 2: Run Fabric and CI/CD
Intent:
1. Show execution fabric behavior and deployment reliability.

Layout:
1. Row 1: `Dispatch Rate`, `Completion Rate`, `Rerun Rate`.
1. Row 2: `CI Pass Rate`, `Deploy Success Rate`, `Median Deploy Time`.
1. Row 3: `Run Stage Durations`.
1. Row 4: `Event Stream Heatmap`.

## Dashboard 3: RNA Quality and Scoring
Intent:
1. Track scientific quality over time and compare model families.

Layout:
1. Row 1: `TM-score p50/p90`, `lDDT p50/p90`, `Confidence Calibration Error`.
1. Row 2: `Family Dropout Score`, `Motif Dropout Score`, `Length Band Score`.
1. Row 3: `Score by Architecture`.
1. Row 4: `Top Deliberate Next Runs (VOI Frontier)`.
