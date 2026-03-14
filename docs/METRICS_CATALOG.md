# Metrics Catalog

## 1. Runtime / Infrastructure Metrics
1. `rna_gpu_util_percent` gauge
1. `rna_vram_used_bytes` gauge
1. `rna_cpu_util_percent` gauge
1. `rna_disk_used_bytes` gauge
1. `rna_service_up{service=...}` gauge

## 2. Execution Fabric Metrics
1. `rna_jobs_total{status=queued|running|completed|failed|stale|superseded}` counter
1. `rna_job_duration_seconds{stage=...}` histogram
1. `rna_dispatch_total` counter
1. `rna_rerun_total{reason=...}` counter

## 3. Data and Registry Metrics
1. `rna_ingest_total{format=...}` counter
1. `rna_ingest_fail_total{reason=...}` counter
1. `rna_registry_writes_total` counter
1. `rna_artifact_bytes_total{kind=...}` counter

## 4. Scientific Quality Metrics
1. `rna_tm_score` histogram
1. `rna_lddt_score` histogram
1. `rna_confidence_calibration_error` gauge
1. `rna_family_dropout_score` gauge
1. `rna_motif_dropout_score` gauge
1. `rna_length_band_score` gauge

## 5. Prioritization Metrics
1. `rna_voi_score` histogram
1. `rna_voi_component{component=uncertainty|upside|cost|novelty|relevance|coverage}` gauge
1. `rna_next_run_selected_total` counter

## 6. CI/CD Metrics
1. `rna_ci_runs_total{status=pass|fail}` counter
1. `rna_ci_duration_seconds` histogram
1. `rna_deploy_total{target=vast,status=pass|fail}` counter
1. `rna_deploy_duration_seconds{target=vast}` histogram
