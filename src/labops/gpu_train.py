"""
gpu_train.py — PyTorch GPU training for RNA 3D structure prediction (EGNN)

Uses rna_3d_pipeline.py for data generation, trains a real EGNN on GPU.
"""
import time
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rna_3d_pipeline import (
    GrammarConfig, derive, build_record, MoleculeRecord,
    NODE_DIM, EDGE_DIM,
)
from rna_tbx import RNALogger

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ── Dataset ──────────────────────────────────────────────────────────────────

class RNAGraphDataset(Dataset):
    def __init__(self, records: list[MoleculeRecord]):
        self.records = records

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        r = self.records[idx]
        g = r.graph
        return {
            "node_feats": torch.from_numpy(g.node_feats),
            "edge_index": torch.from_numpy(g.edge_index).long(),
            "edge_feats": torch.from_numpy(g.edge_feats),
            "coords": torch.from_numpy(g.coords),
            "target_pf": torch.tensor(r.secondary.stats.pairing_fraction, dtype=torch.float32),
            "target_nd": torch.tensor(float(r.secondary.stats.max_nesting_depth), dtype=torch.float32),
            "n_nodes": g.node_feats.shape[0],
        }


def collate_graphs(batch):
    """Collate variable-size graphs into a single batched graph (PyG-style)."""
    node_feats, edge_index, edge_feats, coords = [], [], [], []
    target_pf, target_nd, batch_idx = [], [], []
    offset = 0
    for i, b in enumerate(batch):
        n = b["n_nodes"]
        node_feats.append(b["node_feats"])
        edge_index.append(b["edge_index"] + offset)
        edge_feats.append(b["edge_feats"])
        coords.append(b["coords"])
        target_pf.append(b["target_pf"])
        target_nd.append(b["target_nd"])
        batch_idx.append(torch.full((n,), i, dtype=torch.long))
        offset += n
    return {
        "node_feats": torch.cat(node_feats, dim=0),
        "edge_index": torch.cat(edge_index, dim=1),
        "edge_feats": torch.cat(edge_feats, dim=0),
        "coords": torch.cat(coords, dim=0),
        "target_pf": torch.stack(target_pf),
        "target_nd": torch.stack(target_nd),
        "batch": torch.cat(batch_idx),
    }


# ── Model ────────────────────────────────────────────────────────────────────

class EGNNLayerTorch(nn.Module):
    def __init__(self, d_h, d_e, d_msg):
        super().__init__()
        self.phi_e = nn.Sequential(
            nn.Linear(2 * d_h + 1 + d_e, d_msg), nn.SiLU(),
            nn.Linear(d_msg, d_msg), nn.SiLU(),
        )
        self.phi_h = nn.Sequential(
            nn.Linear(d_h + d_msg, d_h), nn.SiLU(),
            nn.Linear(d_h, d_h),
        )
        self.phi_x = nn.Sequential(
            nn.Linear(d_msg, d_msg), nn.SiLU(),
            nn.Linear(d_msg, 1),
        )
        self.norm = nn.LayerNorm(d_h)

    def forward(self, h, x, edge_index, edge_attr):
        src, dst = edge_index[0], edge_index[1]
        diff = x[src] - x[dst]
        sq_dist = (diff ** 2).sum(dim=-1, keepdim=True)
        msg_input = torch.cat([h[src], h[dst], sq_dist, edge_attr], dim=-1)
        msg = self.phi_e(msg_input)

        # Aggregate messages per node
        n = h.shape[0]
        agg = torch.zeros(n, msg.shape[1], device=h.device)
        count = torch.zeros(n, 1, device=h.device)
        agg.scatter_add_(0, dst.unsqueeze(1).expand_as(msg), msg)
        count.scatter_add_(0, dst.unsqueeze(1), torch.ones_like(dst.unsqueeze(1).float()))
        count = count.clamp(min=1)
        agg = agg / count

        h_new = self.norm(h + self.phi_h(torch.cat([h, agg], dim=-1)))

        weights = self.phi_x(msg)
        coord_upd = torch.zeros(n, 3, device=x.device)
        coord_upd.scatter_add_(0, src.unsqueeze(1).expand(-1, 3), diff * weights)
        coord_upd = coord_upd / count
        x_new = x + coord_upd

        return h_new, x_new


class EGNNModelTorch(nn.Module):
    def __init__(self, d_in=NODE_DIM, d_h=128, d_e=EDGE_DIM, d_msg=64, n_layers=6):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(d_in, d_h), nn.SiLU(),
            nn.Linear(d_h, d_h),
        )
        self.layers = nn.ModuleList([
            EGNNLayerTorch(d_h, d_e, d_msg) for _ in range(n_layers)
        ])
        self.readout = nn.Sequential(
            nn.Linear(d_h, d_h), nn.SiLU(),
            nn.Dropout(0.1),
            nn.Linear(d_h, d_h // 2), nn.SiLU(),
            nn.Linear(d_h // 2, 2),
        )

    def forward(self, batch):
        h = self.encoder(batch["node_feats"])
        x = batch["coords"].clone()
        ei = batch["edge_index"]
        ea = batch["edge_feats"]
        for layer in self.layers:
            h, x = layer(h, x, ei, ea)
        # Global mean pooling per graph
        batch_idx = batch["batch"]
        n_graphs = batch_idx.max().item() + 1
        graph_h = torch.zeros(n_graphs, h.shape[1], device=h.device)
        count = torch.zeros(n_graphs, 1, device=h.device)
        graph_h.scatter_add_(0, batch_idx.unsqueeze(1).expand_as(h), h)
        count.scatter_add_(0, batch_idx.unsqueeze(1), torch.ones(h.shape[0], 1, device=h.device))
        graph_h = graph_h / count.clamp(min=1)
        pred = self.readout(graph_h)
        return pred  # [:, 0] = pf logit, [:, 1] = nd log


# ── Data Generation ──────────────────────────────────────────────────────────

def generate_corpus(n_samples, configs=None, seed=42):
    rng = np.random.default_rng(seed)
    if configs is None:
        configs = [
            GrammarConfig(gc_bias=gc, max_depth=md, wobble_p=wp)
            for gc in [0.40, 0.52, 0.65]
            for md in [3, 5, 7]
            for wp in [0.05, 0.15]
        ]
    records = []
    per_cfg = max(1, n_samples // len(configs))
    for ci, cfg in enumerate(configs):
        for k in range(per_cfg):
            local_rng = np.random.default_rng(seed=seed + ci * 1000 + k)
            motif = derive(local_rng, cfg)
            try:
                rec = build_record(motif)
                if 10 <= rec.secondary.motif.n <= 300:
                    records.append(rec)
            except Exception:
                continue
    print(f"Generated {len(records)} valid molecules from {len(configs)} configs")
    return records


# ── Training Loop ────────────────────────────────────────────────────────────

def train(n_samples=512, n_epochs=50, batch_size=32, lr=3e-4,
          run_name="default", log_dir="/workspace/logs/rna"):
    print(f"\n{'='*60}")
    print(f"RNA 3D EGNN Training — PyTorch on {DEVICE}")
    print(f"{'='*60}")

    # Generate data
    t0 = time.time()
    records = generate_corpus(n_samples)
    print(f"Data generation: {time.time()-t0:.1f}s")

    # Split train/val
    n_val = max(1, len(records) // 5)
    val_records = records[:n_val]
    train_records = records[n_val:]
    print(f"Train: {len(train_records)}  Val: {len(val_records)}")

    train_ds = RNAGraphDataset(train_records)
    val_ds = RNAGraphDataset(val_records)
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_graphs)
    val_dl = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_graphs)

    # Model
    model = EGNNModelTorch(d_h=128, d_msg=64, n_layers=6).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Model params: {n_params:,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=n_epochs)

    best_val_loss = float("inf")
    ckpt_path = Path("/workspace/backstage-server-lab/artifacts/checkpoints")
    ckpt_path.mkdir(parents=True, exist_ok=True)

    print(f"\n{'Epoch':>5} {'Train Loss':>11} {'Val Loss':>11} {'Val MAE_pf':>10} {'Val MAE_nd':>10} {'Time':>6}")
    print("-" * 60)

    train_losses, val_losses = [], []

    with RNALogger(log_dir, run_name=run_name) as logger:
        for epoch in range(1, n_epochs + 1):
            t_epoch = time.time()

            # Train
            model.train()
            train_loss = 0.0
            n_train = 0
            for batch in train_dl:
                batch = {k: v.to(DEVICE) for k, v in batch.items()}
                pred = model(batch)
                pf_pred = torch.sigmoid(pred[:, 0])
                nd_pred = torch.exp(pred[:, 1].clamp(-10, 10))
                loss_pf = F.mse_loss(pf_pred, batch["target_pf"])
                loss_nd = F.mse_loss(nd_pred, batch["target_nd"])
                loss = loss_pf + 0.01 * loss_nd
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                train_loss += loss.item() * pf_pred.shape[0]
                n_train += pf_pred.shape[0]
            train_loss /= max(n_train, 1)

            # Val
            model.eval()
            val_loss = 0.0
            val_mae_pf = 0.0
            val_mae_nd = 0.0
            n_val_total = 0
            with torch.no_grad():
                for batch in val_dl:
                    batch = {k: v.to(DEVICE) for k, v in batch.items()}
                    pred = model(batch)
                    pf_pred = torch.sigmoid(pred[:, 0])
                    nd_pred = torch.exp(pred[:, 1].clamp(-10, 10))
                    loss_pf = F.mse_loss(pf_pred, batch["target_pf"])
                    loss_nd = F.mse_loss(nd_pred, batch["target_nd"])
                    loss = loss_pf + 0.01 * loss_nd
                    bs = pf_pred.shape[0]
                    val_loss += loss.item() * bs
                    val_mae_pf += (pf_pred - batch["target_pf"]).abs().sum().item()
                    val_mae_nd += (nd_pred - batch["target_nd"]).abs().sum().item()
                    n_val_total += bs
            val_loss /= max(n_val_total, 1)
            val_mae_pf /= max(n_val_total, 1)
            val_mae_nd /= max(n_val_total, 1)

            scheduler.step()
            dt = time.time() - t_epoch
            train_losses.append(train_loss)
            val_losses.append(val_loss)

            # TensorBoard logging
            logger.scalars({
                "train/loss": train_loss,
                "val/loss": val_loss,
                "metrics/mae_pf": val_mae_pf,
                "metrics/mae_nd": val_mae_nd,
                "lr": optimizer.param_groups[0]["lr"],
            }, step=epoch)

            # Histogram logging at intervals
            if epoch % 5 == 0 and records:
                rec = records[epoch % len(records)]
                logger.histogram("tda/features", rec.tda.feat, step=epoch)

            if epoch % 5 == 0 or epoch == 1:
                print(f"{epoch:5d} {train_loss:11.5f} {val_loss:11.5f} {val_mae_pf:10.4f} {val_mae_nd:10.2f} {dt:5.1f}s")

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(model.state_dict(), ckpt_path / "egnn_best.pt")

    # Final save
    torch.save(model.state_dict(), ckpt_path / "egnn_final.pt")
    print(f"\n{'='*60}")
    print(f"Training complete. Best val loss: {best_val_loss:.5f}")
    print(f"Checkpoints: {ckpt_path}")
    print(f"TensorBoard: {log_dir}/{run_name}")

    if torch.cuda.is_available():
        print(f"Peak GPU memory: {torch.cuda.max_memory_allocated()/1e9:.2f} GB")

    return model


def sweep(log_dir="/workspace/logs/rna"):
    """Run a 3-config sweep with TensorBoard logging."""
    configs = [
        ("gc0.40_d4_w0.08", dict(n_samples=256, n_epochs=30, run_name="gc0.40_d4_w0.08")),
        ("gc0.52_d5_w0.12", dict(n_samples=256, n_epochs=30, run_name="gc0.52_d5_w0.12")),
        ("gc0.65_d7_w0.15", dict(n_samples=256, n_epochs=30, run_name="gc0.65_d7_w0.15")),
    ]
    for name, kwargs in configs:
        print(f"\n>>> Sweep: {name}")
        train(log_dir=log_dir, **kwargs)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep", action="store_true", help="Run 3-config sweep")
    parser.add_argument("--samples", type=int, default=512)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--run-name", default="default")
    parser.add_argument("--log-dir", default="/workspace/logs/rna")
    args = parser.parse_args()
    if args.sweep:
        sweep(log_dir=args.log_dir)
    else:
        train(n_samples=args.samples, n_epochs=args.epochs, run_name=args.run_name,
              log_dir=args.log_dir)
