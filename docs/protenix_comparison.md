# ░░░ RNA Structure Prediction: Protenix & the Landscape ░░░

> A comparative analysis of Protenix (ByteDance's open-source AlphaFold3),
> the Grammar-EGNN pipeline used in this lab, and the broader ecosystem of
> RNA structure prediction methods.

---

## ░ Our Pipeline: Grammar-EGNN ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

### What It Is

A synthetic-data-driven pipeline for predicting **scalar structural properties**
of RNA (pairing fraction, nesting depth) using E(3)-equivariant graph neural
networks trained on grammar-generated molecules.

### Architecture

```
Stochastic Grammar (GrammarConfig)
  -> Nussinov DP (secondary structure)
  -> Frenet-Serret 3D geometry (coarse-grain coordinates)
  -> Vietoris-Rips persistence (TDA fingerprint)
  -> MolecularGraph (node_feats + edge_index + edge_feats + coords)
  -> EGNN (6 layers, 128-dim, E(3)-equivariant message passing)
  -> [pairing_fraction, max_nesting_depth]
```

### Characteristics

| Property | Value |
|---|---|
| **Data source** | Synthetic (stochastic context-free grammar) |
| **Alignment required** | None -- works from single sequence |
| **Secondary structure** | Nussinov DP, O(n^3), exact max-pairs |
| **3D geometry** | Frenet-Serret frame propagation, A-form helix + stochastic loops |
| **Shape descriptors** | Vietoris-Rips persistence homology (H0, H1 Betti curves) |
| **ML model** | EGNN (E(3)-equivariant GNN), ~250K parameters |
| **Training data size** | 256-1024 synthetic molecules |
| **Training compute** | Single GPU, 2-5 minutes |
| **Predictions** | Pairing fraction (mae < 0.04), nesting depth (mae < 1.0) |
| **Does NOT predict** | Full atomic coordinates, binding interfaces, dynamics |

### Strengths

- Fast iteration: generate data and train in minutes
- Fully interpretable pipeline: every stage has clear mathematical semantics
- No dependency on experimental databases
- TDA features provide rotation/translation-invariant structural descriptors
- E(3) equivariance baked into the architecture -- no data augmentation needed
- Grammar parameters (gc_bias, wobble_p, max_depth) give fine-grained control
  over the structural diversity of training data
- Good for studying the relationship between sequence features and structural
  properties in a controlled setting

### Limitations

- Synthetic data does not capture the full complexity of real RNA structures
- No pseudoknots (Nussinov algorithm produces nested structures only)
- Coarse-grain geometry -- not atomistic resolution
- Predicts aggregate properties, not per-residue or per-atom coordinates
- No thermodynamic energy model -- Nussinov maximizes pairs, not free energy
- Cannot handle protein-RNA complexes or ligand binding

---

## ░ Protenix (AlphaFold3-like) ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

### What It Is

**Protenix** is ByteDance's open-source reimplementation of AlphaFold3 (AF3),
the third generation of DeepMind's structure prediction system. It handles
proteins, RNA, DNA, ligands, and their complexes. The code is released under an
open license, making AF3-class predictions accessible to researchers without
DeepMind's proprietary infrastructure.

Repository: `github.com/bytedance/protenix`

### Architecture

Protenix follows the AF3 architecture:

1. **Input processing**: tokenize sequences (protein amino acids, RNA/DNA
   nucleotides, ligand atoms), compute MSA features from sequence databases
2. **Template search**: find homologous structures in PDB
3. **Pairformer**: evolved from AF2's Evoformer -- attention-based module that
   reasons jointly over single-residue representations and pairwise
   representations. Replaces AF2's MSA-based attention with a more efficient
   pairwise attention scheme.
4. **Diffusion module**: instead of AF2's structure module that iteratively
   refines coordinates, AF3/Protenix uses a **denoising diffusion** approach.
   Starting from Gaussian noise, a neural network iteratively denoises 3D
   coordinates conditioned on the Pairformer output. This is the key
   architectural change from AF2 to AF3.
5. **Confidence head**: predicts pLDDT (per-residue confidence), PAE (predicted
   aligned error), and ranking scores

### Characteristics

| Property | Value |
|---|---|
| **Data source** | PDB experimental structures (~200K structures) |
| **Alignment required** | MSA from sequence databases (UniRef, BFD, MGnify) |
| **Secondary structure** | Learned implicitly from data |
| **3D geometry** | Full atomic coordinates via diffusion |
| **ML model** | Pairformer + diffusion, ~100M+ parameters |
| **Training data size** | ~100K+ experimental structures |
| **Training compute** | Multi-GPU clusters, days to weeks |
| **Inference compute** | Single GPU, minutes per structure |
| **Predictions** | Full atomic 3D coordinates + confidence scores |
| **Handles** | Protein, RNA, DNA, ligands, ions, covalent modifications, complexes |

### Strengths

- State-of-the-art accuracy on protein structure prediction (CASP15 winner
  territory)
- Handles multi-chain complexes: protein-RNA, protein-DNA, protein-ligand
- Diffusion-based generation produces diverse conformational samples
- Open source with active development
- Confidence scores (pLDDT, PAE) calibrate prediction reliability
- Implicitly learns thermodynamic and evolutionary constraints from data

### Limitations

- Massive compute requirement for training (not feasible for most labs)
- MSA computation is itself expensive and requires large sequence databases
  (hundreds of GB)
- RNA prediction accuracy lags behind protein accuracy -- fewer RNA structures
  in PDB, less evolutionary signal in RNA MSAs
- Black-box: difficult to interpret what the model has learned
- Diffusion sampling introduces stochasticity -- multiple runs give different
  conformations (which is a feature for flexible regions, but noise for rigid
  ones)
- Ligand prediction accuracy is still limited compared to docking methods
- Requires careful template management to avoid data leakage in benchmarks

### Relation to Our Lab

Protenix solves a fundamentally different problem: full 3D coordinate prediction
from sequence, trained on experimental data. Our Grammar-EGNN pipeline predicts
structural properties from synthetic data. The approaches are complementary:

- **Protenix** answers: "Given this RNA sequence, what does the 3D structure look
  like at atomic resolution?"
- **Our pipeline** answers: "Given this RNA sequence, what are its aggregate
  structural characteristics (compactness, nesting complexity)?"

Our pipeline could serve as a **fast pre-screening** tool: quickly estimate
structural properties of thousands of sequences before investing Protenix compute
on the most interesting candidates. Our TDA features could also be used to
**validate** Protenix outputs -- do the predicted structures have the topological
signatures expected for a given sequence composition?

---

## ░ Alternative Approaches ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

### ViennaRNA

**What it does**: Thermodynamic RNA secondary structure prediction using nearest-
neighbor energy parameters.

| Property | Value |
|---|---|
| **Method** | Dynamic programming over the Turner energy model |
| **Compute cost** | O(n^3) time, O(n^2) memory; seconds for typical sequences |
| **Data requirements** | None (energy parameters from experimental thermodynamics) |
| **Predictions** | MFE structure, partition function, base pair probabilities, ensemble diversity |
| **Strengths** | Gold standard for secondary structure; well-calibrated probabilities via partition function; handles dangling ends, special loops, multi-loops; decades of validation |
| **Limitations** | Secondary structure only (no 3D); no pseudoknots in standard mode; energy parameters extrapolate poorly for long sequences; no protein context |

**Relation to our lab**: Our Nussinov algorithm is a simplified version of what
ViennaRNA does. Nussinov maximizes pair count; ViennaRNA minimizes free energy
using experimentally measured thermodynamic parameters. Replacing our Nussinov
step with ViennaRNA's `RNAfold` would give more physically realistic secondary
structures at the cost of slightly more complex integration (ViennaRNA is a C
library with Python bindings). The structural statistics we predict (pairing
fraction, nesting depth) could be computed from ViennaRNA output instead.

---

### RNAfold / LinearFold

**RNAfold** is ViennaRNA's flagship tool. **LinearFold** (Huang et al., 2019) is
a fast approximation.

| Property | RNAfold | LinearFold |
|---|---|---|
| **Method** | Exact DP (Zuker algorithm) | Left-to-right beam search approximation |
| **Compute cost** | O(n^3) time | O(n * b) time where b = beam width (effectively linear) |
| **Data requirements** | Turner energy parameters | Same |
| **Predictions** | MFE structure, pair probabilities | MFE structure (approximate) |
| **Strengths** | Exact; well-validated | 1000x faster for long sequences (>1000 nt); handles full viral genomes |
| **Limitations** | Slow for very long RNA (>5000 nt) | Approximate; can miss the true MFE; beam width is a tunable hyperparameter |

**Relation to our lab**: LinearFold could replace our Nussinov step for
generating secondary structures of long sequences during data generation. For our
typical sequence lengths (10-300 nt), the speed advantage is marginal, but for
scaling to full-length mRNA or lncRNA, LinearFold would be essential.

---

### RNA-FM (RNA Foundation Model)

**What it does**: Self-supervised language model pre-trained on millions of
non-coding RNA sequences.

| Property | Value |
|---|---|
| **Method** | Masked language modeling on RNA sequences (BERT-style) |
| **Compute cost** | Pre-training: multi-GPU, days. Fine-tuning/inference: single GPU, seconds |
| **Data requirements** | Pre-training: RNAcentral (~27M sequences). Fine-tuning: task-specific labels |
| **Predictions** | Sequence embeddings; fine-tuned for secondary structure, function, localization |
| **Strengths** | Transfer learning -- pre-train once, fine-tune for many tasks; captures evolutionary patterns without explicit MSA; fast inference |
| **Limitations** | Embeddings are not inherently 3D-aware; fine-tuning still needs labeled data; less accurate than physics-based methods for secondary structure; black-box representations |

**Relation to our lab**: RNA-FM embeddings could replace or augment our hand-
crafted node features (one-hot nucleotide + loop label + TDA). Instead of 16-dim
engineered features, each nucleotide would carry a ~640-dim contextual embedding
from the foundation model. This would likely improve predictions on real RNA data
but would require real RNA labels for fine-tuning, moving away from our synthetic-
only paradigm.

---

### RoseTTAFold2NA

**What it does**: Joint protein-nucleic acid structure prediction. Extension of
RoseTTAFold (Baker lab) to handle protein-RNA and protein-DNA complexes.

| Property | Value |
|---|---|
| **Method** | Three-track attention (1D sequence, 2D pairwise, 3D coordinate) with SE(3)-equivariant coordinate updates |
| **Compute cost** | Single GPU, minutes per complex; training requires multi-GPU cluster |
| **Data requirements** | PDB protein-NA complexes (~5K structures); MSAs for protein and RNA chains |
| **Predictions** | Full atomic coordinates of protein-RNA/DNA complexes |
| **Strengths** | Handles protein-nucleic acid interfaces; uses evolutionary information from both protein and RNA MSAs; open source (Baker lab) |
| **Limitations** | Fewer training structures than protein-only models; RNA-only prediction is less accurate than dedicated RNA tools; requires MSA computation for both chains |

**Relation to our lab**: RoseTTAFold2NA addresses the protein-RNA interface
prediction problem that is completely outside our pipeline's scope. If our lab
expands to study RNA-protein binding, RF2NA would be the natural starting point.
Our TDA features could potentially score or validate RF2NA's predicted complex
structures.

---

### EternaFold

**What it does**: RNA secondary structure prediction using parameters learned
from citizen science data.

| Property | Value |
|---|---|
| **Method** | Modified CONTRAfold (conditional log-linear model) with parameters trained on Eterna player data |
| **Compute cost** | O(n^3); comparable to ViennaRNA |
| **Data requirements** | Eterna game data (hundreds of thousands of player-designed RNA sequences with experimental SHAPE reactivity) |
| **Predictions** | Secondary structure, base pair probabilities |
| **Strengths** | Trained on diverse, experimentally validated human-designed sequences; often more accurate than ViennaRNA on designed RNAs; captures non-natural sequence distributions |
| **Limitations** | Less validated on natural RNA; citizen science data has its own biases; still O(n^3) |

**Relation to our lab**: EternaFold is an interesting data story -- using
gamification to generate training labels. Our grammar-based data generation is
philosophically similar: we generate diverse structures with known properties.
EternaFold's parameters could replace Turner parameters in a ViennaRNA-like
secondary structure predictor, potentially giving more accurate fold predictions
for the kinds of designed sequences our grammar produces.

---

### trRosettaRNA

**What it does**: RNA 3D structure prediction via transformer-based inter-residue
distance and orientation prediction, followed by energy minimization.

| Property | Value |
|---|---|
| **Method** | Transformer predicts distance/orientation distributions between residue pairs; restraint-guided folding via energy minimization (L-BFGS) |
| **Compute cost** | Single GPU for prediction, minutes; energy minimization on CPU, minutes to hours |
| **Data requirements** | RNA structures from PDB (~1K non-redundant); RNA MSAs from Rfam |
| **Predictions** | Full 3D coordinates (coarse-grain to all-atom) |
| **Strengths** | Explicit geometric reasoning via distance/orientation maps; interpretable intermediate predictions; works with shallow MSAs |
| **Limitations** | Smaller training set than protein methods; energy minimization can get stuck in local minima; MSA quality critical for accuracy |

**Relation to our lab**: trRosettaRNA's distance prediction approach is
conceptually related to our graph construction -- both reason about pairwise
relationships between residues. Our edge features encode pairwise distances and
edge types; trRosettaRNA predicts distance distributions. The key difference is
that trRosettaRNA uses predicted distances to build 3D coordinates via physical
energy minimization, while we use 3D coordinates as input features for property
prediction.

---

### ARES (Atomic Rotationally Equivariant Scorer)

**What it does**: Scores the quality of predicted RNA 3D structures using
rotationally equivariant neural networks.

| Property | Value |
|---|---|
| **Method** | SE(3)-equivariant neural network that scores 3D RNA structures (like a learned energy function) |
| **Compute cost** | Single GPU, seconds per structure |
| **Data requirements** | PDB RNA structures + decoy sets (computationally generated near-native structures) |
| **Predictions** | Quality score for a given 3D structure; can rank conformations |
| **Strengths** | Rotation/translation invariant by construction; fast scoring enables large-scale screening; differentiable -- can be used for gradient-based structure refinement |
| **Limitations** | Scorer only -- does not generate structures; needs a separate pipeline to produce candidate structures; trained on relatively small RNA structure dataset |

**Relation to our lab**: ARES is the closest architectural cousin to our EGNN.
Both use equivariant message passing on molecular graphs; both produce scalar
outputs from 3D molecular inputs. The difference is in the task:

- **ARES** takes a candidate 3D structure and predicts its quality (how close to
  the native structure)
- **Our EGNN** takes a graph with synthetic 3D coordinates and predicts
  structural properties (pairing fraction, nesting depth)

Our TDA features add a unique angle that ARES does not use -- persistent homology
captures global topological shape in a way that complements the local geometric
information in equivariant message passing. A hybrid approach (ARES-style scoring
+ TDA features) could be interesting.

---

## ░ Comparison Matrix ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

| Method | Compute | Data Needed | Predicts | 3D? | Handles RNA-Protein? |
|---|---|---|---|---|---|
| **Our Grammar-EGNN** | 1 GPU, minutes | None (synthetic) | Structural properties | Coarse-grain (input) | No |
| **Protenix (AF3)** | Multi-GPU, days (train) | PDB + MSA databases | Full atomic coords | Yes | Yes |
| **ViennaRNA** | CPU, seconds | None (energy params) | 2D structure, pair probs | No | No |
| **LinearFold** | CPU, milliseconds | None (energy params) | 2D structure (approx) | No | No |
| **RNA-FM** | 1 GPU, seconds (infer) | RNAcentral (pre-train) | Embeddings, fine-tuned tasks | No | No |
| **RoseTTAFold2NA** | 1 GPU, minutes | PDB complexes + MSAs | Full atomic coords (complex) | Yes | Yes |
| **EternaFold** | CPU, seconds | Eterna game data | 2D structure, pair probs | No | No |
| **trRosettaRNA** | 1 GPU + CPU hours | PDB RNA + Rfam MSAs | Full 3D coords | Yes | No |
| **ARES** | 1 GPU, seconds | PDB RNA + decoys | Quality score | Scores 3D | No |

---

## ░ Strategic Positioning ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

### Where Our Pipeline Fits

Our Grammar-EGNN pipeline occupies a unique niche: **fast, interpretable,
zero-data structural property prediction**. It is not trying to compete with
Protenix or trRosettaRNA on 3D coordinate accuracy. Instead, it provides:

1. **A training ground**: the synthetic pipeline lets you iterate on GNN
   architectures (EGNN layers, readout heads, loss functions) without waiting for
   data downloads or MSA computation. When an architecture works on synthetic
   data, transfer it to real data.

2. **A feature engineering testbed**: the TDA stage (Vietoris-Rips persistence,
   Betti curves) produces rotation-invariant shape descriptors that could augment
   any of the methods above. These features are novel in the RNA prediction
   space.

3. **A fast pre-filter**: before investing GPU-hours on Protenix or
   trRosettaRNA, screen thousands of candidate sequences with our pipeline to
   estimate structural compactness and complexity. Focus expensive 3D prediction
   on the sequences with the most interesting predicted properties.

4. **An educational tool**: the pipeline's modularity (grammar -> fold -> geometry
   -> TDA -> graph -> EGNN) makes each stage independently understandable and
   modifiable. This is valuable for onboarding researchers who need to understand
   equivariant GNNs, TDA, or RNA biology.

### Upgrade Paths

| Goal | Action |
|---|---|
| More realistic 2D structures | Replace Nussinov with ViennaRNA `RNAfold` |
| Handle longer sequences | Replace Nussinov with LinearFold |
| Richer node features | Replace one-hot + TDA with RNA-FM embeddings |
| Predict full 3D coordinates | Add coordinate loss, train on PDB RNA structures |
| Score predicted structures | Train ARES-style quality head alongside property head |
| Handle protein-RNA | Extend graph to multi-chain, use RF2NA-style architecture |
| Benchmark against SOTA | Submit to RNA-Puzzles or CASP-RNA evaluation |
