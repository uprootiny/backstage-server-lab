"""
validation_harness.py — Local validation harness for RNA pipeline.

Runs end-to-end validation of the full pipeline:
  sequence generation → folding → 3D geometry → TDA → graph → EGNN → scoring

Serves a live validation dashboard on 0.0.0.0:8522 with:
  - Real-time validation progress
  - Per-stage timing and error rates
  - Kaggle scoring simulation
  - Comparison against baselines

Usage:
    python3 -m labops.validation_harness              # run validation
    python3 -m labops.validation_harness --serve       # run + serve dashboard
    python3 -m labops.validation_harness --quick       # fast 20-molecule check
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np

# Pipeline imports
from labops.rna_3d_pipeline import (
    GrammarConfig, derive, build_record, fold_motif, build_geometry,
    build_tda, build_graph, EGNNModel, MoleculeRecord, export_dataset,
)
from labops.kaggle_scoring import (
    tm_score, lddt_score, ribonanza_mae, mcrmse,
    generate_rna3d_ground_truth, baseline_rna3d, score_rna3d,
    generate_ribonanza_ground_truth, baseline_ribonanza, score_ribonanza,
    generate_openvaccine_ground_truth, baseline_openvaccine, score_openvaccine,
)


@dataclass
class StageResult:
    name: str
    status: str = "pending"  # pending, running, passed, failed, skipped
    duration_ms: float = 0.0
    n_items: int = 0
    errors: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


@dataclass
class ValidationReport:
    stages: list[StageResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    n_passed: int = 0
    n_failed: int = 0
    n_skipped: int = 0
    overall: str = "pending"
    timestamp: str = ""
    kaggle_scores: dict = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"{'='*65}",
            f"  VALIDATION REPORT — {self.timestamp}",
            f"{'='*65}",
            f"  Overall: {self.overall.upper()}",
            f"  Stages: {self.n_passed} passed, {self.n_failed} failed, {self.n_skipped} skipped",
            f"  Duration: {self.total_duration_ms:.0f}ms",
            "",
        ]
        for s in self.stages:
            icon = {"passed": "+", "failed": "X", "skipped": "-", "running": "~"}.get(s.status, "?")
            lines.append(f"  [{icon}] {s.name:30s} {s.status:8s} {s.duration_ms:7.0f}ms  n={s.n_items}")
            if s.errors:
                for e in s.errors[:3]:
                    lines.append(f"       ERROR: {e[:80]}")
            if s.metrics:
                for k, v in s.metrics.items():
                    lines.append(f"       {k}: {v}")
        if self.kaggle_scores:
            lines.append(f"\n  Kaggle Scores:")
            for comp, scores in self.kaggle_scores.items():
                lines.append(f"    {comp}:")
                for k, v in scores.items():
                    lines.append(f"      {k}: {v}")
        lines.append(f"{'='*65}")
        return "\n".join(lines)


def _run_stage(name: str, fn, report: ValidationReport, **kwargs) -> StageResult:
    """Run a validation stage, catching errors."""
    stage = StageResult(name=name, status="running")
    report.stages.append(stage)
    t0 = time.perf_counter()
    try:
        result = fn(**kwargs)
        stage.duration_ms = (time.perf_counter() - t0) * 1000
        stage.status = "passed"
        if isinstance(result, dict):
            stage.n_items = result.get("n_items", 0)
            stage.metrics = {k: v for k, v in result.items() if k != "n_items" and k != "data"}
            return stage
        stage.n_items = len(result) if hasattr(result, "__len__") else 0
        return stage
    except Exception as e:
        stage.duration_ms = (time.perf_counter() - t0) * 1000
        stage.status = "failed"
        stage.errors.append(str(e))
        report.n_failed += 1
        return stage


def run_validation(n_molecules: int = 100, seed: int = 42) -> ValidationReport:
    """Run full pipeline validation."""
    report = ValidationReport(timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    t_start = time.perf_counter()
    rng = np.random.default_rng(seed)

    # Stage 1: Grammar generation
    def stage_generate():
        configs = [
            GrammarConfig(gc_bias=gc, max_depth=md, wobble_p=wp)
            for gc in [0.40, 0.52, 0.65]
            for md in [3, 5, 7]
            for wp in [0.08, 0.15]
        ]
        motifs = []
        for i in range(n_molecules):
            cfg = configs[i % len(configs)]
            local = np.random.default_rng(seed=seed + i)
            m = derive(local, cfg)
            motifs.append(m)
        lens = [m.n for m in motifs]
        return {
            "n_items": len(motifs),
            "data": motifs,
            "len_mean": f"{np.mean(lens):.1f}",
            "len_range": f"[{min(lens)}, {max(lens)}]",
            "configs_used": len(configs),
        }

    s1 = _run_stage("1. Sequence Generation", stage_generate, report)
    motifs = s1.metrics.get("data", []) if s1.status == "passed" else []
    # Clean up data from metrics display
    if "data" in s1.metrics:
        del s1.metrics["data"]

    # Stage 2: Secondary structure folding
    def stage_fold():
        records = []
        errors = 0
        for m in motifs:
            try:
                sr = fold_motif(m)
                records.append(sr)
            except Exception:
                errors += 1
        pf_vals = [r.stats.pairing_fraction for r in records]
        return {
            "n_items": len(records),
            "data": records,
            "fold_errors": errors,
            "pairing_frac_mean": f"{np.mean(pf_vals):.3f}" if pf_vals else "n/a",
        }

    s2 = _run_stage("2. Nussinov Folding", stage_fold, report)
    sec_records = s2.metrics.pop("data", []) if s2.status == "passed" else []

    # Stage 3: 3D Geometry
    def stage_geometry():
        geo_records = []
        for sr in sec_records:
            gr = build_geometry(sr)
            geo_records.append((sr, gr))
        coord_sizes = [gr.coords.shape[0] for _, gr in geo_records]
        return {
            "n_items": len(geo_records),
            "data": geo_records,
            "coord_dim": "3",
            "total_atoms": sum(coord_sizes),
        }

    s3 = _run_stage("3. 3D Geometry (Frenet-Serret)", stage_geometry, report)
    geo_pairs = s3.metrics.pop("data", []) if s3.status == "passed" else []

    # Stage 4: TDA
    def stage_tda():
        tda_records = []
        for sr, gr in geo_pairs:
            tda = build_tda(gr)
            tda_records.append((sr, gr, tda))
        feat_dims = [t.feat.shape[0] for _, _, t in tda_records]
        return {
            "n_items": len(tda_records),
            "data": tda_records,
            "tda_feature_dim": feat_dims[0] if feat_dims else 0,
        }

    s4 = _run_stage("4. TDA Fingerprinting", stage_tda, report)
    tda_triples = s4.metrics.pop("data", []) if s4.status == "passed" else []

    # Stage 5: Graph construction
    def stage_graph():
        full_records = []
        for sr, gr, tda in tda_triples:
            g = build_graph(sr, gr, tda)
            full_records.append(MoleculeRecord(secondary=sr, geometry=gr, tda=tda, graph=g))
        node_counts = [r.graph.node_feats.shape[0] for r in full_records]
        edge_counts = [r.graph.edge_index.shape[1] for r in full_records]
        return {
            "n_items": len(full_records),
            "data": full_records,
            "mean_nodes": f"{np.mean(node_counts):.1f}",
            "mean_edges": f"{np.mean(edge_counts):.1f}",
        }

    s5 = _run_stage("5. Graph Construction", stage_graph, report)
    full_records = s5.metrics.pop("data", []) if s5.status == "passed" else []

    # Stage 6: EGNN forward pass
    def stage_egnn():
        model = EGNNModel.make(rng=np.random.default_rng(seed))
        preds = []
        for r in full_records[:20]:  # test on first 20
            out = model.forward(r.graph)
            preds.append({
                "pred_pf": out.pred_pf,
                "true_pf": r.secondary.stats.pairing_fraction,
                "pred_nd": out.pred_nd,
                "true_nd": float(r.secondary.stats.max_nesting_depth),
            })
        mae_pf = np.mean([abs(p["pred_pf"] - p["true_pf"]) for p in preds])
        mae_nd = np.mean([abs(p["pred_nd"] - p["true_nd"]) for p in preds])
        return {
            "n_items": len(preds),
            "mae_pf": f"{mae_pf:.4f}",
            "mae_nd": f"{mae_nd:.2f}",
            "note": "untrained model (random weights)",
        }

    s6 = _run_stage("6. EGNN Forward Pass", stage_egnn, report)

    # Stage 7: Dataset export
    def stage_export():
        if full_records:
            out_path = "/tmp/validation_corpus.npz"
            export_dataset(full_records, out_path)
            size_kb = Path(out_path).stat().st_size / 1024
            return {"n_items": len(full_records), "file": out_path, "size_kb": f"{size_kb:.1f}"}
        return {"n_items": 0, "skipped": "no records"}

    _run_stage("7. Dataset Export", stage_export, report)

    # Stage 8: Kaggle scoring
    def stage_kaggle():
        gt = generate_rna3d_ground_truth(n_sequences=20, seed=seed)
        preds = baseline_rna3d(gt, strategy="grammar_egnn")
        r = score_rna3d(gt, preds, strategy="grammar_egnn")
        report.kaggle_scores["rna3d_grammar_egnn"] = r.scores

        gt_r = generate_ribonanza_ground_truth(n_sequences=20, seed=seed)
        preds_r = baseline_ribonanza(gt_r, strategy="gc_heuristic")
        rr = score_ribonanza(gt_r, preds_r, strategy="gc_heuristic")
        report.kaggle_scores["ribonanza_gc_heuristic"] = rr.scores

        gt_v = generate_openvaccine_ground_truth(n_sequences=20, seed=seed)
        preds_v = baseline_openvaccine(gt_v, strategy="mean_fill")
        rv = score_openvaccine(gt_v, preds_v, strategy="mean_fill")
        report.kaggle_scores["openvaccine_mean_fill"] = rv.scores

        return {"n_items": 3, "competitions_scored": 3}

    _run_stage("8. Kaggle Scoring", stage_kaggle, report)

    # Finalize
    report.total_duration_ms = (time.perf_counter() - t_start) * 1000
    report.n_passed = sum(1 for s in report.stages if s.status == "passed")
    report.n_failed = sum(1 for s in report.stages if s.status == "failed")
    report.n_skipped = sum(1 for s in report.stages if s.status == "skipped")
    report.overall = "PASSED" if report.n_failed == 0 else "FAILED"

    return report


def serve_dashboard(report: ValidationReport, port: int = 8522):
    """Serve a live validation dashboard."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
    except ImportError:
        print("FastAPI not available, printing report instead:")
        print(report.summary())
        return

    app = FastAPI(title="Validation Harness")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/validation")
    async def get_report():
        stages = []
        for s in report.stages:
            stages.append({
                "name": s.name, "status": s.status,
                "duration_ms": s.duration_ms, "n_items": s.n_items,
                "errors": s.errors, "metrics": s.metrics,
            })
        return {
            "stages": stages,
            "overall": report.overall,
            "total_duration_ms": report.total_duration_ms,
            "n_passed": report.n_passed,
            "n_failed": report.n_failed,
            "kaggle_scores": report.kaggle_scores,
            "timestamp": report.timestamp,
        }

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        stages_html = ""
        for s in report.stages:
            color = {"passed": "#3dd68c", "failed": "#e05050", "skipped": "#666"}.get(s.status, "#e8a020")
            icon = {"passed": "&#x2713;", "failed": "&#x2717;", "skipped": "&#x2014;"}.get(s.status, "&#x25CF;")
            metrics_html = "".join(f"<div class='metric'>{k}: {v}</div>" for k, v in s.metrics.items())
            errors_html = "".join(f"<div class='error'>{e}</div>" for e in s.errors[:3])
            stages_html += f"""
            <div class='stage' style='border-left: 3px solid {color}'>
                <div class='stage-header'>
                    <span style='color:{color}'>{icon}</span>
                    <span class='stage-name'>{s.name}</span>
                    <span class='stage-status' style='color:{color}'>{s.status}</span>
                    <span class='stage-time'>{s.duration_ms:.0f}ms</span>
                    <span class='stage-count'>n={s.n_items}</span>
                </div>
                {metrics_html}{errors_html}
            </div>"""

        kaggle_html = ""
        for comp, scores in report.kaggle_scores.items():
            rows = "".join(f"<tr><td>{k}</td><td>{v:.4f}</td></tr>" for k, v in scores.items() if isinstance(v, (int, float)))
            kaggle_html += f"<h4>{comp}</h4><table class='score-table'>{rows}</table>"

        return f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Validation Harness</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0c10;color:#e8dfc8;font-family:monospace;padding:24px}}
h1{{color:#e8a020;font-size:18px;margin-bottom:4px}}
h2{{color:#e8a020;font-size:14px;margin:20px 0 10px}}
h4{{color:#50a8e0;font-size:12px;margin:12px 0 6px}}
.overall{{font-size:24px;font-weight:bold;margin:8px 0 16px;color:{'#3dd68c' if report.overall=='PASSED' else '#e05050'}}}
.stats{{font-size:12px;color:#888;margin-bottom:16px}}
.stage{{background:#0f1218;border-radius:6px;padding:12px;margin-bottom:8px}}
.stage-header{{display:flex;gap:12px;align-items:center;font-size:12px}}
.stage-name{{flex:1;font-weight:bold}}
.stage-status{{width:60px}}
.stage-time{{width:70px;text-align:right;color:#888}}
.stage-count{{width:50px;text-align:right;color:#666}}
.metric{{font-size:11px;color:#50a8e0;margin:4px 0 0 24px}}
.error{{font-size:11px;color:#e05050;margin:4px 0 0 24px}}
.score-table{{font-size:11px;margin:4px 0 12px;border-collapse:collapse}}
.score-table td{{padding:2px 12px;border-bottom:1px solid #1e2430}}
</style></head>
<body>
<h1>RNA Pipeline Validation Harness</h1>
<div class='overall'>{report.overall}</div>
<div class='stats'>{report.n_passed} passed, {report.n_failed} failed · {report.total_duration_ms:.0f}ms · {report.timestamp}</div>
<h2>Pipeline Stages</h2>
{stages_html}
<h2>Kaggle Scores</h2>
{kaggle_html}
</body></html>"""

    print(f"Validation dashboard at http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def main():
    parser = argparse.ArgumentParser(description="RNA Pipeline Validation Harness")
    parser.add_argument("--quick", action="store_true", help="Quick 20-molecule check")
    parser.add_argument("--serve", action="store_true", help="Serve live dashboard on :8522")
    parser.add_argument("--molecules", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--port", type=int, default=8522)
    parser.add_argument("--json", type=str, help="Export report to JSON file")
    args = parser.parse_args()

    n = 20 if args.quick else args.molecules
    print(f"Running validation with {n} molecules (seed={args.seed})...")
    report = run_validation(n_molecules=n, seed=args.seed)
    print(report.summary())

    if args.json:
        Path(args.json).write_text(json.dumps({
            "stages": [asdict(s) for s in report.stages],
            "overall": report.overall,
            "total_duration_ms": report.total_duration_ms,
            "kaggle_scores": report.kaggle_scores,
            "timestamp": report.timestamp,
        }, indent=2, default=str))
        print(f"\nReport saved to {args.json}")

    if args.serve:
        serve_dashboard(report, port=args.port)


if __name__ == "__main__":
    main()
