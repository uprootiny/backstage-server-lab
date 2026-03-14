"""
kaggle_scoring.py — Server-side Kaggle submission scoring simulator.

Implements scoring metrics for three RNA/ML Kaggle competitions:

1. Stanford RNA 3D Folding (Part 2)
   - Metric: TM-score (template modeling score, 0-1, higher=better)
   - Evaluates predicted 3D coordinates against ground truth

2. Stanford Ribonanza RNA Folding
   - Metric: MAE (mean absolute error on reactivity, lower=better)
   - Evaluates predicted chemical reactivity profiles

3. OpenVaccine: COVID-19 mRNA Vaccine Degradation Prediction
   - Metric: MCRMSE (mean columnwise RMSE, lower=better)
   - Evaluates predicted degradation rates at each position

Each scorer can:
  - Score a single submission against ground truth
  - Generate synthetic ground truth for testing
  - Produce a leaderboard from multiple submissions
  - Export results to JSONL for the pipeline ledger
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np
from numpy.linalg import norm, svd


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TM-score (RNA 3D Folding)
# ═══════════════════════════════════════════════════════════════════════════════

def tm_score(pred_coords: np.ndarray, true_coords: np.ndarray) -> float:
    """
    Template Modeling score for 3D structure comparison.

    TM-score ∈ (0, 1], where 1 = perfect match.
    TM-score > 0.5 generally indicates same fold.

    Uses Kabsch alignment (optimal rotation) then the Zhang & Skolnick
    length-normalized distance formula.
    """
    assert pred_coords.shape == true_coords.shape
    n = len(pred_coords)
    if n == 0:
        return 0.0

    # Kabsch alignment
    pred_c = pred_coords - pred_coords.mean(axis=0)
    true_c = true_coords - true_coords.mean(axis=0)
    H = pred_c.T @ true_c
    U, S, Vt = svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    diag = np.diag([1.0, 1.0, d])
    R = Vt.T @ diag @ U.T
    pred_aligned = pred_c @ R.T

    # TM-score formula
    d0 = 1.24 * max(1, n - 15) ** (1.0 / 3.0) - 1.8  # length-dependent scale
    d0 = max(d0, 0.5)

    dists = norm(pred_aligned - true_c, axis=1)
    tm = (1.0 / (1.0 + (dists / d0) ** 2)).sum() / n
    return float(tm)


def lddt_score(pred_coords: np.ndarray, true_coords: np.ndarray,
               thresholds=(0.5, 1.0, 2.0, 4.0)) -> float:
    """
    Local Distance Difference Test (lDDT).

    Measures fraction of local distance pairs preserved within thresholds.
    Used in CASP/RNA-Puzzles evaluations.
    """
    n = len(pred_coords)
    if n < 2:
        return 0.0

    # Compute pairwise distances
    pred_d = np.sqrt(((pred_coords[:, None] - pred_coords[None, :]) ** 2).sum(-1))
    true_d = np.sqrt(((true_coords[:, None] - true_coords[None, :]) ** 2).sum(-1))

    # Only consider local contacts (true distance < 15Å)
    mask = (true_d < 15.0) & (np.eye(n) == 0)
    if mask.sum() == 0:
        return 0.0

    diff = np.abs(pred_d - true_d)
    total = 0.0
    for t in thresholds:
        total += (diff[mask] < t).mean()
    return float(total / len(thresholds))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MAE (Ribonanza RNA Folding)
# ═══════════════════════════════════════════════════════════════════════════════

def ribonanza_mae(pred_reactivity: np.ndarray, true_reactivity: np.ndarray,
                  mask: Optional[np.ndarray] = None) -> float:
    """
    Mean Absolute Error for reactivity prediction.

    Ribonanza scoring: MAE over all valid positions across all sequences.
    Lower is better. Typical winning scores: 0.12-0.15.
    """
    if mask is not None:
        pred_reactivity = pred_reactivity[mask]
        true_reactivity = true_reactivity[mask]
    return float(np.abs(pred_reactivity - true_reactivity).mean())


def ribonanza_per_experiment_mae(pred: dict[str, np.ndarray],
                                 true: dict[str, np.ndarray]) -> dict[str, float]:
    """Per-experiment MAE (DMS, 2A3, SHAPE)."""
    results = {}
    for exp in pred:
        if exp in true:
            results[exp] = ribonanza_mae(pred[exp], true[exp])
    results["overall"] = np.mean(list(results.values())) if results else 1.0
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MCRMSE (OpenVaccine mRNA Degradation)
# ═══════════════════════════════════════════════════════════════════════════════

def mcrmse(pred: np.ndarray, true: np.ndarray) -> float:
    """
    Mean Columnwise Root Mean Squared Error.

    OpenVaccine metric: RMSE computed per target column, then averaged.
    Targets: reactivity, deg_Mg_pH10, deg_pH10, deg_Mg_50C, deg_50C
    Lower is better. Typical winning scores: 0.22-0.28.
    """
    if pred.ndim == 1:
        return float(np.sqrt(((pred - true) ** 2).mean()))
    per_col = np.sqrt(((pred - true) ** 2).mean(axis=0))
    return float(per_col.mean())


# ═══════════════════════════════════════════════════════════════════════════════
# Synthetic Ground Truth Generators
# ═══════════════════════════════════════════════════════════════════════════════

def generate_rna3d_ground_truth(n_sequences: int = 20, seed: int = 42) -> list[dict]:
    """Generate synthetic RNA 3D folding ground truth."""
    from labops.rna_3d_pipeline import GrammarConfig, derive, build_record

    rng = np.random.default_rng(seed)
    gt = []
    for i in range(n_sequences):
        cfg = GrammarConfig(
            gc_bias=float(rng.uniform(0.35, 0.70)),
            max_depth=int(rng.integers(3, 8)),
            wobble_p=float(rng.uniform(0.05, 0.15)),
        )
        local = np.random.default_rng(seed=seed + i)
        motif = derive(local, cfg)
        try:
            rec = build_record(motif)
            gt.append({
                "id": f"rna3d_{i:04d}",
                "sequence": rec.secondary.motif.sequence,
                "bracket": rec.secondary.bracket,
                "coords": rec.geometry.coords,
                "n_pairs": rec.secondary.stats.n_pairs,
                "pairing_fraction": rec.secondary.stats.pairing_fraction,
            })
        except Exception:
            continue
    return gt


def generate_ribonanza_ground_truth(n_sequences: int = 50, seed: int = 42) -> list[dict]:
    """Generate synthetic reactivity profiles."""
    rng = np.random.default_rng(seed)
    gt = []
    for i in range(n_sequences):
        n = int(rng.integers(40, 200))
        seq = "".join(rng.choice(list("AUGC"), size=n))
        # Simulated reactivity: paired positions have low reactivity
        paired = rng.random(n) > 0.5
        dms = np.where(paired, rng.uniform(0.0, 0.3, n), rng.uniform(0.5, 1.5, n))
        a2a3 = np.where(paired, rng.uniform(0.0, 0.2, n), rng.uniform(0.3, 1.2, n))
        gt.append({
            "id": f"ribo_{i:04d}",
            "sequence": seq,
            "dms_reactivity": dms.astype(np.float32),
            "2a3_reactivity": a2a3.astype(np.float32),
        })
    return gt


def generate_openvaccine_ground_truth(n_sequences: int = 30, seed: int = 42) -> list[dict]:
    """Generate synthetic mRNA degradation profiles."""
    rng = np.random.default_rng(seed)
    gt = []
    for i in range(n_sequences):
        n = int(rng.integers(68, 130))  # OpenVaccine sequences are 68-130nt
        seq = "".join(rng.choice(list("AUGC"), size=n))
        targets = rng.uniform(0.0, 1.5, (n, 5)).astype(np.float32)
        gt.append({
            "id": f"vax_{i:04d}",
            "sequence": seq,
            "targets": targets,  # reactivity, deg_Mg_pH10, deg_pH10, deg_Mg_50C, deg_50C
        })
    return gt


# ═══════════════════════════════════════════════════════════════════════════════
# Baseline Submission Generators
# ═══════════════════════════════════════════════════════════════════════════════

def baseline_rna3d(gt: list[dict], strategy: str = "grammar_egnn") -> list[dict]:
    """Generate baseline 3D predictions."""
    from labops.rna_3d_pipeline import bracket_to_3d

    rng = np.random.default_rng(99)
    preds = []
    for item in gt:
        if strategy == "grammar_egnn":
            # Use our pipeline: re-fold with noise
            coords = bracket_to_3d(item["bracket"], rng=rng, noise=0.5)
        elif strategy == "random_walk":
            n = len(item["sequence"])
            coords = np.cumsum(rng.normal(0, 3.0, (n, 3)), axis=0)
        elif strategy == "helix_only":
            n = len(item["sequence"])
            t = np.arange(n, dtype=float)
            coords = np.column_stack([
                9.0 * np.cos(t * 0.57),
                9.0 * np.sin(t * 0.57),
                t * 2.81,
            ])
        else:
            coords = item["coords"] + rng.normal(0, 2.0, item["coords"].shape)
        preds.append({"id": item["id"], "coords": coords})
    return preds


def baseline_ribonanza(gt: list[dict], strategy: str = "mean_fill") -> list[dict]:
    """Generate baseline reactivity predictions."""
    rng = np.random.default_rng(99)
    preds = []
    for item in gt:
        n = len(item["sequence"])
        if strategy == "mean_fill":
            dms = np.full(n, 0.5, dtype=np.float32)
            a2a3 = np.full(n, 0.4, dtype=np.float32)
        elif strategy == "gc_heuristic":
            dms = np.array([0.2 if c in "GC" else 0.7 for c in item["sequence"]], dtype=np.float32)
            a2a3 = dms * 0.8
        elif strategy == "noisy_oracle":
            dms = item["dms_reactivity"] + rng.normal(0, 0.15, n).astype(np.float32)
            a2a3 = item["2a3_reactivity"] + rng.normal(0, 0.12, n).astype(np.float32)
        else:
            dms = rng.uniform(0, 1.5, n).astype(np.float32)
            a2a3 = rng.uniform(0, 1.2, n).astype(np.float32)
        preds.append({"id": item["id"], "dms": dms, "2a3": a2a3})
    return preds


def baseline_openvaccine(gt: list[dict], strategy: str = "mean_fill") -> list[dict]:
    """Generate baseline degradation predictions."""
    rng = np.random.default_rng(99)
    preds = []
    for item in gt:
        n = len(item["sequence"])
        if strategy == "mean_fill":
            targets = np.full((n, 5), 0.5, dtype=np.float32)
        elif strategy == "noisy_oracle":
            targets = item["targets"] + rng.normal(0, 0.2, (n, 5)).astype(np.float32)
        else:
            targets = rng.uniform(0, 1.5, (n, 5)).astype(np.float32)
        preds.append({"id": item["id"], "targets": targets})
    return preds


# ═══════════════════════════════════════════════════════════════════════════════
# Scoring Engine
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SubmissionResult:
    competition: str
    strategy: str
    scores: dict
    n_sequences: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def score_rna3d(gt: list[dict], preds: list[dict], strategy: str = "unknown") -> SubmissionResult:
    """Score RNA 3D folding predictions."""
    pred_map = {p["id"]: p for p in preds}
    tm_scores, lddt_scores = [], []
    for item in gt:
        pred = pred_map.get(item["id"])
        if pred is None:
            continue
        true_c = item["coords"]
        pred_c = pred["coords"][:len(true_c)]  # trim to same length
        tm = tm_score(pred_c, true_c)
        ld = lddt_score(pred_c, true_c)
        tm_scores.append(tm)
        lddt_scores.append(ld)

    return SubmissionResult(
        competition="stanford-rna-3d-folding",
        strategy=strategy,
        n_sequences=len(tm_scores),
        scores={
            "tm_score_mean": float(np.mean(tm_scores)) if tm_scores else 0,
            "tm_score_std": float(np.std(tm_scores)) if tm_scores else 0,
            "tm_score_median": float(np.median(tm_scores)) if tm_scores else 0,
            "lddt_mean": float(np.mean(lddt_scores)) if lddt_scores else 0,
            "lddt_std": float(np.std(lddt_scores)) if lddt_scores else 0,
            "n_above_05": sum(1 for t in tm_scores if t > 0.5),
        },
    )


def score_ribonanza(gt: list[dict], preds: list[dict], strategy: str = "unknown") -> SubmissionResult:
    """Score Ribonanza reactivity predictions."""
    pred_map = {p["id"]: p for p in preds}
    dms_errs, a2a3_errs = [], []
    for item in gt:
        pred = pred_map.get(item["id"])
        if pred is None:
            continue
        dms_errs.append(float(np.abs(pred["dms"] - item["dms_reactivity"]).mean()))
        a2a3_errs.append(float(np.abs(pred["2a3"] - item["2a3_reactivity"]).mean()))

    return SubmissionResult(
        competition="stanford-ribonanza",
        strategy=strategy,
        n_sequences=len(dms_errs),
        scores={
            "mae_dms": float(np.mean(dms_errs)) if dms_errs else 1.0,
            "mae_2a3": float(np.mean(a2a3_errs)) if a2a3_errs else 1.0,
            "mae_overall": float(np.mean(dms_errs + a2a3_errs)) if dms_errs else 1.0,
        },
    )


def score_openvaccine(gt: list[dict], preds: list[dict], strategy: str = "unknown") -> SubmissionResult:
    """Score OpenVaccine degradation predictions."""
    pred_map = {p["id"]: p for p in preds}
    all_rmse = []
    for item in gt:
        pred = pred_map.get(item["id"])
        if pred is None:
            continue
        per_col = np.sqrt(((pred["targets"] - item["targets"]) ** 2).mean(axis=0))
        all_rmse.append(float(per_col.mean()))

    return SubmissionResult(
        competition="openvaccine-mrna",
        strategy=strategy,
        n_sequences=len(all_rmse),
        scores={
            "mcrmse": float(np.mean(all_rmse)) if all_rmse else 1.0,
            "mcrmse_std": float(np.std(all_rmse)) if all_rmse else 0,
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Full Evaluation Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def run_full_evaluation(out_dir: str = "/workspace/backstage-server-lab/artifacts") -> list[SubmissionResult]:
    """Run all baselines across all three competitions and produce a leaderboard."""
    results = []
    out_path = Path(out_dir)

    print("=" * 70)
    print("  KAGGLE SUBMISSION SCORING — 3 Competitions × Multiple Baselines")
    print("=" * 70)

    # --- RNA 3D Folding ---
    print("\n>>> Stanford RNA 3D Folding")
    gt_3d = generate_rna3d_ground_truth(n_sequences=30)
    print(f"    Ground truth: {len(gt_3d)} sequences")
    for strat in ["grammar_egnn", "helix_only", "random_walk", "noisy_oracle"]:
        preds = baseline_rna3d(gt_3d, strategy=strat)
        result = score_rna3d(gt_3d, preds, strategy=strat)
        results.append(result)
        s = result.scores
        print(f"    {strat:20s} TM={s['tm_score_mean']:.4f}±{s['tm_score_std']:.4f}  "
              f"lDDT={s['lddt_mean']:.4f}  >{'.5'}={s['n_above_05']}/{result.n_sequences}")

    # --- Ribonanza ---
    print("\n>>> Stanford Ribonanza RNA Folding")
    gt_ribo = generate_ribonanza_ground_truth(n_sequences=50)
    print(f"    Ground truth: {len(gt_ribo)} sequences")
    for strat in ["mean_fill", "gc_heuristic", "noisy_oracle", "random"]:
        preds = baseline_ribonanza(gt_ribo, strategy=strat)
        result = score_ribonanza(gt_ribo, preds, strategy=strat)
        results.append(result)
        s = result.scores
        print(f"    {strat:20s} MAE_dms={s['mae_dms']:.4f}  MAE_2a3={s['mae_2a3']:.4f}  "
              f"overall={s['mae_overall']:.4f}")

    # --- OpenVaccine ---
    print("\n>>> OpenVaccine mRNA Degradation")
    gt_vax = generate_openvaccine_ground_truth(n_sequences=30)
    print(f"    Ground truth: {len(gt_vax)} sequences")
    for strat in ["mean_fill", "noisy_oracle", "random"]:
        preds = baseline_openvaccine(gt_vax, strategy=strat)
        result = score_openvaccine(gt_vax, preds, strategy=strat)
        results.append(result)
        s = result.scores
        print(f"    {strat:20s} MCRMSE={s['mcrmse']:.4f}±{s['mcrmse_std']:.4f}")

    # --- Export leaderboard ---
    leaderboard = []
    for r in results:
        entry = {
            "competition": r.competition,
            "strategy": r.strategy,
            "n_sequences": r.n_sequences,
            "timestamp": r.timestamp,
            **r.scores,
        }
        leaderboard.append(entry)

    lb_path = out_path / "kaggle_leaderboard.json"
    lb_path.write_text(json.dumps(leaderboard, indent=2))

    # Also append to pipeline runs ledger
    ledger_path = out_path / "kaggle_scoring_ledger.jsonl"
    with open(ledger_path, "a") as f:
        for r in results:
            f.write(json.dumps({
                "event": "submission_scored",
                "competition": r.competition,
                "strategy": r.strategy,
                "scores": r.scores,
                "n_sequences": r.n_sequences,
                "timestamp": r.timestamp,
            }) + "\n")

    print(f"\n{'=' * 70}")
    print(f"  Leaderboard: {lb_path}")
    print(f"  Ledger:      {ledger_path}")
    print(f"  Total submissions scored: {len(results)}")
    print(f"{'=' * 70}")

    return results


if __name__ == "__main__":
    run_full_evaluation()
