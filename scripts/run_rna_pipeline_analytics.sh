#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY_BIN="${PY_BIN:-python3}"
OUT_JSON="${1:-$ROOT_DIR/reports/rna_pipeline_analytics.json}"
OUT_MD="${2:-$ROOT_DIR/docs/RNA_PIPELINE_ANALYTICS.md}"
N_SAMPLES="${N_SAMPLES:-32}"

mkdir -p "$(dirname "$OUT_JSON")" "$(dirname "$OUT_MD")"

PYTHONPATH="$ROOT_DIR/src" "$PY_BIN" - <<'PY' "$OUT_JSON" "$OUT_MD" "$N_SAMPLES"
import json
import sys
from pathlib import Path
import numpy as np

from labops import rna_3d_pipeline as p

out_json = Path(sys.argv[1])
out_md = Path(sys.argv[2])
n_samples = int(sys.argv[3])

rng = np.random.default_rng(42)
corpus = [p.derive(rng, p.DEFAULT_CFG) for _ in range(n_samples)]
records = [p.build_record(m) for m in corpus]
model = p.EGNNModel.make(rng=rng)
out = model.forward(records[0].graph)

lens = np.array([r.secondary.motif.n for r in records])
pf = np.array([r.secondary.stats.pairing_fraction for r in records])
nd = np.array([r.secondary.stats.max_nesting_depth for r in records])
edge_counts = np.array([r.graph.edge_index.shape[1] for r in records])
node_dims = sorted(set(int(r.graph.node_feats.shape[1]) for r in records))
edge_dims = sorted(set(int(r.graph.edge_feats.shape[1]) for r in records))

invariants = {
    "node_dim_is_16": all(r.graph.node_feats.shape[1] == p.NODE_DIM for r in records),
    "edge_dim_is_9": all(r.graph.edge_feats.shape[1] == p.EDGE_DIM for r in records),
    "tda_dim_is_48": all(r.tda.feat.shape[0] == p.TDA_DIM for r in records),
    "no_nan_coords": all(not np.isnan(r.geometry.coords).any() for r in records),
    "no_nan_node_feats": all(not np.isnan(r.graph.node_feats).any() for r in records),
}

payload = {
    "samples": n_samples,
    "length": {"mean": float(lens.mean()), "std": float(lens.std()), "min": int(lens.min()), "max": int(lens.max())},
    "pairing_fraction": {"mean": float(pf.mean()), "std": float(pf.std()), "min": float(pf.min()), "max": float(pf.max())},
    "nesting_depth": {"mean": float(nd.mean()), "std": float(nd.std()), "min": int(nd.min()), "max": int(nd.max())},
    "graph_edges": {"mean": float(edge_counts.mean()), "std": float(edge_counts.std())},
    "node_dims": node_dims,
    "edge_dims": edge_dims,
    "egnn_probe": {
        "pred_pf": float(out.pred_pf),
        "pred_nd": float(out.pred_nd),
        "true_pf": float(records[0].secondary.stats.pairing_fraction),
        "true_nd": int(records[0].secondary.stats.max_nesting_depth),
    },
    "invariants": invariants,
}
out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

lines = [
    "# RNA Pipeline Analytics",
    "",
    f"- samples: {n_samples}",
    f"- length_mean_std: {payload['length']['mean']:.2f} ± {payload['length']['std']:.2f}",
    f"- pairing_fraction_mean_std: {payload['pairing_fraction']['mean']:.3f} ± {payload['pairing_fraction']['std']:.3f}",
    f"- nesting_depth_mean_std: {payload['nesting_depth']['mean']:.2f} ± {payload['nesting_depth']['std']:.2f}",
    f"- edge_count_mean_std: {payload['graph_edges']['mean']:.2f} ± {payload['graph_edges']['std']:.2f}",
    "",
    "## Invariants",
    "",
]
for k, v in invariants.items():
    lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")

lines += [
    "",
    "## EGNN Probe",
    "",
    f"- pred_pf={payload['egnn_probe']['pred_pf']:.4f} vs true_pf={payload['egnn_probe']['true_pf']:.4f}",
    f"- pred_nd={payload['egnn_probe']['pred_nd']:.4f} vs true_nd={payload['egnn_probe']['true_nd']}",
]
out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"analytics_json={out_json}")
print(f"analytics_md={out_md}")
print("invariants_ok=" + str(all(invariants.values())))
if not all(invariants.values()):
    raise SystemExit(5)
PY
