# RNA Research Summaries

## 1. Approach Families

### A. Secondary-Structure First
1. Predict base-pairing / dot-bracket.
2. Convert to contact maps and coarse geometry.
3. Optionally lift to 3D coordinates.
Best for:
1. Fast baselines.
2. Interpretable failure modes in helix/loop regions.

### B. Pairwise Geometry First
1. Predict `L x L x d` pairwise tensors (distances/orientations/probabilities).
2. Decode to coordinates using reconstruction or diffusion heads.
Best for:
1. Mid/high-accuracy folding systems.
2. Better long-range interaction modeling.

### C. Coordinate Direct
1. Predict atom/backbone coordinates directly.
2. Use confidence heads and iterative refinement.
Best for:
1. End-to-end structure pipelines.
2. Submission-oriented Kaggle workflows.

### D. Hybrid Template + Model
1. Retrieve template/TBM candidates.
2. Blend with model predictions.
3. Fill unresolved regions with de-novo generation.
Best for:
1. Practical leaderboard robustness.
2. Hard-target fallback behavior.

## 2. Ontology (Project-Level)

### Core Entities
1. `competition`
2. `dataset`
3. `model`
4. `notebook`
5. `experiment`
6. `run`
7. `artifact`
8. `hypothesis`
9. `validation_spec`

### Core Relations
1. `uses_dataset`
2. `implements_model`
3. `evaluated_by`
4. `produces_artifact`
5. `supports_hypothesis`
6. `contradicts_hypothesis`
7. `derived_from`
8. `visualizable_as`

### Validation Ontology
1. `leaderboard_public_private`
2. `family_dropout`
3. `sequence_identity_dropout`
4. `motif_dropout`
5. `length_band_dropout`
6. `temporal_split`

## 3. Representation Lattice

### Canonical Records
1. `SequenceRecord`
2. `StructureRecord`
3. `RunRecord`

### Common Representation Types
1. `dot_bracket`
2. `contact_map`
3. `distance_matrix`
4. `pairwise_logits`
5. `torsion_angles`
6. `coarse_backbone`
7. `atom_coordinates`
8. `confidence_map`

### Key Transform Paths
1. `sequence -> pairwise_logits -> contact_map -> 3D coordinates`
2. `coordinates -> contact_map -> delta_against_reference`
3. `dot_bracket -> contact_map -> motif error analysis`

## 4. Known Tricks (High Reuse)

### Data and Validation
1. Family-aware splits to reduce homology leakage.
2. Hard-target replay sets for regression prevention.
3. Sequence-length curriculum.

### Modeling
1. Recycling/refinement loops.
2. Pairwise geometry heads.
3. Confidence calibration (`pLDDT`-like / B-factor mapping).
4. Mixed template + learned decoding.

### Inference and Ensembling
1. Multi-seed sampling.
2. Lightweight ensemble averaging.
3. Selective fallback to de-novo when templates fail.

### Submission Engineering
1. Stable output formatting checks.
2. Constraint clipping and post-hoc correction.
3. Deterministic run manifests and checksums.

## 5. Fancier Tricks (Advanced)

### Representation-Aware
1. Cross-representation consistency losses (`contact <-> coordinate`).
2. Confidence-aware reweighting per residue/motif.
3. Learned converters between output formats for model interoperability.

### Search and Optimization
1. VOI-driven experiment scheduling instead of grid-only sweeps.
2. Multi-objective tuning (`TM-score`, `lDDT`, cost, robustness).
3. Failure-cluster specific finetuning (loop drift vs helix collapse).

### Causal/Interpretability
1. Parameter impact traces through pipeline stages.
2. Motif-localized delta maps between runs.
3. Hypothesis evidence chains with contradictory run retention.

### Systems
1. Typed operator event streams (`infra|ingest|eval|anomaly`).
2. Run-fabric states including `stale` and `superseded`.
3. Automatic rerun suggestions weighted by VOI and cost.
