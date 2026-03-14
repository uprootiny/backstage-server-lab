from __future__ import annotations

import hashlib
import json
import random
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .experiment import Experiment, load_experiment


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed(payload: str) -> int:
    return int(hashlib.sha256(payload.encode()).hexdigest()[:8], 16)


def _run_variant(exp_name: str, idx: int, variant: dict[str, Any]) -> dict[str, Any]:
    s = _seed(f"{exp_name}:{idx}:{json.dumps(variant, sort_keys=True)}")
    rng = random.Random(s)
    lr = float(variant.get("lr", 1e-3))
    batch = float(variant.get("batch_size", 32))
    base = 0.62 + (0.08 / (1.0 + abs((lr * 1e3) - 1.0))) + (0.06 if batch >= 32 else 0.03)
    score = max(0.0, min(1.0, base + rng.uniform(-0.03, 0.03)))
    return {
        "run_id": str(uuid.uuid4()),
        "variant_idx": idx,
        "variant": variant,
        "score": score,
        "started_at": _now(),
        "ended_at": _now(),
    }


def run_experiment_file(path: Path, workers: int = 3) -> dict[str, Any]:
    exp: Experiment = load_experiment(path)
    exp.results_dir.mkdir(parents=True, exist_ok=True)

    jobs = [(exp.name, idx, variant) for idx, variant in enumerate(exp.variants)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(_run_variant_unpack, jobs))

    results = sorted(results, key=lambda r: r["score"], reverse=True)
    out = {
        "experiment": exp.name,
        "hypothesis": exp.hypothesis,
        "dataset": exp.dataset,
        "metrics": exp.metrics,
        "results": results,
        "generated_at": _now(),
    }
    (exp.results_dir / "results.json").write_text(json.dumps(out, indent=2))
    return out


def _run_variant_unpack(job: tuple[str, int, dict[str, Any]]) -> dict[str, Any]:
    exp_name, idx, variant = job
    return _run_variant(exp_name, idx, variant)
