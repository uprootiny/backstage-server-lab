"""
rna_tbx.py — TensorBoard logging for RNA 3D training pipeline.

Self-contained writer using torch.utils.tensorboard (no TF dependency).
Logs scalars, histograms, images, and HParams for grammar config sweeps.

Usage:
    # As standalone demo writer:
    python3 rna_tbx.py /workspace/logs/rna

    # As library in training loops:
    from labops.rna_tbx import RNALogger
    with RNALogger("/workspace/logs/rna", run_name="gc0.52_d5") as logger:
        logger.log_epoch(epoch, train_loss, val_loss, metrics_dict)
"""
from __future__ import annotations

import math
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from torch.utils.tensorboard import SummaryWriter

# Plotting uses raw numpy array → image (no matplotlib needed for TensorBoard)
# But we'll use matplotlib if available for richer images
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


PHOSPHOR = {
    "bg": "#0d0f0e", "amber": "#e8a020", "jade": "#3dd68c",
    "crimson": "#e05050", "azure": "#50a8e0", "violet": "#b060e0",
    "cream": "#e8dfc8", "dim": "#3a3c38",
}
NUKE_COLOR = {"A": PHOSPHOR["jade"], "U": PHOSPHOR["crimson"],
              "G": PHOSPHOR["amber"], "C": PHOSPHOR["azure"]}


@dataclass
class RNALogger:
    """TensorBoard logger for RNA training runs."""
    log_dir: str
    run_name: str = "default"
    _writer: Optional[SummaryWriter] = None

    def __enter__(self):
        run_path = Path(self.log_dir) / self.run_name
        run_path.mkdir(parents=True, exist_ok=True)
        self._writer = SummaryWriter(str(run_path))
        return self

    def __exit__(self, *exc):
        if self._writer:
            self._writer.close()

    @property
    def writer(self) -> SummaryWriter:
        if self._writer is None:
            raise RuntimeError("Use RNALogger as context manager")
        return self._writer

    def log_epoch(self, epoch: int, train_loss: float, val_loss: float,
                  metrics: Optional[dict] = None):
        w = self.writer
        w.add_scalar("train/loss", train_loss, epoch)
        w.add_scalar("val/loss", val_loss, epoch)
        if metrics:
            for k, v in metrics.items():
                w.add_scalar(k, v, epoch)

    def log_tda_histogram(self, epoch: int, tda_feats: np.ndarray, tag="tda/features"):
        self.writer.add_histogram(tag, tda_feats, epoch)

    def log_grammar_hparams(self, hparam_dict: dict, metric_dict: dict):
        self.writer.add_hparams(hparam_dict, metric_dict)

    def log_arc_diagram(self, epoch: int, sequence: str, bracket: str,
                        tag="viz/arc_diagram"):
        if not HAS_MPL:
            return
        fig = _draw_arc_diagram(sequence, bracket)
        self.writer.add_figure(tag, fig, epoch)
        plt.close(fig)

    def log_persistence_barcode(self, epoch: int, dgm_H0, dgm_H1,
                                tag="viz/persistence_barcode"):
        if not HAS_MPL:
            return
        fig = _draw_persistence_barcode(dgm_H0, dgm_H1)
        self.writer.add_figure(tag, fig, epoch)
        plt.close(fig)

    def log_dihedral_rose(self, epoch: int, dihedrals: np.ndarray,
                          tag="viz/dihedral_rose"):
        if not HAS_MPL:
            return
        fig = _draw_dihedral_rose(dihedrals)
        self.writer.add_figure(tag, fig, epoch)
        plt.close(fig)

    def log_training_overview(self, epoch: int, train_losses: list, val_losses: list,
                              tag="viz/training_overview"):
        if not HAS_MPL:
            return
        fig = _draw_training_overview(train_losses, val_losses)
        self.writer.add_figure(tag, fig, epoch)
        plt.close(fig)


# ── Visualization helpers ────────────────────────────────────────────────────

def _setup_ax(ax, title=""):
    ax.set_facecolor(PHOSPHOR["bg"])
    ax.set_title(title, color=PHOSPHOR["cream"], fontsize=9)
    for spine in ax.spines.values():
        spine.set_color(PHOSPHOR["dim"])
    ax.tick_params(colors=PHOSPHOR["cream"])


def _draw_arc_diagram(sequence: str, bracket: str):
    n = len(sequence)
    fig, ax = plt.subplots(figsize=(10, 3), facecolor=PHOSPHOR["bg"])
    _setup_ax(ax, f"Arc Diagram (n={n})")

    # Draw backbone
    ax.plot(range(n), [0]*n, color=PHOSPHOR["dim"], linewidth=1, zorder=1)

    # Draw nucleotide dots
    for i, nt in enumerate(sequence):
        ax.scatter(i, 0, c=NUKE_COLOR.get(nt, PHOSPHOR["cream"]), s=15, zorder=3)

    # Draw arcs for base pairs
    stack = []
    for i, ch in enumerate(bracket):
        if ch == "(":
            stack.append(i)
        elif ch == ")" and stack:
            j = stack.pop()
            mid = (i + j) / 2
            width = i - j
            height = width / 3
            arc = matplotlib.patches.Arc(
                (mid, 0), width, height * 2,
                angle=0, theta1=0, theta2=180,
                color=PHOSPHOR["jade"], linewidth=0.8, alpha=0.7
            )
            ax.add_patch(arc)

    ax.set_xlim(-1, n)
    ax.set_ylim(-0.5, n/4)
    ax.set_xlabel("position", color=PHOSPHOR["cream"])
    ax.set_yticks([])
    plt.tight_layout()
    return fig


def _draw_persistence_barcode(H0, H1):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4), facecolor=PHOSPHOR["bg"])
    for ax, dgm, label, color in [
        (ax1, H0, "H0 (components)", PHOSPHOR["jade"]),
        (ax2, H1, "H1 (loops)", PHOSPHOR["crimson"]),
    ]:
        _setup_ax(ax, label)
        if dgm:
            for k, (b, d) in enumerate(sorted(dgm, key=lambda x: x[1]-x[0], reverse=True)[:30]):
                ax.barh(k, d - b, left=b, height=0.8, color=color, alpha=0.7)
            ax.set_xlabel("filtration", color=PHOSPHOR["cream"])
            ax.set_ylabel("feature", color=PHOSPHOR["cream"])
        else:
            ax.text(0.5, 0.5, "empty", ha="center", va="center",
                    color=PHOSPHOR["dim"], transform=ax.transAxes)
    plt.tight_layout()
    return fig


def _draw_dihedral_rose(dihedrals: np.ndarray):
    valid = dihedrals[~np.isnan(dihedrals)]
    fig = plt.figure(figsize=(5, 5), facecolor=PHOSPHOR["bg"])
    ax = fig.add_subplot(111, projection="polar")
    ax.set_facecolor(PHOSPHOR["bg"])
    if len(valid) > 0:
        angles = np.radians(valid)
        ax.hist(angles, bins=36, color=PHOSPHOR["violet"], alpha=0.7,
                edgecolor=PHOSPHOR["bg"])
    ax.set_title("Dihedral Rose", color=PHOSPHOR["cream"], fontsize=9, pad=15)
    ax.tick_params(colors=PHOSPHOR["cream"])
    ax.grid(True, alpha=0.2, color=PHOSPHOR["dim"])
    plt.tight_layout()
    return fig


def _draw_training_overview(train_losses, val_losses):
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=PHOSPHOR["bg"])
    _setup_ax(ax, "Training Overview")
    epochs = range(1, len(train_losses) + 1)
    ax.plot(epochs, train_losses, color=PHOSPHOR["amber"], label="train", linewidth=1.5)
    ax.plot(epochs, val_losses, color=PHOSPHOR["jade"], label="val", linewidth=1.5)
    ax.set_xlabel("epoch", color=PHOSPHOR["cream"])
    ax.set_ylabel("loss", color=PHOSPHOR["cream"])
    ax.set_yscale("log")
    ax.legend(framealpha=0.2, labelcolor=PHOSPHOR["cream"])
    ax.grid(True, alpha=0.15, color=PHOSPHOR["dim"])
    plt.tight_layout()
    return fig


# ── Demo writer (standalone) ─────────────────────────────────────────────────

def write_demo_run(log_dir: str):
    """Write a demo training run so TensorBoard has data on first launch."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from rna_3d_pipeline import (
        GrammarConfig, derive, build_record,
    )

    rng = np.random.default_rng(42)
    cfg = GrammarConfig(gc_bias=0.52, max_depth=5)

    # Generate a small corpus for demo
    corpus = []
    for k in range(24):
        local_rng = np.random.default_rng(seed=42 + k)
        motif = derive(local_rng, cfg)
        try:
            rec = build_record(motif)
            corpus.append(rec)
        except Exception:
            continue

    with RNALogger(log_dir, run_name="demo_gc0.52_d5") as logger:
        train_losses = []
        val_losses = []
        for epoch in range(1, 31):
            # Simulated training curve
            t_loss = 2.0 * math.exp(-0.08 * epoch) + 0.05 * rng.normal()
            v_loss = 1.8 * math.exp(-0.07 * epoch) + 0.03 * rng.normal()
            t_loss = max(0.01, t_loss)
            v_loss = max(0.01, v_loss)
            train_losses.append(t_loss)
            val_losses.append(v_loss)

            pf_mae = 0.15 * math.exp(-0.06 * epoch) + 0.02
            nd_mae = 8.0 * math.exp(-0.1 * epoch) + 0.5

            logger.log_epoch(epoch, t_loss, v_loss, {
                "metrics/mae_pf": pf_mae,
                "metrics/mae_nd": nd_mae,
                "tda/H0_mean_persistence": float(rng.normal(15, 2)),
                "tda/H1_mean_persistence": float(rng.normal(5, 1.5)),
            })

            # TDA histogram from real data
            if epoch % 5 == 0 and corpus:
                idx = epoch % len(corpus)
                rec = corpus[idx]
                logger.log_tda_histogram(epoch, rec.tda.feat)
                logger.log_arc_diagram(epoch, rec.secondary.motif.sequence,
                                       rec.secondary.bracket)
                logger.log_persistence_barcode(epoch, rec.tda.dgm.H0, rec.tda.dgm.H1)
                logger.log_dihedral_rose(epoch, rec.geometry.dihedrals)

            if epoch % 10 == 0:
                logger.log_training_overview(epoch, train_losses, val_losses)

        # HParams
        logger.log_grammar_hparams(
            {"gc_bias": cfg.gc_bias, "max_depth": cfg.max_depth, "wobble_p": cfg.wobble_p},
            {"hparam/final_val_loss": val_losses[-1], "hparam/final_mae_pf": pf_mae},
        )

    print(f"Demo run written to {log_dir}/demo_gc0.52_d5")


if __name__ == "__main__":
    logdir = sys.argv[1] if len(sys.argv) > 1 else "/workspace/logs/rna"
    write_demo_run(logdir)
