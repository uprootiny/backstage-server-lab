"""
baselines.py — Robust baseline suite for three experiment paths.

Each experiment path has 6-8 baselines ranging from trivial to informed:

  Path A: RNA 3D Structure Prediction (TM-score, lDDT)
  Path B: RNA Reactivity Prediction / Ribonanza (MAE)
  Path C: mRNA Degradation / OpenVaccine (MCRMSE)

Every baseline is deterministic (seeded), documented, and produces
a score that contextualizes what "good" means for each metric.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Optional

import numpy as np
from numpy.linalg import norm

# ═══════════════════════════════════════════════════════════════════════════════
# PATH A: RNA 3D Structure Prediction
# ═══════════════════════════════════════════════════════════════════════════════
#
# Metric: TM-score (0-1, higher=better), lDDT (0-1, higher=better)
#
# Baselines ordered from worst to best expected score:
#
# A0  random_sphere    — uniform points on unit sphere (no structure)
# A1  random_walk      — cumulative Gaussian walk (chain-like, no fold)
# A2  straight_helix   — A-form helix, ignoring secondary structure
# A3  nussinov_helix   — helix for paired, random for unpaired
# A4  grammar_coarse   — our Frenet-Serret pipeline, high noise
# A5  grammar_refined  — our pipeline, low noise (best non-oracle)
# A6  noisy_oracle_2A  — true coords + 2Å Gaussian noise
# A7  noisy_oracle_1A  — true coords + 1Å noise (near-perfect)

def _aform_helix(n: int, seed: int = 0) -> np.ndarray:
    """A-form RNA helix coordinates (rise=2.81, twist=32.7°, r=9.0)."""
    t = np.arange(n, dtype=float)
    return np.column_stack([
        9.0 * np.cos(t * math.radians(32.7)),
        9.0 * np.sin(t * math.radians(32.7)),
        t * 2.81,
    ])


def baseline_3d(gt: list[dict], strategy: str, seed: int = 42) -> list[dict]:
    """Generate 3D coordinate predictions for RNA 3D folding."""
    from labops.rna_3d_pipeline import (
        bracket_to_3d, nussinov, pairs_to_bracket, GrammarConfig,
    )
    rng = np.random.default_rng(seed)
    preds = []

    for item in gt:
        seq = item["sequence"]
        n = len(seq)

        if strategy == "random_sphere":
            # Points uniformly on sphere — no chain structure
            phi = rng.uniform(0, 2 * math.pi, n)
            costheta = rng.uniform(-1, 1, n)
            r = rng.uniform(5, 50, n)
            coords = np.column_stack([
                r * np.sqrt(1 - costheta**2) * np.cos(phi),
                r * np.sqrt(1 - costheta**2) * np.sin(phi),
                r * costheta,
            ])

        elif strategy == "random_walk":
            # Gaussian random walk — chain topology, no fold
            steps = rng.normal(0, 5.9, (n, 3))  # 5.9Å = P-P bond
            coords = np.cumsum(steps, axis=0)

        elif strategy == "straight_helix":
            # A-form helix along z-axis — ignores loops
            coords = _aform_helix(n)

        elif strategy == "nussinov_helix":
            # Fold with Nussinov, helix for stems, random for loops
            _, pairs = nussinov(seq)
            brk = pairs_to_bracket(n, pairs)
            paired = set()
            for i, j in pairs:
                paired.add(i)
                paired.add(j)
            helix_c = _aform_helix(n)
            # Jitter unpaired positions away from helix axis
            coords = helix_c.copy()
            for i in range(n):
                if i not in paired:
                    coords[i] += rng.normal(0, 8.0, 3)

        elif strategy == "grammar_coarse":
            # Our full pipeline, but high noise (0.8Å)
            brk = item.get("bracket", "." * n)
            if brk == "." * n:
                _, pairs = nussinov(seq)
                brk = pairs_to_bracket(n, pairs)
            coords = bracket_to_3d(brk, rng=np.random.default_rng(seed), noise=0.8)

        elif strategy == "grammar_refined":
            # Our full pipeline, low noise (0.1Å) — best non-oracle
            brk = item.get("bracket", "." * n)
            if brk == "." * n:
                _, pairs = nussinov(seq)
                brk = pairs_to_bracket(n, pairs)
            coords = bracket_to_3d(brk, rng=np.random.default_rng(seed), noise=0.1)

        elif strategy == "noisy_oracle_2A":
            coords = item["coords"] + rng.normal(0, 2.0, item["coords"].shape)

        elif strategy == "noisy_oracle_1A":
            coords = item["coords"] + rng.normal(0, 1.0, item["coords"].shape)

        else:
            coords = np.zeros((n, 3))

        preds.append({"id": item["id"], "coords": coords.astype(np.float32)})
    return preds


# ═══════════════════════════════════════════════════════════════════════════════
# PATH B: RNA Reactivity Prediction (Ribonanza)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Metric: MAE (lower=better). Winning scores ~0.12-0.15
#
# B0  random_uniform   — uniform [0, 1.5] (no signal)
# B1  constant_mean    — global mean of training set
# B2  gc_heuristic     — paired=low, unpaired=high based on GC
# B3  nussinov_binary  — fold with Nussinov, paired→0.15, unpaired→0.75
# B4  position_prior   — reactivity correlated with distance from ends
# B5  kmer_lookup      — 3-mer average reactivity table
# B6  noisy_oracle     — true + noise(σ=0.15)
# B7  oracle_tight     — true + noise(σ=0.05)

def _nussinov_paired_mask(seq: str) -> np.ndarray:
    """Return boolean mask: True where nucleotide is base-paired."""
    from labops.rna_3d_pipeline import nussinov
    n = len(seq)
    _, pairs = nussinov(seq)
    mask = np.zeros(n, dtype=bool)
    for i, j in pairs:
        mask[i] = mask[j] = True
    return mask


def baseline_ribonanza(gt: list[dict], strategy: str, seed: int = 42) -> list[dict]:
    """Generate reactivity predictions for Ribonanza."""
    rng = np.random.default_rng(seed)
    preds = []

    # Precompute global stats for constant_mean baseline
    all_dms = np.concatenate([item["dms_reactivity"] for item in gt])
    all_2a3 = np.concatenate([item["2a3_reactivity"] for item in gt])
    global_dms_mean = float(all_dms.mean())
    global_2a3_mean = float(all_2a3.mean())

    # Build k-mer lookup for kmer_lookup baseline
    kmer_table_dms = {}
    kmer_table_2a3 = {}
    for item in gt:
        seq = item["sequence"]
        for i in range(len(seq) - 2):
            kmer = seq[i:i+3]
            kmer_table_dms.setdefault(kmer, []).append(float(item["dms_reactivity"][i+1]))
            kmer_table_2a3.setdefault(kmer, []).append(float(item["2a3_reactivity"][i+1]))
    kmer_avg_dms = {k: np.mean(v) for k, v in kmer_table_dms.items()}
    kmer_avg_2a3 = {k: np.mean(v) for k, v in kmer_table_2a3.items()}

    for item in gt:
        seq = item["sequence"]
        n = len(seq)

        if strategy == "random_uniform":
            dms = rng.uniform(0, 1.5, n).astype(np.float32)
            a2a3 = rng.uniform(0, 1.2, n).astype(np.float32)

        elif strategy == "constant_mean":
            dms = np.full(n, global_dms_mean, dtype=np.float32)
            a2a3 = np.full(n, global_2a3_mean, dtype=np.float32)

        elif strategy == "gc_heuristic":
            dms = np.array([0.2 if c in "GC" else 0.7 for c in seq], dtype=np.float32)
            a2a3 = dms * 0.75

        elif strategy == "nussinov_binary":
            paired = _nussinov_paired_mask(seq)
            dms = np.where(paired, 0.15, 0.75).astype(np.float32)
            a2a3 = np.where(paired, 0.10, 0.55).astype(np.float32)

        elif strategy == "position_prior":
            # Ends tend to be more reactive (less structured)
            pos = np.arange(n, dtype=float)
            end_dist = np.minimum(pos, n - 1 - pos) / (n / 2)
            dms = (0.8 - 0.5 * end_dist + rng.normal(0, 0.05, n)).clip(0).astype(np.float32)
            a2a3 = (0.6 - 0.4 * end_dist + rng.normal(0, 0.04, n)).clip(0).astype(np.float32)

        elif strategy == "kmer_lookup":
            dms = np.full(n, global_dms_mean, dtype=np.float32)
            a2a3 = np.full(n, global_2a3_mean, dtype=np.float32)
            for i in range(1, n - 1):
                kmer = seq[i-1:i+2]
                if kmer in kmer_avg_dms:
                    dms[i] = kmer_avg_dms[kmer]
                    a2a3[i] = kmer_avg_2a3[kmer]

        elif strategy == "noisy_oracle":
            dms = (item["dms_reactivity"] + rng.normal(0, 0.15, n)).clip(0).astype(np.float32)
            a2a3 = (item["2a3_reactivity"] + rng.normal(0, 0.12, n)).clip(0).astype(np.float32)

        elif strategy == "oracle_tight":
            dms = (item["dms_reactivity"] + rng.normal(0, 0.05, n)).clip(0).astype(np.float32)
            a2a3 = (item["2a3_reactivity"] + rng.normal(0, 0.04, n)).clip(0).astype(np.float32)

        else:
            dms = np.zeros(n, dtype=np.float32)
            a2a3 = np.zeros(n, dtype=np.float32)

        preds.append({"id": item["id"], "dms": dms, "2a3": a2a3})
    return preds


# ═══════════════════════════════════════════════════════════════════════════════
# PATH C: mRNA Degradation Prediction (OpenVaccine)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Metric: MCRMSE (lower=better). Winning scores ~0.22-0.28
#
# C0  random_uniform   — uniform [0, 1.5]
# C1  constant_mean    — column-wise mean of training
# C2  gc_scaled        — GC content → stability → lower degradation
# C3  position_decay   — exponential decay from 5' end
# C4  structure_aware  — fold, paired=stable, unpaired=degraded
# C5  noisy_oracle     — true + noise(σ=0.20)
# C6  oracle_tight     — true + noise(σ=0.08)

def baseline_openvaccine(gt: list[dict], strategy: str, seed: int = 42) -> list[dict]:
    """Generate degradation predictions for OpenVaccine."""
    rng = np.random.default_rng(seed)

    # Column-wise means for constant_mean baseline
    all_targets = np.concatenate([item["targets"] for item in gt], axis=0)
    col_means = all_targets.mean(axis=0)

    preds = []
    for item in gt:
        seq = item["sequence"]
        n = len(seq)

        if strategy == "random_uniform":
            targets = rng.uniform(0, 1.5, (n, 5)).astype(np.float32)

        elif strategy == "constant_mean":
            targets = np.tile(col_means, (n, 1)).astype(np.float32)

        elif strategy == "gc_scaled":
            gc_local = np.array([
                sum(1 for c in seq[max(0, i-5):i+5] if c in "GC") / min(10, len(seq))
                for i in range(n)
            ])
            # Higher GC → more stable → lower degradation
            base = 0.8 - 0.6 * gc_local[:, None]
            targets = (base * np.ones((1, 5)) + rng.normal(0, 0.08, (n, 5))).clip(0).astype(np.float32)

        elif strategy == "position_decay":
            pos = np.arange(n, dtype=float) / n
            decay = np.exp(-2.0 * pos)
            targets = (decay[:, None] * np.ones((1, 5)) * 0.8 + rng.normal(0, 0.1, (n, 5))).clip(0).astype(np.float32)

        elif strategy == "structure_aware":
            paired = _nussinov_paired_mask(seq)
            base = np.where(paired, 0.3, 0.8)
            targets = (base[:, None] * np.ones((1, 5)) + rng.normal(0, 0.1, (n, 5))).clip(0).astype(np.float32)

        elif strategy == "noisy_oracle":
            targets = (item["targets"] + rng.normal(0, 0.20, (n, 5))).clip(0).astype(np.float32)

        elif strategy == "oracle_tight":
            targets = (item["targets"] + rng.normal(0, 0.08, (n, 5))).clip(0).astype(np.float32)

        else:
            targets = np.zeros((n, 5), dtype=np.float32)

        preds.append({"id": item["id"], "targets": targets})
    return preds


# ═══════════════════════════════════════════════════════════════════════════════
# Evaluation Runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_all_baselines(n_3d: int = 40, n_ribo: int = 80, n_vax: int = 40,
                      seed: int = 2026) -> dict:
    """Run all baselines across all three paths. Returns structured results."""
    import json
    from labops.kaggle_scoring import (
        generate_rna3d_ground_truth, generate_ribonanza_ground_truth,
        generate_openvaccine_ground_truth, score_rna3d, score_ribonanza,
        score_openvaccine,
    )

    results = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "paths": {}}

    # PATH A
    print("═" * 72)
    print("  PATH A: RNA 3D Structure Prediction")
    print("═" * 72)
    gt_3d = generate_rna3d_ground_truth(n_3d, seed=seed)
    print(f"  Ground truth: {len(gt_3d)} sequences")
    path_a = []
    for strat in ["random_sphere", "random_walk", "straight_helix",
                   "nussinov_helix", "grammar_coarse", "grammar_refined",
                   "noisy_oracle_2A", "noisy_oracle_1A"]:
        preds = baseline_3d(gt_3d, strat, seed=seed)
        r = score_rna3d(gt_3d, preds, strategy=strat)
        s = r.scores
        path_a.append({"strategy": strat, **s})
        print(f"  {strat:22s}  TM={s['tm_score_mean']:.4f}±{s['tm_score_std']:.4f}"
              f"  lDDT={s['lddt_mean']:.4f}  >{'.5'}={s['n_above_05']}/{r.n_sequences}")
    results["paths"]["rna_3d_folding"] = path_a

    # PATH B
    print()
    print("═" * 72)
    print("  PATH B: RNA Reactivity Prediction (Ribonanza)")
    print("═" * 72)
    gt_ribo = generate_ribonanza_ground_truth(n_ribo, seed=seed)
    print(f"  Ground truth: {len(gt_ribo)} sequences")
    path_b = []
    for strat in ["random_uniform", "constant_mean", "gc_heuristic",
                   "nussinov_binary", "position_prior", "kmer_lookup",
                   "noisy_oracle", "oracle_tight"]:
        preds = baseline_ribonanza(gt_ribo, strat, seed=seed)
        r = score_ribonanza(gt_ribo, preds, strategy=strat)
        s = r.scores
        path_b.append({"strategy": strat, **s})
        print(f"  {strat:22s}  DMS={s['mae_dms']:.4f}  2A3={s['mae_2a3']:.4f}"
              f"  overall={s['mae_overall']:.4f}")
    results["paths"]["ribonanza"] = path_b

    # PATH C
    print()
    print("═" * 72)
    print("  PATH C: mRNA Degradation (OpenVaccine)")
    print("═" * 72)
    gt_vax = generate_openvaccine_ground_truth(n_vax, seed=seed)
    print(f"  Ground truth: {len(gt_vax)} sequences")
    path_c = []
    for strat in ["random_uniform", "constant_mean", "gc_scaled",
                   "position_decay", "structure_aware",
                   "noisy_oracle", "oracle_tight"]:
        preds = baseline_openvaccine(gt_vax, strat, seed=seed)
        r = score_openvaccine(gt_vax, preds, strategy=strat)
        s = r.scores
        path_c.append({"strategy": strat, **s})
        print(f"  {strat:22s}  MCRMSE={s['mcrmse']:.4f}±{s['mcrmse_std']:.4f}")
    results["paths"]["openvaccine"] = path_c

    # Summary
    print()
    print("═" * 72)
    print("  BASELINE SUMMARY — What 'good' means for each metric")
    print("═" * 72)
    best_a = min(path_a, key=lambda x: -x["tm_score_mean"])
    worst_a = min(path_a, key=lambda x: x["tm_score_mean"])
    best_b = min(path_b, key=lambda x: x["mae_overall"])
    worst_b = max(path_b, key=lambda x: x["mae_overall"])
    best_c = min(path_c, key=lambda x: x["mcrmse"])
    worst_c = max(path_c, key=lambda x: x["mcrmse"])

    print(f"  RNA 3D:      random={worst_a['tm_score_mean']:.3f} → best baseline={best_a['tm_score_mean']:.3f} (TM-score)")
    print(f"  Ribonanza:   random={worst_b['mae_overall']:.3f} → best baseline={best_b['mae_overall']:.3f} (MAE)")
    print(f"  OpenVaccine: random={worst_c['mcrmse']:.3f} → best baseline={best_c['mcrmse']:.3f} (MCRMSE)")
    print(f"  Total: {len(path_a) + len(path_b) + len(path_c)} baselines across 3 experiment paths")
    print("═" * 72)

    # Save
    out = Path("artifacts/baseline_leaderboard.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"\n  Saved: {out}")

    return results


if __name__ == "__main__":
    run_all_baselines()
