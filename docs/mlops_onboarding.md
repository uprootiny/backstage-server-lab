# ░░░ MLOps Onboarding: RNA Structure Prediction Lab ░░░

> A practical walkthrough for an ML researcher stepping into modern RNA 3D
> structure prediction on GPU infrastructure. This is the map of the territory
> -- where things are, how they connect, and how to run your first experiment.

---

## ░ Act 1: The Setup ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

### 1.1 The Machine

You are working on a **Vast.ai GPU instance** -- a rented cloud machine with an
NVIDIA GPU, typically an RTX 4090 or A6000. The instance is ephemeral: Vast.ai
can reclaim it, so all state that matters lives in git or gets synced off-box.

The instance exposes several services via mapped ports. The host IP is in the
Vast.ai dashboard; internal container ports map to external high-numbered ports.

| Internal Port | External Port (example) | Service |
|---|---|---|
| `8080` | `:19808` | **Jupyter Lab** -- 35+ notebooks, terminal access |
| `6006` | `:19448` | **TensorBoard** -- 9+ training runs with scalars, histograms, images |
| `1111` | `:19121` | **Streamlit dashboard** -- project cards, scores, observatory |
| `8520` | varies | **GPU Wrangler** -- browser-based training launcher |
| `8384` | `:19753` | **Syncthing** -- file synchronization |
| `22` | `:19636` | **SSH** -- direct terminal access |

SSH access:
```bash
ssh -i ~/.ssh/gpu_orchestra_ed25519 -p 19636 root@<VAST_IP>
```

Cloudflare tunnel URLs rotate. Check `docs/LIVE_ENDPOINTS.md` for the current
observatory URL.

### 1.2 TensorBoard at :19448

TensorBoard shows **9 training runs** across the `rna` log directory at
`/workspace/logs/rna/`. Each run is a subdirectory containing TensorBoard event
files written by `RNALogger` (defined in `src/labops/rna_tbx.py`).

What you see:
- **Scalars tab**: `train/loss`, `val/loss`, `metrics/mae_pf`, `metrics/mae_nd`,
  `tda/h0_mean`, `tda/h1_mean`, learning rate curves
- **Histograms tab**: `tda/feature_distribution` -- the distribution of
  topological descriptor values shifts as the model trains
- **Images tab**: arc diagrams, persistence barcodes, dihedral roses, folding
  kinetics timelines, contact evolution heatmaps, energy-distance scatter plots,
  Markov state model networks, and folding funnel diagrams
- **HParams tab**: hyperparameter comparison across runs (`gc_bias`,
  `max_depth`, `wobble_rate`) with metric columns

Runs are named by their grammar config, e.g., `gc0.52_d5_w0.12` encodes
`gc_bias=0.52`, `max_depth=5`, `wobble_p=0.12`.

### 1.3 Streamlit Dashboard at :19121

The Streamlit app (`src/labops/kaggle_mashup_app.py` and
`src/labops/research_library_app.py`) presents:
- **Project cards** for each research direction
- **Scoring model** outputs with numeric ratings
- **Notebook digest** linking to the 35+ Jupyter notebooks
- **Technique matrix** cross-referencing methods against datasets

### 1.4 Jupyter at :19808

The notebook server has 35+ notebooks spanning:
- Data exploration and Kaggle dataset ingestion
- RNA pipeline walkthroughs (`02_rna_3d_training_filled.ipynb`)
- Experiment harness demos
- Visualization prototypes
- Pipeline integration tests

### 1.5 Repo Structure

```
backstage-server-lab/
  src/
    labops/
      rna_3d_pipeline.py    # Core pipeline: grammar, Nussinov, geometry, TDA, graph, EGNN
      gpu_train.py           # PyTorch GPU training loop (the main training entry point)
      rna_tbx.py             # TensorBoard logging (RNALogger) + visualization renderers
      graph.py               # NetworkX graph export utilities
      experiment.py          # Experiment tracking
      runner.py              # Run orchestration
      validation.py          # Validation specs
      bench.py               # Benchmarking
      hypothesis.py          # Hypothesis management
      voi.py                 # Value-of-information surfaces
      techniques.py          # Technique registry
      rna_ingest.py          # RNA data ingestion
      notebook_ops.py        # Notebook operations
      harness/               # Evaluation harness (cache, registry, eval, submit, DAG)
      datasets/              # Kaggle dataset loaders
  web/
    gpu-wrangler/            # Browser-based GPU training launcher (Flask + JS)
    notebook-lab/            # Notebook lab interface
    portal/                  # Instance portal
  configs/                   # Configuration files
  artifacts/                 # Checkpoints, exported datasets, run manifests
  notebooks/                 # Jupyter notebooks (35+)
  experiments/               # Experiment definitions
  scripts/                   # Shell scripts for deploy, bootstrap, sync
  deploy/                    # Deployment configs
  observability/             # Prometheus, Grafana, health checks
  docs/                      # Documentation (you are here)
  logs/                      # TensorBoard event logs (on the instance at /workspace/logs/)
```

---

## ░ Act 2: The Pipeline ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

The RNA 3D prediction pipeline lives in `src/labops/rna_3d_pipeline.py`. It is a
five-stage pipeline that converts **nothing** (random seeds) into **graph-based
molecular representations** suitable for equivariant neural networks. Every stage
is deterministic given a seed.

### 2.1 Grammar-Based Sequence Generation

The pipeline starts with a **stochastic context-free grammar** that generates
realistic RNA motif structures. This is not real genomic data -- it is synthetic
data with controllable structural properties.

**`GrammarConfig`** controls the generative process:
- `gc_bias` (default 0.52): probability weight toward G/C nucleotides (affects
  thermodynamic stability)
- `wobble_p` (default 0.12): probability of G-U wobble pairs instead of
  Watson-Crick pairs
- `max_depth` (default 6): maximum recursion depth of nested motifs
- `p_iloop` (default 0.40): probability of generating an internal loop
- `p_bulge` (default 0.25): probability of generating a bulge
- `stem_min/stem_max`, `loop_min/loop_max`: size ranges for structural elements

**`derive(rng, cfg, depth=0)`** recursively generates a `Motif`:
1. At `max_depth`, always produce a **hairpin** (stem + loop + reverse-complement stem)
2. Otherwise, roll a random number:
   - `r < p_iloop`: wrap an inner motif in an **internal loop** (stem + asymmetric unpaired flanks + inner + flanks + stem)
   - `r < p_iloop + p_bulge`: wrap in a **bulge** (stem + one-sided unpaired insertion + inner + stem)
   - else: terminal **hairpin**
3. The grammar emits both the nucleotide **sequence** and the **dot-bracket** notation

The `Motif` dataclass carries: `sequence` (e.g., `"GCGAUUAGCGC"`), `bracket`
(e.g., `"(((...))).."`), `kind` (hairpin/stem), and `pairs` (list of `(i, j)`
base pair indices).

### 2.2 Nussinov DP Secondary Structure Prediction

**`nussinov(seq, min_loop=3)`** implements the classic Nussinov dynamic
programming algorithm for RNA secondary structure prediction:

- **Time complexity**: O(n^3) where n is sequence length
- **Optimality**: maximizes the total number of base pairs
- **Constraint**: minimum hairpin loop size of 3 (biological minimum)
- **Pairing rules**: Watson-Crick (A-U, G-C) plus G-U wobble pairs

The algorithm fills an n x n DP table where `dp[i,j]` = maximum pairs in
subsequence `seq[i..j]`. Traceback recovers the optimal pairing via `_trace()`.

Output: a `SecondaryRecord` containing the DP matrix, optimal pairs, dot-bracket
string, loop-type labels (stem/hairpin/internal/bulge/free), and
`StructuralStats`:
- `pairing_fraction`: fraction of nucleotides involved in base pairs (this is a
  training target)
- `max_nesting_depth`: deepest level of nested parentheses (this is a training
  target)
- `max_pair_span`: longest distance between paired nucleotides

### 2.3 Frenet-Serret Coarse-Grain 3D Geometry

The pipeline generates 3D coordinates using a **Frenet-Serret frame
propagation** scheme -- a differential geometry approach where a moving reference
frame (tangent T, normal N, binormal B) traces a curve through 3D space.

**`SE3Frame`** encapsulates a position + orientation in SE(3):
- `pos`: 3D position vector
- `T`: tangent direction (forward along the backbone)
- `N`: normal direction (perpendicular to T)
- `B`: binormal = T x N (completes the right-handed frame)
- `R`: rotation matrix [N | B | T]
- `apply(local_pt)`: transforms a point from local to world coordinates

**`helix_coords(n_residues, frame, params)`** generates A-form RNA helix geometry:
- A-form parameters: rise = 2.81 A, twist = 32.7 deg/residue, radius = 9.0 A
- Each residue traces a helical path: `(r*cos(phi), r*sin(phi), k*rise)`
- Returns coordinates + an updated SE3Frame at the helix exit

**`loop_coords(n_residues, frame, bond_len, kappa_mean, tau_std)`** generates
disordered loop regions using stochastic curvature:
- `kappa_mean=0.04`: mean curvature (low = nearly straight)
- `tau_std=0.08`: torsion noise standard deviation
- Each step: advance by `bond_len` along T, then perturb T toward N (curvature)
  and B (torsion)
- **Bishop parallel transport** (`bishop_transport`) rotates N to follow T
  without introducing twist artifacts

**`bracket_to_3d(bracket)`** scans the dot-bracket string for contiguous
segments of `(`, `)`, or `.`, assigns helix geometry to paired regions and loop
geometry to unpaired regions, then adds Gaussian noise (default sigma=0.2 A).

### 2.4 Topological Data Analysis (TDA)

TDA provides a **shape fingerprint** of the 3D structure that is invariant to
rotation and translation.

**`pairwise_dist(coords)`** computes the full n x n Euclidean distance matrix.

**`vietoris_rips(D, max_rad)`** builds a Vietoris-Rips filtration:
1. Sort all pairwise edges by distance
2. Use a **Union-Find** data structure to track connected components (H0
   features)
3. Track triangle closures to detect 1-cycles (H1 features)
4. Output: `PersistenceDiagram` with `H0` (connected components) and `H1`
   (loops) as lists of `(birth, death)` intervals

**`betti_curve(diagram, t)`** converts persistence intervals to a Betti curve:
at each threshold `t`, count how many features are alive (born before t, die
after t).

**`topo_features(dgm)`** produces a fixed-size feature vector (TDA_DIM = 48):
- 4 persistence statistics for H0: mean, std, max persistence, count
- 4 persistence statistics for H1: mean, std, max persistence, count
- 20-bin Betti curve for H0
- 20-bin Betti curve for H1

These 48 TDA features are injected into both node features and edge features of
the molecular graph.

### 2.5 Graph-Based ML Features

**`build_graph(sr, gr, tda)`** constructs a `MolecularGraph` suitable for graph
neural networks:

**Node features** (NODE_DIM = 16 per residue):
- Bits 0-3: one-hot nucleotide type (A, U, G, C)
- Bits 4-8: one-hot loop label (stem, hairpin, internal, bulge, free)
- Bits 9-11: centered + scaled 3D coordinates (x, y, z)
- Bits 12-15: top-4 TDA persistence statistics (normalized)

**Edge construction** -- four edge types:
1. **Backbone**: sequential neighbors (i, i+1)
2. **Watson-Crick**: A-U and G-C base pairs from Nussinov
3. **G-U wobble**: wobble base pairs
4. **Stacking**: spatially close paired residues within 8 positions and 15 A

**Edge features** (EDGE_DIM = 9 per edge):
- Bits 0-3: one-hot edge type
- Bit 4: normalized pairwise distance
- Bits 5-8: H1 TDA persistence statistics

Edges are bidirectional (both `(i,j)` and `(j,i)` are added).

### 2.6 EGNN Training (E(3)-Equivariant Message Passing)

The model is an **E(3)-equivariant graph neural network** (EGNN). E(3)
equivariance means the model's predictions are unchanged by rotations,
translations, and reflections of the input coordinates. This is a fundamental
symmetry of molecular systems -- a molecule's properties do not depend on how you
orient it in space.

**Architecture** (PyTorch implementation in `gpu_train.py`):

```
Input: node_feats (N, 16), coords (N, 3), edge_index (2, E), edge_feats (E, 9)
  |
  Encoder: Linear(16, 128) -> SiLU -> Linear(128, 128)
  |
  6x EGNN Layers:
    Message: phi_e([h_src, h_dst, ||x_src - x_dst||^2, edge_attr]) -> msg
    Aggregate: mean-pool messages per destination node
    Update h: LayerNorm(h + phi_h([h, agg]))
    Update x: x + mean(diff * phi_x(msg))  [coordinate refinement]
  |
  Global mean pool per graph
  |
  Readout: Linear(128, 128) -> SiLU -> Dropout(0.1) -> Linear(128, 64) -> SiLU -> Linear(64, 2)
  |
  Output: [sigmoid(logit_pf), exp(log_nd)]
```

Key design points:
- **Message function** `phi_e` takes the source and destination node embeddings,
  the squared distance between their coordinates, and the edge features. It does
  not use the raw coordinate difference vector, only its magnitude -- this is
  what makes it E(3)-equivariant.
- **Coordinate update** `phi_x` produces a scalar weight per message, which
  scales the coordinate difference vector. This refines positions while
  maintaining equivariance.
- **LayerNorm** after each node update stabilizes training.
- **Global mean pooling** aggregates per-node embeddings into a single
  graph-level vector, partitioned by batch index.

---

## ░ Act 3: Running Experiments ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

### 3.1 Launch a Training Run

SSH into the instance and run:

```bash
cd /workspace/backstage-server-lab
PYTHONPATH=src python3 src/labops/gpu_train.py \
    --samples 512 \
    --epochs 50 \
    --run-name my_first_run
```

What this does:
1. **Data generation** (~10-30s): creates 512 synthetic RNA molecules by
   sampling 18 grammar configs (3 gc_bias x 3 max_depth x 2 wobble_p), running
   Nussinov folding, generating 3D coordinates, computing TDA features, and
   building molecular graphs
2. **Train/val split**: 80/20 random split
3. **Model init**: 6-layer EGNN with ~250K parameters, AdamW optimizer (lr=3e-4,
   weight_decay=1e-4), cosine annealing LR schedule
4. **Training**: 50 epochs with gradient clipping (max norm 1.0)
5. **TensorBoard logging**: scalars every epoch, histograms every 5 epochs
6. **Checkpointing**: saves `egnn_best.pt` (best val loss) and `egnn_final.pt`

Typical training time: **2-5 minutes** on an RTX 4090 with 512 samples.

### 3.2 Run a Sweep

```bash
PYTHONPATH=src python3 src/labops/gpu_train.py --sweep
```

This runs 3 configurations sequentially:
- `gc0.40_d4_w0.08`: low GC bias, shallow depth, low wobble
- `gc0.52_d5_w0.12`: balanced (default-like)
- `gc0.65_d7_w0.15`: high GC bias, deep nesting, more wobble pairs

Each sweep leg uses 256 samples and 30 epochs. All three appear as separate runs
in TensorBoard.

### 3.3 Custom Log Directory

```bash
PYTHONPATH=src python3 src/labops/gpu_train.py \
    --samples 1024 \
    --epochs 100 \
    --run-name big_run_v2 \
    --log-dir /workspace/logs/rna_experiments
```

### 3.4 Reading TensorBoard Results

Open TensorBoard at the external port (e.g., `http://<VAST_IP>:19448`):

1. **Scalars**: compare `val/loss` curves across runs. Look for:
   - Smooth descent without spikes (good LR schedule)
   - Train/val gap (overfitting indicator)
   - `metrics/mae_pf` and `metrics/mae_nd` converging toward targets
2. **Histograms**: `tda/feature_distribution` should stabilize as the model
   learns -- early epochs show high variance, later epochs show tighter
   distributions
3. **Images**: check arc diagrams for realistic pairing patterns, persistence
   barcodes for topological features
4. **HParams**: sort runs by `metrics/mae_pf` to find the best grammar config

### 3.5 Checking Checkpoints

```bash
ls -la /workspace/backstage-server-lab/artifacts/checkpoints/
# egnn_best.pt   -- lowest val loss during training
# egnn_final.pt  -- state at last epoch
```

Load a checkpoint for inference:
```python
import torch
from labops.gpu_train import EGNNModelTorch
model = EGNNModelTorch()
model.load_state_dict(torch.load("artifacts/checkpoints/egnn_best.pt"))
model.eval()
```

### 3.6 GPU Wrangler at :8520

The GPU Wrangler (`web/gpu-wrangler/`) is a browser-based interface for
launching training runs without SSH:

1. Navigate to `http://<VAST_IP>:<wrangler_port>`
2. Set sample count, epochs, and run name in the form
3. Click "Launch" -- the Flask backend (`web/gpu-wrangler/api.py`) spawns a
   training subprocess
4. Monitor progress in the console output panel or switch to TensorBoard

This is useful for quick iteration when you want to kick off runs from a browser
tab.

---

## ░ Act 4: Understanding Results ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

### 4.1 Loss Function

The training loss is a weighted combination of two MSE terms:

```python
loss = MSE(sigmoid(pred_pf_logit), target_pf) + 0.01 * MSE(exp(pred_nd_log), target_nd)
```

- The pairing fraction prediction goes through a sigmoid (output in [0, 1])
- The nesting depth prediction goes through an exp (output > 0)
- The 0.01 weight on nesting depth reflects its larger numeric scale

### 4.2 val/loss

The validation loss tracks generalization. Because the data is synthetically
generated from a grammar, "generalization" means the model can predict structural
properties of molecules from grammar configs it was trained on but specific
sequences it has not seen.

Good training looks like:
- val/loss drops from ~0.02-0.05 to ~0.001-0.005 over 50 epochs
- Train/val gap stays small (synthetic data has low noise, so overfitting is
  primarily to sequence-specific artifacts)

### 4.3 mae_pf: Mean Absolute Error on Pairing Fraction

**What it is**: average absolute difference between predicted and true pairing
fraction across the validation set.

**Pairing fraction** = (number of nucleotides in base pairs) / (total
nucleotides). A fully paired RNA has pf = 1.0; a fully unpaired one has pf = 0.0.
Typical RNA molecules in this grammar have pf in the range 0.3-0.7.

**Target**: mae_pf < 0.04

This means the model predicts the fraction of paired nucleotides to within 4
percentage points on average. At this accuracy, the model has learned the
relationship between graph-level features (nucleotide composition, connectivity
pattern, TDA shape descriptors) and the overall structural compactness of the
molecule.

### 4.4 mae_nd: Mean Absolute Error on Max Nesting Depth

**What it is**: average absolute difference between predicted and true maximum
nesting depth.

**Max nesting depth** = deepest level of nested parentheses in the dot-bracket
notation. A simple hairpin has depth 1; a deeply nested pseudoknot-free structure
can have depth 6-7 in this grammar.

**Target**: mae_nd < 1.0

This means the model predicts the structural complexity (nesting hierarchy) to
within 1 level on average. Nesting depth is a harder target because it depends on
global structural topology, not just local features.

### 4.5 TDA Histograms

The `tda/feature_distribution` histogram in TensorBoard tracks the distribution
of topological features across the dataset at regular intervals during training.

What to look for:
- **Early epochs**: broad, noisy distribution -- the model has not yet learned
  which topological features are informative
- **Mid-training**: distribution begins to concentrate -- the model is learning
  to correlate topological shape descriptors with structural properties
- **Late epochs**: stable, peaked distribution -- convergence

The H0 (connected components) and H1 (loops) persistence statistics also appear
as separate scalar traces (`tda/h0_mean`, `tda/h1_mean`, etc.). H0 features
track backbone connectivity; H1 features track the topological loops created by
base pairing.

### 4.6 What the Metrics Do NOT Tell You

This pipeline predicts **scalar structural properties** (pairing fraction,
nesting depth), not full 3D coordinates. It answers "how compact and nested is
this RNA?" not "where is every atom?" That distinction is important:

- Low mae_pf means the model understands **structural compactness**
- Low mae_nd means the model understands **hierarchical folding topology**
- Neither means the model can predict a full 3D structure from sequence

For full 3D coordinate prediction, you would need to repurpose the EGNN's
coordinate refinement branch as the primary output, train on coordinate RMSD
loss, and likely need real experimental structures (PDB data) rather than
synthetic grammar data. That is the domain of tools like AlphaFold3/Protenix,
covered in the companion document `protenix_comparison.md`.

---

## ░ Appendix: Quick Reference ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

### Command Cheat Sheet

```bash
# Single training run
PYTHONPATH=src python3 src/labops/gpu_train.py --samples 512 --epochs 50 --run-name test_v1

# 3-config sweep
PYTHONPATH=src python3 src/labops/gpu_train.py --sweep

# Generate synthetic TensorBoard demo data
PYTHONPATH=src python3 src/labops/rna_tbx.py --logdir /workspace/logs/rna --run-name demo

# Export a dataset (no training)
PYTHONPATH=src python3 src/labops/rna_3d_pipeline.py

# Check GPU status
nvidia-smi

# Watch TensorBoard logs
ls /workspace/logs/rna/
```

### Key Files

| File | Purpose |
|---|---|
| `src/labops/rna_3d_pipeline.py` | Grammar, Nussinov, geometry, TDA, graph, EGNN (numpy) |
| `src/labops/gpu_train.py` | PyTorch GPU training loop |
| `src/labops/rna_tbx.py` | TensorBoard logging + visualization renderers |
| `web/gpu-wrangler/api.py` | GPU Wrangler Flask backend |
| `artifacts/checkpoints/` | Model checkpoints |
| `/workspace/logs/rna/` | TensorBoard event files |

### Glossary

| Term | Meaning |
|---|---|
| **EGNN** | E(3)-Equivariant Graph Neural Network |
| **Nussinov** | O(n^3) DP algorithm for RNA secondary structure (max base pairs) |
| **Frenet-Serret** | Moving reference frame (T, N, B) for tracing curves in 3D |
| **SE3Frame** | Position + orientation in the Special Euclidean group SE(3) |
| **TDA** | Topological Data Analysis -- shape descriptors from persistence homology |
| **Vietoris-Rips** | Filtration that builds simplicial complexes from distance thresholds |
| **Betti curve** | Count of topological features alive at each filtration threshold |
| **Pairing fraction** | Fraction of nucleotides involved in base pairs |
| **Nesting depth** | Deepest level of nested brackets in dot-bracket notation |
| **Dot-bracket** | String notation for RNA structure: `(` = paired left, `)` = paired right, `.` = unpaired |
| **GC bias** | Preference for G and C nucleotides (which form stronger base pairs) |
| **Wobble pair** | Non-standard G-U base pair (weaker than Watson-Crick) |
