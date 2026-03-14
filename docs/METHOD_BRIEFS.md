# Method Briefs

Short implementation-oriented briefs for RNA bioinformatics methods.

## Brief 1: MSA/Covariation Prior
What:
1. Convert evolutionary couplings into pairwise priors.
Implementation:
1. Build MSA in preprocessing.
2. Extract coupling matrix.
3. Concatenate with pairwise model features.
Checks:
1. Coupling coverage by residue index.
1. Performance delta on long-range contacts.

## Brief 2: Template-First Hybrid
What:
1. Use template retrieval to bootstrap difficult structures.
Implementation:
1. Retrieve + align templates.
2. Generate TBM candidates.
3. Blend with model predictions and rerank.
Checks:
1. Template confidence logging.
1. Quality split by template-rich/template-poor targets.

## Brief 3: Recycling Refinement
What:
1. Iterative structure refinement to improve local geometry and contacts.
Implementation:
1. Recycle pairwise/structure states for N steps.
2. Stop early on stability threshold.
Checks:
1. Convergence behavior.
1. Gains vs compute cost.

## Brief 4: Confidence-Weighted Ensemble
What:
1. Ensemble multiple seeds/candidates using confidence weights.
Implementation:
1. Generate multi-seed candidates.
2. Compute per-residue confidence.
3. Blend candidates with confidence floor.
Checks:
1. Robustness on hard motifs.
1. Calibration error trend.

## Brief 5: Motif-Aware Evaluation
What:
1. Go beyond global metrics with motif/region-specific error analysis.
Implementation:
1. Build residue-level delta maps.
2. Tag helix/loop/non-canonical motif errors.
Checks:
1. Failure mode frequencies.
1. Improvement concentration zones.
