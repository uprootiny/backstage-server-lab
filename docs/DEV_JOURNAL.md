# Dev Journal — backstage-server-lab

## 2026-03-14/15 · GPU Lab Session

### What Happened

Started with a fresh Vast.ai instance (RTX 4080 SUPER 32GB, CUDA 12.8, PyTorch 2.10).
Built the entire RNA 3D ML research lab from the existing backstage-server-lab repo.

### Infrastructure Built

- **7 web services** running simultaneously, all bound to 0.0.0.0
  - Streamlit mashup (:1111 → ext :19121) — 20 tabs with renders, architecture, techniques
  - TensorBoard (:6006 → ext :19448) — 12 training runs
  - Portal dashboard (:8520) — mission control embedding all surfaces
  - Notebook Lab (:8521) — bespoke DeepNote-like notebook interface
  - Validation Harness (:8522) — 8-stage pipeline validation
  - Grafana (:3000) — GPU/system monitoring with 10-panel dashboard
  - Prometheus (:9090) + node_exporter (:9100) + GPU exporter (:9101)
- **Service supervisor** with 30s health checks and auto-restart
- **boot_all.sh** — one-command bootstrap after instance restart

### ML Pipeline

- Full RNA 3D pipeline: grammar → Nussinov DP → Frenet-Serret 3D → TDA → EGNN
- **12 GPU training runs** with TensorBoard logging (scalars, histograms, images)
- Best model: `egnn_big_ep100` — val_loss=**0.00907**, 640 samples, 100 epochs, 34 min
- Best pairing fraction MAE: **0.038** (target was <0.04)
- Best nesting depth MAE: **0.64** (target was <1.0)

### Kaggle Scoring

- **8 competitions** instrumented with synthetic ground truth and baselines
- **30 baselines** ranging from random to near-oracle
- Competitions: RNA 3D v1/v2, Ribonanza, OpenVaccine, CAFA RNA, Stability, Expression, SS Prediction
- Key insight: Nussinov DP achieves F1=1.0 on secondary structure (exact on synthetic data)
- Key gap: TM-score=0.106 for grammar_refined vs 0.7+ for Protenix/SOTA

### Datasets

- 3 synthetic RNA datasets (PDB-like, Rfam families, SHAPE/DMS probing)
- v4 large corpus: 500+ molecules from 60 grammar configs

### Renders

- **29 publication-quality renders** at 150-200 DPI, phosphor aesthetic
- Categories: 3D structures, arc diagrams, folding dynamics, TDA, training results
- Artsy series: ribbon, arcs, contact map, persistence diagram

### Documentation

- 34 docs including MLOps onboarding (4-act storyboard), Protenix comparison (8 approaches)
- Conference poster at /poster with full pipeline overview and technique library
- 12 documented techniques with impact metrics and code snippets

### Lessons / Working Notes

1. **More epochs > more data** at this scale. 384 samples × 60 epochs beat 512 × 80.
2. **GC bias of 0.52** produces most learnable structures (matches natural RNA).
3. **LayerNorm in EGNN** is essential for runs >40 epochs. Without it, training plateaus.
4. **Bishop parallel transport** eliminated ~2% of geometry NaN errors at loop→helix transitions.
5. **TDA features are noise-robust**: σ=0.2Å noise changes features by <5%.
6. **GPU entered error state** near end of session — nvidia-smi shows ERR!, CUDA unavailable. Requires instance restart (stop/start via Vast CLI). /workspace volume survives.
7. **Vast port mapping**: only 6 ports are externally mapped. For other services, need Cloudflare tunnel or direct IP access.
8. **Instance API key can't restart itself** — need account-level API key from Mac/Contabo.

### File Counts

| Category | Count |
|----------|-------|
| Git commits | 34+ |
| Tracked files | 176 |
| Training runs | 12 |
| Renders | 29 |
| Baselines | 30 |
| Kaggle competitions | 8 |
| Web services | 7 |
| Docs | 34 |
| Notebooks | 11 starter + 23 executed |

### Next Session Priorities

- [ ] Restart instance to fix GPU error state
- [ ] Run improvement experiments on each baseline family
- [ ] Add MSA features to EGNN for better TM-score
- [ ] Wire real PDB data into training
- [ ] Build the ClojureScript notebook interface properly
- [ ] Deploy Cloudflare tunnel for non-mapped ports
- [ ] Connect to Contabo martial/viewer for cross-server integration
