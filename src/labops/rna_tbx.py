from __future__ import annotations

"""TensorBoard logging helpers for RNA training without TensorFlow runtime.

This module writes native TensorBoard event files through protobuf + EventFileWriter.
It supports scalars, histograms, PNG images, and hparams metadata.
"""

import io
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
from tensorboard.compat.proto import event_pb2, summary_pb2
from tensorboard.plugins.hparams import api_pb2, metadata, plugin_data_pb2
from tensorboard.summary.writer.event_file_writer import EventFileWriter


class RNALogger:
    """Structured TensorBoard logger for RNA experiments.

    Invariants
    ----------
    - Events are written under ``logdir/run_name``.
    - ``step`` is monotonically increasing within one run.
    - Histogram values are converted to float64 before binning.
    """

    def __init__(self, logdir: str | Path, run_name: str, flush_secs: int = 10) -> None:
        self.base = Path(logdir)
        self.run_name = run_name
        self.run_dir = self.base / run_name
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._writer = EventFileWriter(str(self.run_dir), max_queue_size=20, flush_secs=flush_secs)
        self._hparams_logged = False

    def close(self) -> None:
        self._writer.flush()
        self._writer.close()

    def __enter__(self) -> "RNALogger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _add_summary(self, summary: summary_pb2.Summary, step: int, wall_time: float | None = None) -> None:
        ev = event_pb2.Event(
            wall_time=time.time() if wall_time is None else float(wall_time),
            step=int(step),
            summary=summary,
        )
        self._writer.add_event(ev)

    def scalar(self, tag: str, value: float, step: int) -> None:
        """Log one scalar value."""
        val = summary_pb2.Summary.Value(tag=tag, simple_value=float(value))
        self._add_summary(summary_pb2.Summary(value=[val]), step=step)

    def scalars(self, values: dict[str, float], step: int) -> None:
        """Log multiple scalar tags in one event."""
        vals = [summary_pb2.Summary.Value(tag=k, simple_value=float(v)) for k, v in values.items()]
        self._add_summary(summary_pb2.Summary(value=vals), step=step)

    def histogram(self, tag: str, values: np.ndarray, step: int, bins: int = 30) -> None:
        """Log histogram from a numeric array."""
        arr = np.asarray(values, dtype=np.float64).ravel()
        if arr.size == 0:
            return
        counts, edges = np.histogram(arr, bins=bins)
        hist = summary_pb2.HistogramProto()
        hist.min = float(arr.min())
        hist.max = float(arr.max())
        hist.num = int(arr.size)
        hist.sum = float(arr.sum())
        hist.sum_squares = float(np.square(arr).sum())
        for e in edges[1:]:
            hist.bucket_limit.append(float(e))
        for c in counts:
            hist.bucket.append(float(c))
        val = summary_pb2.Summary.Value(tag=tag, histo=hist)
        self._add_summary(summary_pb2.Summary(value=[val]), step=step)

    def image(self, tag: str, png_bytes: bytes, step: int, height: int, width: int) -> None:
        """Log one PNG image payload."""
        img = summary_pb2.Summary.Image(encoded_image_string=png_bytes, height=int(height), width=int(width))
        val = summary_pb2.Summary.Value(tag=tag, image=img)
        self._add_summary(summary_pb2.Summary(value=[val]), step=step)

    def maybe_log_hparams(self, hparams: dict[str, Any], metric_tags: list[str], final_metrics: dict[str, float]) -> None:
        """Emit hparams experiment/session metadata + final metric points once per run."""
        if self._hparams_logged:
            return

        hparam_infos: list[api_pb2.HParamInfo] = []
        for k, v in hparams.items():
            if isinstance(v, bool):
                dt = api_pb2.DATA_TYPE_BOOL
            elif isinstance(v, (int, float)):
                dt = api_pb2.DATA_TYPE_FLOAT64
            else:
                dt = api_pb2.DATA_TYPE_STRING
            hparam_infos.append(api_pb2.HParamInfo(name=str(k), type=dt))

        metric_infos = [
            api_pb2.MetricInfo(name=api_pb2.MetricName(tag=t), dataset_type=api_pb2.DATASET_VALIDATION)
            for t in metric_tags
        ]
        experiment = api_pb2.Experiment(
            hparam_infos=hparam_infos,
            metric_infos=metric_infos,
            time_created_secs=time.time(),
        )

        exp_pd = plugin_data_pb2.HParamsPluginData(version=0, experiment=experiment)
        exp_md = metadata.create_summary_metadata(exp_pd)
        exp_val = summary_pb2.Summary.Value(tag=metadata.EXPERIMENT_TAG, metadata=exp_md)
        self._add_summary(summary_pb2.Summary(value=[exp_val]), step=0)

        ss = plugin_data_pb2.SessionStartInfo(start_time_secs=time.time())
        for k, v in hparams.items():
            if isinstance(v, bool):
                ss.hparams[str(k)].bool_value = bool(v)
            elif isinstance(v, (int, float)):
                ss.hparams[str(k)].number_value = float(v)
            else:
                ss.hparams[str(k)].string_value = str(v)
        ss_pd = plugin_data_pb2.HParamsPluginData(version=0, session_start_info=ss)
        ss_md = metadata.create_summary_metadata(ss_pd)
        ss_val = summary_pb2.Summary.Value(tag=metadata.SESSION_START_INFO_TAG, metadata=ss_md)
        self._add_summary(summary_pb2.Summary(value=[ss_val]), step=0)

        end_step = 0
        for tag, val in final_metrics.items():
            self.scalar(tag, float(val), step=end_step)

        success_enum = plugin_data_pb2.SessionEndInfo.DESCRIPTOR.fields_by_name["status"].enum_type.values_by_name[
            "STATUS_SUCCESS"
        ].number
        se = plugin_data_pb2.SessionEndInfo(status=success_enum, end_time_secs=time.time())
        se_pd = plugin_data_pb2.HParamsPluginData(version=0, session_end_info=se)
        se_md = metadata.create_summary_metadata(se_pd)
        se_val = summary_pb2.Summary.Value(tag=metadata.SESSION_END_INFO_TAG, metadata=se_md)
        self._add_summary(summary_pb2.Summary(value=[se_val]), step=end_step)

        self._hparams_logged = True


# ---- plotting helpers (optional matplotlib) ---------------------------------

def _fig_to_png(fig) -> bytes:
    import matplotlib.pyplot as plt

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    out = buf.getvalue()
    fig.clf()
    plt.close(fig)
    return out


def render_arc_diagram(seq: str, pair_prob: np.ndarray) -> tuple[bytes, int, int]:
    import matplotlib.pyplot as plt

    n = len(seq)
    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.set_title("RNA Arc Diagram")
    xs = np.arange(n)
    ax.scatter(xs, np.zeros(n), s=16, c="#e8a020")
    for i in range(n):
        for j in range(i + 1, n):
            p = float(pair_prob[i, j])
            if p < 0.30:
                continue
            mid = (i + j) / 2.0
            h = (j - i) * 0.12
            t = np.linspace(0, 1, 48)
            x = i * (1 - t) + j * t
            y = 4 * h * t * (1 - t)
            ax.plot(x, y, color="#49b072", alpha=min(0.95, 0.2 + p * 0.8), lw=0.8 + 2.2 * p)
    ax.set_ylim(-0.5, max(1.2, n * 0.08))
    ax.set_xlim(-1, n)
    ax.axis("off")
    png = _fig_to_png(fig)
    return png, 300, 900


def render_persistence_barcode(intervals: list[tuple[float, float]]) -> tuple[bytes, int, int]:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.set_title("Vietoris-Rips Persistence Barcode")
    for i, (b, d) in enumerate(intervals[:64]):
        ax.plot([b, d], [i, i], color="#50a8e0", lw=2)
    ax.set_xlabel("epsilon")
    ax.set_ylabel("feature")
    ax.grid(alpha=0.2)
    png = _fig_to_png(fig)
    return png, 300, 900


def render_dihedral_rose(dihedrals_deg: np.ndarray) -> tuple[bytes, int, int]:
    import matplotlib.pyplot as plt

    vals = np.asarray(dihedrals_deg, dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        vals = np.array([0.0])
    theta = np.deg2rad(vals)
    fig = plt.figure(figsize=(4.5, 4.5))
    ax = fig.add_subplot(111, projection="polar")
    bins = 36
    hist, edges = np.histogram(theta, bins=bins, range=(-math.pi, math.pi))
    widths = np.diff(edges)
    ax.bar(edges[:-1], hist, width=widths, color="#e05050", alpha=0.75, align="edge")
    ax.set_title("Dihedral Rose")
    png = _fig_to_png(fig)
    return png, 540, 540


def render_training_overview(epochs: np.ndarray, train_loss: np.ndarray, val_loss: np.ndarray) -> tuple[bytes, int, int]:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3.0))
    ax.plot(epochs, train_loss, label="train/loss", color="#e8a020", lw=2)
    ax.plot(epochs, val_loss, label="val/loss", color="#49b072", lw=2)
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right")
    ax.set_title("Training Overview")
    png = _fig_to_png(fig)
    return png, 320, 940


def render_folding_kinetics_timeline(time_axis: np.ndarray, populations: np.ndarray, labels: list[str]) -> tuple[bytes, int, int]:
    """Population vs time curves for macro-states."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3.0))
    for i, lb in enumerate(labels):
        ax.plot(time_axis, populations[i], lw=1.8, label=lb)
    ax.set_title("Folding Kinetics Timeline")
    ax.set_xlabel("time")
    ax.set_ylabel("population")
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", ncol=2, fontsize=8)
    png = _fig_to_png(fig)
    return png, 320, 940


def render_contact_evolution(contact_series: np.ndarray) -> tuple[bytes, int, int]:
    """Heat-style contact formation timeline."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3.0))
    ax.imshow(contact_series, aspect="auto", interpolation="nearest", cmap="viridis")
    ax.set_title("Contact Evolution Plot")
    ax.set_xlabel("time")
    ax.set_ylabel("contact index")
    png = _fig_to_png(fig)
    return png, 320, 940


def render_structure_distance_map(distance_matrix: np.ndarray) -> tuple[bytes, int, int]:
    """Pairwise structure distance matrix visual."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4.8, 4.4))
    im = ax.imshow(distance_matrix, interpolation="nearest", cmap="magma")
    ax.set_title("Structure Distance Map")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    png = _fig_to_png(fig)
    return png, 520, 560


def render_energy_vs_distance(dist: np.ndarray, energy: np.ndarray) -> tuple[bytes, int, int]:
    """Free-energy landscape cross section."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    ax.scatter(dist, energy, s=18, alpha=0.8, color="#e8a020")
    ax.set_title("Energy vs Structure Distance")
    ax.set_xlabel("distance from MFE")
    ax.set_ylabel("free energy")
    ax.grid(alpha=0.2)
    png = _fig_to_png(fig)
    return png, 360, 820


def render_markov_state_network(nodes_xy: np.ndarray, edges: list[tuple[int, int, float]]) -> tuple[bytes, int, int]:
    """Simple MSM network view (nodes + weighted edges)."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for a, b, w in edges:
        xa, ya = nodes_xy[a]
        xb, yb = nodes_xy[b]
        ax.plot([xa, xb], [ya, yb], color="#50a8e0", alpha=min(1.0, 0.25 + w), lw=1 + 2 * w)
    ax.scatter(nodes_xy[:, 0], nodes_xy[:, 1], s=120, c="#e05050", alpha=0.85)
    for i, (x, y) in enumerate(nodes_xy):
        ax.text(x + 0.01, y + 0.01, f"S{i}", fontsize=8, color="#d0d7e5")
    ax.set_title("Markov State Model Network")
    ax.set_xticks([])
    ax.set_yticks([])
    png = _fig_to_png(fig)
    return png, 420, 760


def render_folding_funnel(dist: np.ndarray, energy: np.ndarray) -> tuple[bytes, int, int]:
    """Funnel-like lower envelope over energy-distance cloud."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    ax.scatter(dist, energy, s=14, alpha=0.55, color="#49b072")
    d_grid = np.linspace(float(np.min(dist)), float(np.max(dist)), 120)
    env = np.array([np.min(energy[np.abs(dist - d) < 0.5]) if np.any(np.abs(dist - d) < 0.5) else np.nan for d in d_grid])
    mask = np.isfinite(env)
    ax.plot(d_grid[mask], env[mask], color="#e8a020", lw=2.2, label="funnel envelope")
    ax.set_title("Folding Funnel Diagram")
    ax.set_xlabel("conformational distance")
    ax.set_ylabel("free energy")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=8)
    png = _fig_to_png(fig)
    return png, 360, 820


def demo_write(logdir: str | Path, run_name: str = "demo_rna_run") -> dict[str, Any]:
    """Generate a synthetic run with scalars, histograms, images, and hparams."""
    rng = np.random.default_rng(42)
    seq = "".join(rng.choice(list("AUGC"), size=64))
    pair_prob = rng.random((64, 64))
    pair_prob = np.triu((pair_prob + pair_prob.T) / 2, 1)
    dihedrals = rng.normal(0, 65, size=220)
    intervals = sorted([(float(rng.uniform(0, 0.8)), float(rng.uniform(0.9, 2.2))) for _ in range(28)], key=lambda x: x[0])
    n_states = 6
    t = np.linspace(0.0, 1.0, 120)
    pops = np.vstack(
        [
            np.clip(np.exp(-5 * t), 0, 1),
            np.clip(0.1 + 0.7 * (1 - np.exp(-3 * t)), 0, 1),
            np.clip(0.2 * np.sin(3 * t) ** 2, 0, 1),
            np.clip(0.15 + 0.2 * np.sin(4 * t + 0.4) ** 2, 0, 1),
            np.clip(0.05 + 0.3 * (1 - np.exp(-2 * t)), 0, 1),
            np.clip(0.08 + 0.12 * np.cos(2 * t) ** 2, 0, 1),
        ]
    )
    pops = pops / np.maximum(1e-8, pops.sum(axis=0, keepdims=True))
    contact_series = rng.integers(0, 2, size=(40, t.size))
    dist = rng.integers(0, 25, size=220).astype(float)
    energy = -2.8 - 0.12 * dist + rng.normal(0, 1.4, size=dist.size)
    dmat = rng.uniform(0, 1, size=(32, 32))
    dmat = (dmat + dmat.T) / 2
    np.fill_diagonal(dmat, 0)
    nodes_xy = rng.uniform(0, 1, size=(n_states, 2))
    edges = [(i, (i + 1) % n_states, float(rng.uniform(0.2, 0.95))) for i in range(n_states)]

    with RNALogger(logdir=logdir, run_name=run_name) as tb:
        epochs = np.arange(1, 31)
        train = np.exp(-epochs / 14.0) + rng.normal(0, 0.015, size=epochs.size)
        val = np.exp(-epochs / 12.0) + 0.06 + rng.normal(0, 0.015, size=epochs.size)
        for ep in epochs:
            i = ep - 1
            metrics = {
                "train/loss": float(max(0.01, train[i])),
                "val/loss": float(max(0.01, val[i])),
                "metrics/pair_f1": float(np.clip(0.45 + 0.018 * ep + rng.normal(0, 0.02), 0, 1)),
                "metrics/pair_mcc": float(np.clip(0.35 + 0.016 * ep + rng.normal(0, 0.02), -1, 1)),
                "metrics/mae_pf": float(np.clip(0.38 - 0.009 * ep + rng.normal(0, 0.01), 0, 1)),
                "metrics/mae_nd": float(np.clip(0.52 - 0.012 * ep + rng.normal(0, 0.015), 0, 2)),
                "tda/h0_mean": float(np.clip(1.2 - 0.01 * ep + rng.normal(0, 0.01), 0, 5)),
                "tda/h0_std": float(np.clip(0.42 - 0.003 * ep + rng.normal(0, 0.005), 0, 2)),
                "tda/h1_mean": float(np.clip(0.65 + 0.004 * ep + rng.normal(0, 0.004), 0, 3)),
                "tda/h1_std": float(np.clip(0.18 + 0.003 * ep + rng.normal(0, 0.004), 0, 3)),
            }
            tb.scalars(metrics, step=ep)
            tb.histogram("tda/feature_distribution", rng.normal(0.0, 1.0 + ep * 0.02, size=256), step=ep)

            if ep % 5 == 0:
                arc, h, w = render_arc_diagram(seq=seq, pair_prob=pair_prob)
                tb.image("images/arc_diagram", arc, step=ep, height=h, width=w)
                bar, h, w = render_persistence_barcode(intervals=intervals)
                tb.image("images/persistence_barcode", bar, step=ep, height=h, width=w)
                rose, h, w = render_dihedral_rose(dihedrals_deg=dihedrals)
                tb.image("images/dihedral_rose", rose, step=ep, height=h, width=w)
                kin, h, w = render_folding_kinetics_timeline(time_axis=t, populations=pops, labels=[f"S{i}" for i in range(n_states)])
                tb.image("images/folding_kinetics_timeline", kin, step=ep, height=h, width=w)
                ce, h, w = render_contact_evolution(contact_series=contact_series)
                tb.image("images/contact_evolution", ce, step=ep, height=h, width=w)
                sdm, h, w = render_structure_distance_map(distance_matrix=dmat)
                tb.image("images/structure_distance_map", sdm, step=ep, height=h, width=w)
                evd, h, w = render_energy_vs_distance(dist=dist, energy=energy)
                tb.image("images/energy_vs_distance", evd, step=ep, height=h, width=w)
                msm, h, w = render_markov_state_network(nodes_xy=nodes_xy, edges=edges)
                tb.image("images/markov_state_network", msm, step=ep, height=h, width=w)
                fun, h, w = render_folding_funnel(dist=dist, energy=energy)
                tb.image("images/folding_funnel", fun, step=ep, height=h, width=w)
            if ep % 10 == 0:
                ov, h, w = render_training_overview(epochs[:ep], train[:ep], val[:ep])
                tb.image("images/training_overview", ov, step=ep, height=h, width=w)

        tb.maybe_log_hparams(
            hparams={"gc_bias": 0.52, "max_depth": 5, "wobble_rate": 0.12},
            metric_tags=["metrics/pair_f1", "metrics/pair_mcc", "metrics/mae_pf", "metrics/mae_nd"],
            final_metrics={
                "metrics/pair_f1": float(metrics["metrics/pair_f1"]),
                "metrics/pair_mcc": float(metrics["metrics/pair_mcc"]),
                "metrics/mae_pf": float(metrics["metrics/mae_pf"]),
                "metrics/mae_nd": float(metrics["metrics/mae_nd"]),
            },
        )

    return {"ok": True, "logdir": str(Path(logdir) / run_name), "epochs": 30}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Write synthetic RNA TensorBoard events")
    ap.add_argument("--logdir", default="/workspace/logs/rna")
    ap.add_argument("--run-name", default="demo_rna_run")
    args = ap.parse_args()
    out = demo_write(logdir=args.logdir, run_name=args.run_name)
    print(out)
