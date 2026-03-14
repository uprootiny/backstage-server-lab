# Scoring Model

## 1. Run Quality Score

Define a composite run score to rank candidate runs:

```text
run_quality_score =
  0.35 * tm_score_norm +
  0.25 * lddt_norm +
  0.15 * family_dropout_norm +
  0.10 * motif_dropout_norm +
  0.10 * confidence_calibration_norm +
  0.05 * reproducibility_norm
```

Notes:
1. `*_norm` should be normalized to `[0,1]`.
1. Missing values should be imputed conservatively.

## 2. VOI Score

```text
voi_score = ((uncertainty * upside * relevance * novelty) / cost) * coverage_bonus
```

Recommended defaults:
1. `uncertainty`: model disagreement or confidence entropy.
1. `upside`: projected gain from prior nearby runs.
1. `relevance`: alignment with current hypothesis.
1. `novelty`: distance from already tested configurations.
1. `cost`: normalized GPU/latency cost.
1. `coverage_bonus`: increases score for under-sampled validation regimes.

## 3. Promotion Rules

1. `candidate`: `run_quality_score >= 0.60`
1. `review`: `run_quality_score >= 0.70` and `family_dropout_norm >= 0.55`
1. `promote`: `run_quality_score >= 0.78` and no critical reproducibility violations

## 4. Rerun Rules

1. Rerun failed jobs if `voi_score >= 0.12`.
1. Rerun stale jobs if upstream artifact changed.
1. Do not rerun superseded jobs unless explicitly requested.
