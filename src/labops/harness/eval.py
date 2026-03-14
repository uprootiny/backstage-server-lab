from __future__ import annotations


def run_quality_score(
    tm_score_norm: float,
    lddt_norm: float,
    family_dropout_norm: float,
    motif_dropout_norm: float,
    confidence_calibration_norm: float,
    reproducibility_norm: float,
) -> float:
    return (
        0.35 * tm_score_norm
        + 0.25 * lddt_norm
        + 0.15 * family_dropout_norm
        + 0.10 * motif_dropout_norm
        + 0.10 * confidence_calibration_norm
        + 0.05 * reproducibility_norm
    )


def voi_score(
    uncertainty: float,
    upside: float,
    relevance: float,
    novelty: float,
    cost: float,
    coverage_bonus: float,
) -> float:
    denom = cost if cost > 0 else 1e-6
    return ((uncertainty * upside * relevance * novelty) / denom) * coverage_bonus
