# RNA Technique Matrix Validation

- generated_at: 2026-03-14T17:49:40.846827Z
- run_id: `kaggle-parallel-20260314T174604Z`
- plan: `/home/uprootiny/backstage-server-lab/artifacts/kaggle_parallel/plan_rna_technique_matrix.json`
- expected_jobs: 9
- observed_jobs: 9
- ok: 9
- failed: 0

## Group Summary

| Technique | Dataset | Param Profile | Runs | OK | Failed | Success Rate | Median Seconds |
|---|---|---|---:|---:|---:|---:|---:|
| `baseline_reliable` | `stanford_rna_3d_kaggle` | `base` | 1 | 1 | 0 | 1.00 | 108.28 |
| `baseline_reliable` | `stanford_rna_3d_kaggle` | `p_recycle_6` | 1 | 1 | 0 | 1.00 | 107.43 |
| `baseline_reliable` | `stanford_rna_3d_kaggle` | `p_seed_3` | 1 | 1 | 0 | 1.00 | 104.28 |
| `high_score_pragmatic` | `stanford_rna_3d_kaggle` | `base` | 1 | 1 | 0 | 1.00 | 6.57 |
| `high_score_pragmatic` | `stanford_rna_3d_kaggle` | `p_recycle_10` | 1 | 1 | 0 | 1.00 | 6.60 |
| `high_score_pragmatic` | `stanford_rna_3d_kaggle` | `p_template_off` | 1 | 1 | 0 | 1.00 | 6.98 |
| `insight_maximizer` | `stanford_rna_3d_kaggle` | `base` | 1 | 1 | 0 | 1.00 | 6.62 |
| `insight_maximizer` | `stanford_rna_3d_kaggle` | `p_delta_020` | 1 | 1 | 0 | 1.00 | 6.67 |
| `insight_maximizer` | `stanford_rna_3d_kaggle` | `p_delta_030` | 1 | 1 | 0 | 1.00 | 6.32 |

## Perturbation Effects

| Technique | Dataset | Repeat | Param Profile | Base | Variant | Δ Seconds |
|---|---|---:|---|---|---|---:|
| `baseline_reliable` | `stanford_rna_3d_kaggle` | 1 | `p_recycle_6` | `ok` | `ok` | -0.85 |
| `baseline_reliable` | `stanford_rna_3d_kaggle` | 1 | `p_seed_3` | `ok` | `ok` | -4.00 |
| `high_score_pragmatic` | `stanford_rna_3d_kaggle` | 1 | `p_template_off` | `ok` | `ok` | 0.41 |
| `high_score_pragmatic` | `stanford_rna_3d_kaggle` | 1 | `p_recycle_10` | `ok` | `ok` | 0.03 |
| `insight_maximizer` | `stanford_rna_3d_kaggle` | 1 | `p_delta_030` | `ok` | `ok` | -0.30 |
| `insight_maximizer` | `stanford_rna_3d_kaggle` | 1 | `p_delta_020` | `ok` | `ok` | 0.05 |
