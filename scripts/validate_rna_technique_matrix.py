#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def choose_run_id(rows: list[dict[str, Any]], explicit: str | None) -> str:
    if explicit:
        return explicit
    run_ends = [r for r in rows if r.get("event") == "run_end"]
    if not run_ends:
        raise SystemExit("no run_end rows in ledger")
    return str(run_ends[-1].get("run_id", ""))


def seconds_safe(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def group_summary(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for j in jobs:
        p = j.get("params", {}) if isinstance(j.get("params", {}), dict) else {}
        key = (str(p.get("technique_id", "?")), str(p.get("dataset_id", "?")), str(p.get("param_profile", "?")))
        by_key[key].append(j)

    out: list[dict[str, Any]] = []
    for (technique_id, dataset_id, param_profile), rows in sorted(by_key.items()):
        statuses = [str(r.get("status", "")) for r in rows]
        secs = [seconds_safe(r.get("seconds", 0.0)) for r in rows]
        out.append(
            {
                "technique_id": technique_id,
                "dataset_id": dataset_id,
                "param_profile": param_profile,
                "runs": len(rows),
                "ok": sum(1 for s in statuses if s == "ok"),
                "failed": sum(1 for s in statuses if s != "ok"),
                "success_rate": round(sum(1 for s in statuses if s == "ok") / max(1, len(rows)), 4),
                "median_seconds": round(median(secs) if secs else 0.0, 2),
            }
        )
    return out


def perturbation_effects(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_anchor: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for j in jobs:
        p = j.get("params", {}) if isinstance(j.get("params", {}), dict) else {}
        anchor = (str(p.get("technique_id", "?")), str(p.get("dataset_id", "?")), int(p.get("repeat", 0)))
        profile = str(p.get("param_profile", "?"))
        by_anchor[anchor][profile] = j

    out: list[dict[str, Any]] = []
    for (technique_id, dataset_id, rep), prof_rows in sorted(by_anchor.items()):
        base = prof_rows.get("base")
        if not base:
            continue
        base_sec = seconds_safe(base.get("seconds", 0.0))
        base_ok = str(base.get("status", "")) == "ok"

        for profile, row in prof_rows.items():
            if profile == "base":
                continue
            sec = seconds_safe(row.get("seconds", 0.0))
            ok = str(row.get("status", "")) == "ok"
            out.append(
                {
                    "technique_id": technique_id,
                    "dataset_id": dataset_id,
                    "repeat": rep,
                    "param_profile": profile,
                    "base_status": "ok" if base_ok else "failed",
                    "status": "ok" if ok else "failed",
                    "base_seconds": round(base_sec, 2),
                    "seconds": round(sec, 2),
                    "delta_seconds": round(sec - base_sec, 2),
                }
            )
    return out


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# RNA Technique Matrix Validation",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- run_id: `{payload['run_id']}`",
        f"- plan: `{payload['plan']}`",
        f"- expected_jobs: {payload['expected_jobs']}",
        f"- observed_jobs: {payload['observed_jobs']}",
        f"- ok: {payload['ok']}",
        f"- failed: {payload['failed']}",
        "",
        "## Group Summary",
        "",
        "| Technique | Dataset | Param Profile | Runs | OK | Failed | Success Rate | Median Seconds |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in payload["group_summary"]:
        lines.append(
            f"| `{r['technique_id']}` | `{r['dataset_id']}` | `{r['param_profile']}` | {r['runs']} | {r['ok']} | {r['failed']} | {r['success_rate']:.2f} | {r['median_seconds']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Perturbation Effects",
            "",
            "| Technique | Dataset | Repeat | Param Profile | Base | Variant | Δ Seconds |",
            "|---|---|---:|---|---|---|---:|",
        ]
    )

    for r in payload["perturbation_effects"]:
        lines.append(
            f"| `{r['technique_id']}` | `{r['dataset_id']}` | {r['repeat']} | `{r['param_profile']}` | `{r['base_status']}` | `{r['status']}` | {r['delta_seconds']:.2f} |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate latest technique matrix run from ledger + plan")
    ap.add_argument("--plan", default="artifacts/kaggle_parallel/plan_rna_technique_matrix.json")
    ap.add_argument("--ledger", default="artifacts/kaggle_parallel/ledger.jsonl")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--out-json", default="reports/rna_technique_matrix_validation.json")
    ap.add_argument("--out-md", default="docs/RNA_TECHNIQUE_MATRIX_VALIDATION.md")
    args = ap.parse_args()

    plan_path = Path(args.plan)
    ledger_path = Path(args.ledger)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)

    plan = read_json(plan_path)
    plan_jobs = {str(j.get("id", "")): j for j in plan.get("jobs", []) if isinstance(j, dict)}
    rows = read_jsonl(ledger_path)
    run_id = choose_run_id(rows, args.run_id or None)

    job_rows = [r for r in rows if r.get("event") == "job_end" and str(r.get("run_id", "")) == run_id]
    enriched: list[dict[str, Any]] = []
    for r in job_rows:
        job_id = str(r.get("job_id", ""))
        p = plan_jobs.get(job_id, {})
        merged = dict(r)
        merged["params"] = dict(p.get("params", {})) if isinstance(p.get("params", {}), dict) else {}
        merged["notebook"] = str(p.get("notebook", r.get("notebook", "")))
        merged["expected_output_notebook"] = str(Path("artifacts/kaggle_parallel/executed") / f"{job_id}.executed.ipynb")
        merged["output_exists"] = Path(merged["expected_output_notebook"]).exists()
        enriched.append(merged)

    ok = sum(1 for r in enriched if str(r.get("status", "")) == "ok")
    failed = len(enriched) - ok
    missing_outputs = [r["job_id"] for r in enriched if str(r.get("status", "")) == "ok" and not bool(r.get("output_exists", False))]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "kind": "rna_technique_matrix_validation",
        "run_id": run_id,
        "plan": str(plan_path),
        "ledger": str(ledger_path),
        "expected_jobs": len(plan_jobs),
        "observed_jobs": len(enriched),
        "ok": ok,
        "failed": failed,
        "missing_output_notebooks": missing_outputs,
        "group_summary": group_summary(enriched),
        "perturbation_effects": perturbation_effects(enriched),
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload), encoding="utf-8")

    print(json.dumps({"run_id": run_id, "out_json": str(out_json), "out_md": str(out_md), "ok": ok, "failed": failed}, indent=2))


if __name__ == "__main__":
    main()
