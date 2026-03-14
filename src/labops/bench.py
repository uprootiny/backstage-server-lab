from __future__ import annotations

import hashlib
import math
import random
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import orjson
import yaml

from .store import connect, insert_run, insert_validation


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def stable_seed(variant: str, hypothesis_id: str) -> int:
    h = hashlib.sha256(f"{variant}:{hypothesis_id}".encode()).hexdigest()[:8]
    return int(h, 16)


def synthetic_metric(params: dict[str, Any], seed: int) -> float:
    rng = random.Random(seed)
    lr = float(params.get("lr", 1e-3))
    batch = float(params.get("batch_size", 32))
    reg = float(params.get("regularization", 0.0))
    noise = rng.uniform(-0.03, 0.03)
    score = 0.65 + (0.09 * math.exp(-abs(math.log10(lr) + 3.0))) + (0.04 * math.tanh((batch - 16.0) / 32.0)) - (0.03 * reg) + noise
    return max(0.0, min(1.0, score))


def run_variant(hypothesis_id: str, variant: str, params: dict[str, Any]) -> dict[str, Any]:
    started = now_iso()
    seed = stable_seed(variant, hypothesis_id)
    metric = synthetic_metric(params, seed)
    voi_weight = float(params.get("voi_weight", 1.0))
    score = metric * voi_weight
    return {
        "run_id": str(uuid.uuid4()),
        "hypothesis_id": hypothesis_id,
        "variant": variant,
        "params_json": orjson.dumps(params).decode(),
        "metric": metric,
        "score": score,
        "started_at": started,
        "ended_at": now_iso(),
    }


def run_bench(db_path: Path, config_path: Path, hypothesis_id: str, workers: int = 3) -> list[dict[str, Any]]:
    cfg = load_yaml(config_path)
    base = cfg.get("base", {})
    variants = cfg.get("variants", {})

    jobs: list[tuple[str, dict[str, Any]]] = []
    for name, overrides in variants.items():
        params = {**base, **(overrides or {})}
        jobs.append((name, params))

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        future_map = {ex.submit(run_variant, hypothesis_id, name, params): name for name, params in jobs}
        for fut in as_completed(future_map):
            results.append(fut.result())

    conn = connect(db_path)
    for r in results:
        insert_run(conn, r)
        passed = r["metric"] >= float(cfg.get("validation", {}).get("min_metric", 0.7))
        insert_validation(
            conn,
            {
                "validation_id": str(uuid.uuid4()),
                "run_id": r["run_id"],
                "passed": passed,
                "notes": "auto bench validation",
                "created_at": now_iso(),
            },
        )
    conn.close()
    return sorted(results, key=lambda x: x["score"], reverse=True)


def export_thesis_graph(db_path: Path, out_path: Path) -> None:
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT hypothesis_id, statement, question, voi_prior, kaggle_ref, paper_ref FROM hypotheses")
    hypotheses = cur.fetchall()
    cur.execute("SELECT run_id, hypothesis_id, variant, metric, score FROM runs")
    runs = cur.fetchall()
    conn.close()

    g = nx.DiGraph()
    for h_id, statement, question, voi_prior, kaggle_ref, paper_ref in hypotheses:
        g.add_node(h_id, kind="hypothesis", statement=statement, question=question, voi_prior=voi_prior)
        if kaggle_ref:
            kaggle_node = f"kaggle:{kaggle_ref}"
            g.add_node(kaggle_node, kind="kaggle_ref")
            g.add_edge(h_id, kaggle_node, relation="backed_by")
        if paper_ref:
            paper_node = f"paper:{paper_ref}"
            g.add_node(paper_node, kind="paper_ref")
            g.add_edge(h_id, paper_node, relation="backed_by")

    for run_id, h_id, variant, metric, score in runs:
        g.add_node(run_id, kind="run", variant=variant, metric=metric, score=score)
        g.add_edge(h_id, run_id, relation="tested_by")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "nodes": [{"id": n, **attrs} for n, attrs in g.nodes(data=True)],
        "edges": [{"source": u, "target": v, **attrs} for u, v, attrs in g.edges(data=True)],
    }
    out_path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
