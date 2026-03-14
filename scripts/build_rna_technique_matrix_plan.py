#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def now_id() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass
class DatasetSpec:
    dataset_id: str
    url: str
    weight: float


@dataclass
class TechniqueSpec:
    technique_id: str
    notebook: str
    timeout_min: int
    expected_improvement: float
    uncertainty: float
    importance: float
    base_params: dict[str, Any]
    perturbations: list[dict[str, Any]]


def load_cfg(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config must be a mapping")
    return raw


def parse_datasets(raw: dict[str, Any]) -> list[DatasetSpec]:
    out: list[DatasetSpec] = []
    for row in raw.get("datasets", []):
        if not isinstance(row, dict):
            continue
        out.append(
            DatasetSpec(
                dataset_id=str(row.get("id", "unknown_dataset")),
                url=str(row.get("url", "")).strip(),
                weight=float(row.get("weight", 1.0)),
            )
        )
    if not out:
        raise ValueError("no datasets configured")
    return out


def parse_techniques(raw: dict[str, Any]) -> list[TechniqueSpec]:
    notebook_map = raw.get("notebooks", {})
    if not isinstance(notebook_map, dict):
        notebook_map = {}

    out: list[TechniqueSpec] = []
    for row in raw.get("technique_baselines", []):
        if not isinstance(row, dict):
            continue
        ref = str(row.get("notebook_ref", "")).strip()
        notebook = str(notebook_map.get(ref, row.get("notebook", ""))).strip()
        if not notebook:
            continue
        out.append(
            TechniqueSpec(
                technique_id=str(row.get("id", "technique")),
                notebook=notebook,
                timeout_min=int(row.get("timeout_min", raw.get("default_timeout_min", 40))),
                expected_improvement=float(row.get("expected_improvement", 0.15)),
                uncertainty=float(row.get("uncertainty", 0.55)),
                importance=float(row.get("importance", 0.85)),
                base_params=dict(row.get("params", {})) if isinstance(row.get("params", {}), dict) else {},
                perturbations=list(row.get("perturbations", [])) if isinstance(row.get("perturbations", []), list) else [],
            )
        )
    if not out:
        raise ValueError("no technique_baselines configured")
    return out


def build_jobs(raw: dict[str, Any], datasets: list[DatasetSpec], techniques: list[TechniqueSpec], max_jobs: int) -> list[dict[str, Any]]:
    repeats = int(raw.get("repeats", 1))
    jobs: list[dict[str, Any]] = []

    for rep in range(1, repeats + 1):
        for ds in datasets:
            for tech in techniques:
                variants = [{"id": "base", "params": {}}]
                for p in tech.perturbations:
                    if isinstance(p, dict):
                        variants.append({"id": str(p.get("id", "perturb")), "params": dict(p.get("params", {}))})

                for v in variants:
                    nb = Path(tech.notebook)
                    if not nb.exists():
                        continue
                    params = dict(tech.base_params)
                    params.update(v.get("params", {}))
                    params["dataset_id"] = ds.dataset_id
                    params["repeat"] = rep
                    params["param_profile"] = v["id"]
                    params["technique_id"] = tech.technique_id

                    job_id = f"mx-{tech.technique_id}-{ds.dataset_id}-{v['id']}-r{rep}"
                    jobs.append(
                        {
                            "id": job_id,
                            "notebook": str(nb),
                            "timeout_min": int(tech.timeout_min),
                            "params": params,
                            "expected_improvement": round(tech.expected_improvement * ds.weight, 4),
                            "uncertainty": round(tech.uncertainty, 4),
                            "importance": round(tech.importance, 4),
                            "tags": [
                                "technique-matrix",
                                f"technique:{tech.technique_id}",
                                f"dataset:{ds.dataset_id}",
                                f"param:{v['id']}",
                                f"repeat:{rep}",
                            ],
                        }
                    )
                    if len(jobs) >= max_jobs:
                        return jobs
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser(description="Build matrix plan for RNA technique baselines + perturbations")
    ap.add_argument("--config", default="configs/rna_technique_matrix.yaml")
    ap.add_argument("--out-plan", default="artifacts/kaggle_parallel/plan_rna_technique_matrix.json")
    ap.add_argument("--out-manifest", default="artifacts/kaggle_parallel/rna_technique_matrix_manifest.json")
    ap.add_argument("--max-jobs", type=int, default=20)
    args = ap.parse_args()

    cfg = load_cfg(Path(args.config))
    datasets = parse_datasets(cfg)
    techniques = parse_techniques(cfg)
    jobs = build_jobs(cfg, datasets, techniques, max_jobs=int(args.max_jobs))
    if not jobs:
        raise SystemExit("no runnable jobs generated (notebooks missing?)")

    plan = {
        "profile": str(cfg.get("profile", "rna_technique_matrix_v1")),
        "created_at": now_id(),
        "retries": {"max_attempts": 2, "backoff_sec": 4},
        "datasets": [{"id": d.dataset_id, "url": d.url} for d in datasets if d.url],
        "jobs": jobs,
    }

    out_plan = Path(args.out_plan)
    out_manifest = Path(args.out_manifest)
    out_plan.parent.mkdir(parents=True, exist_ok=True)
    out_manifest.parent.mkdir(parents=True, exist_ok=True)

    out_plan.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    manifest = {
        "created_at": now_id(),
        "config": args.config,
        "plan": str(out_plan),
        "job_count": len(jobs),
        "techniques": sorted({j["params"]["technique_id"] for j in jobs}),
        "datasets": sorted({j["params"]["dataset_id"] for j in jobs}),
        "param_profiles": sorted({j["params"]["param_profile"] for j in jobs}),
    }
    out_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"plan": str(out_plan), "manifest": str(out_manifest), "jobs": len(jobs)}, indent=2))


if __name__ == "__main__":
    main()
