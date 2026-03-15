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

---

## 2026-03-15 · GPU Loss & Reboot Postmortem

### What Happened

The RTX 4080 SUPER entered a fatal error state (`ERR!` in nvidia-smi) during a long session. CUDA became unavailable, all GPU workloads halted, and `torch.cuda.is_available()` returned `False`. The instance itself stayed running (SSH accessible, CPU services alive) but the GPU was bricked until a full instance stop/start cycle.

### Why We Lost GPU Access

1. **GPU entered Xid error state.** Likely triggered by sustained high-VRAM usage across 12 training runs, 7 web services, and concurrent notebook execution. Vast.ai consumer-tier GPUs don't have ECC memory — a single uncorrectable error can cascade into a driver-level lockout.
2. **No watchdog or memory pressure relief.** We had health checks for web services but nothing monitoring `nvidia-smi` for error states or VRAM pressure. By the time the error surfaced, the GPU was unrecoverable without a cold restart.
3. **Thermal/power throttling is invisible.** Vast.ai doesn't expose power limit or thermal data through their API. The GPU may have been throttling for a while before the hard fault.

### Why We Lost Access Entirely

4. **Instance API key can't restart itself.** The Vast.ai CLI running *on* the instance can't stop/start its own instance — that requires an account-level API key on an external machine (Mac or Contabo).
5. **No out-of-band restart path was pre-configured.** We had to manually SSH from another machine, run `vastai stop instance 32817406`, wait for shutdown, then `vastai start instance 32817406`.

### How We Rebooted

```bash
# From external machine (not the GPU instance itself):
vastai stop instance 32817406
# waited ~60s for state transition
vastai start instance 32817406
# waited for instance to come back online
ssh -p 19636 root@175.155.64.231
cd /workspace/backstage-server-lab
bash scripts/boot_all.sh
nvidia-smi  # confirm GPU healthy
```

The `/workspace` volume survived intact — no data loss. `boot_all.sh` brought all 7 services back up.

### How Prior Recovery Attempts Failed

- **`nvidia-smi -r` (driver reset):** "GPU reset not supported" on this card/driver combo.
- **Killing CUDA processes:** All `fuser /dev/nvidia*` kills completed, but the GPU stayed in ERR state. The error is at the driver level, not process level.
- **`rmmod nvidia && modprobe nvidia`:** Permission denied on Vast.ai containers — no kernel module access.
- **Waiting it out:** GPU error state does not self-heal. Unlike throttling, an Xid fault requires a cold power cycle.

### How to Anticipate & Prevent This

1. **GPU watchdog cron (add to `boot_all.sh`):**
   ```bash
   # every 2 min, check nvidia-smi exit code
   */2 * * * * nvidia-smi > /dev/null 2>&1 || \
     echo "GPU FAULT $(date)" >> /workspace/logs/gpu_watchdog.log
   ```
   This at least alerts early. Can't auto-restart from inside, but can trigger a webhook to Contabo.

2. **VRAM headroom policy:** Keep at least 2GB free. Before launching a new training run, check:
   ```bash
   free_mb=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
   [ "$free_mb" -lt 2048 ] && echo "WARN: low VRAM, defer new jobs"
   ```

3. **Pre-stage restart from Contabo:**
   ```bash
   # on Contabo, add a script: ~/restart-vast-gpu.sh
   #!/bin/bash
   vastai stop instance 32817406 && sleep 60 && vastai start instance 32817406
   ```
   Then from the GPU box (while it's still alive), you can trigger:
   ```bash
   ssh contabo 'bash ~/restart-vast-gpu.sh'
   ```

4. **Stagger GPU workloads.** Don't run 12 training experiments + live services simultaneously. Use a job queue or at minimum serialize training runs.

5. **Checkpoint aggressively.** Every 10 epochs, save to `/workspace/backstage-server-lab/artifacts/checkpoints/`. Our best model survived because we did this — but earlier runs didn't checkpoint and were lost.

6. **Monitor `dmesg` for Xid errors:**
   ```bash
   dmesg | grep -i xid  # early warning before full fault
   ```

### Key Takeaways

| Lesson | Action |
|--------|--------|
| GPU error ≠ process crash — can't fix from userspace | Always have an external restart path ready |
| /workspace volume is durable across stop/start | Don't panic about data, focus on getting GPU back |
| `boot_all.sh` is the critical recovery script | Keep it working, keep it committed |
| Consumer GPUs fault under sustained pressure | Build in VRAM guards and thermal awareness |
| Self-hosted restart is impossible on Vast.ai | Pre-stage `vastai` CLI + API key on Contabo |

---

### Next Session Priorities

- [x] Restart instance to fix GPU error state
- [ ] Add GPU watchdog cron to `boot_all.sh`
- [ ] Pre-stage restart script on Contabo
- [ ] Run improvement experiments on each baseline family
- [ ] Add MSA features to EGNN for better TM-score
- [ ] Wire real PDB data into training
- [ ] Build the ClojureScript notebook interface properly
- [ ] Deploy Cloudflare tunnel for non-mapped ports
- [ ] Connect to Contabo martial/viewer for cross-server integration
