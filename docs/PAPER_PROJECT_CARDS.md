# RNA Paper Project Cards

Snappy cards for rapid method transfer into experiments.

## Card 1: DRfold (end-to-end + geometry restraints)
What:
1. Ab initio RNA 3D prediction combining frame learning and geometry constraints.
How:
1. Sequence features feed end-to-end coordinate/frame heads.
2. Geometric potentials regularize candidate structures.
Tricks:
1. Joint frame + geometry optimization.
1. Candidate generation plus scoring.
Tropes:
1. Deep prediction + structured refinement loop.
Reuse:
1. Add geometry-regularized loss branch in `transforms/geometry_head`.

## Card 2: RhoFold+ (RNA LM-conditioned folding)
What:
1. RNA 3D prediction with stronger language-model-style sequence priors.
How:
1. Encode sequence with RNA language features.
2. Decode to pairwise/3D structures with refinement.
Tricks:
1. Transfer from RNA pretraining.
1. Better long-range priors than plain token embeddings.
Tropes:
1. Foundation encoder + structure decoder.
Reuse:
1. Plug LM embeddings into `reps/sequence -> transforms/predict_geometry`.

## Card 3: NuFold (end-to-end tertiary structure modeling)
What:
1. End-to-end tertiary structure model for RNA coordinates.
How:
1. Internal geometric representations decode into 3D structures.
Tricks:
1. Architecture tuned for RNA-specific interactions.
Tropes:
1. Sequence-to-geometry-to-coordinate chain.
Reuse:
1. Benchmark against DRfold-like stack in run fabric.

## Card 4: UFold (secondary structure via image-like map)
What:
1. Fast RNA secondary structure prediction framed as image segmentation.
How:
1. Convert sequence relations into 2D maps and apply CNN-like inference.
Tricks:
1. Contact-map/image framing.
1. Efficient inference for large sets.
Tropes:
1. Strong 2D prior as foundation for harder 3D tasks.
Reuse:
1. Add as `infer_2d_prior` baseline to improve tertiary pipeline initialization.

## Card 5: RNA-Puzzles Round V Findings
What:
1. Blind benchmark showing persistent tertiary/generalization challenges.
How:
1. Compare methods on unseen targets and motif-level correctness.
Tricks:
1. Benchmark by motif and tertiary contact, not only global score.
Tropes:
1. “Good 2D != good 3D.”
Reuse:
1. Add motif error tags + tertiary contact metrics to evaluation harness.

## Card 6: CASP16 Nucleic Acid Assessment
What:
1. Blind-assessment evidence that template availability remains highly influential.
How:
1. Cross-method evaluation on difficult nucleic-acid targets.
Tricks:
1. Separate template-rich and template-scarce target analysis.
Tropes:
1. Hybrid template/de-novo remains pragmatic.
Reuse:
1. Keep TBM fallback as first-class branch in production inference.

## Card 7: Covariation + MSA Signal Integration
What:
1. Use multiple sequence alignments to infer evolutionary coupling constraints for RNA folds.
How:
1. Build/curate MSA.
2. Extract covariation signals.
3. Inject as priors into pairwise geometry or contact heads.
Tricks:
1. MSA depth filtering by quality.
1. Weighted coupling integration instead of hard constraints.
Tropes:
1. Evolutionary evidence as pairwise regularizer.
Reuse:
1. Add `protenix_prep_pipeline` + covariation features in preprocessing stage.

## Card 8: Template Retrieval and Alignment Pipeline
What:
1. Retrieve structurally similar templates to reduce search space on hard targets.
How:
1. Search sequence/template databases.
2. Align and score candidates.
3. Blend template-informed and de-novo candidates.
Tricks:
1. Top-k template blending with decay by alignment confidence.
1. Explicit fallback path when templates are low-confidence.
Tropes:
1. Hybrid template+model as practical SOTA pattern.
Reuse:
1. Keep TBM as first-stage branch and log template provenance.

## Card 9: Constraint-Augmented Folding
What:
1. Improve structure plausibility by adding external constraints (contacts, motifs, SHAPE-like proxies).
How:
1. Convert constraints to model-compatible tensors.
2. Apply during decoding or ranking.
Tricks:
1. Soft constraints with annealed weights.
1. Constraint conflict detection before final rank.
Tropes:
1. “Learned model + light physics/constraints.”
Reuse:
1. Integrate constraint channels in `predict_geometry` and candidate ranking.

## Tropes Library (cross-paper)
1. Foundation priors + geometry heads.
1. Multi-candidate generation then ranking.
1. Refinement/recycling loops.
1. Template-aware fallback.
1. Secondary-structure auxiliary supervision.
1. Confidence calibration as decision tool, not only output decoration.
1. MSA/covariation priors for pairwise constraints.
1. Constraint-aware decoding and reranking.

## Quick Recombination Ideas
1. `UFold-style 2D prior` + `DRfold-style geometry` + `TBM fallback`.
1. `RNA-LM embeddings` + `multi-seed sampling` + `confidence-weighted ensemble`.
1. `Motif-tagged evaluation` + `VOI scheduler` for efficient iteration.
