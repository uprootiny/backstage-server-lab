#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DEFAULT = ROOT / "catalogue/notebook_sources.yaml"
EXTERNAL_DIR = ROOT / "notebooks/external"
ARTIFACT_DIR = ROOT / "artifacts/notebook_sources"
INDEX_PATH = ARTIFACT_DIR / "index.json"
PLAN_PATH = ROOT / "artifacts/kaggle_parallel/plan.json"
EVENTS_PATH = ROOT / "artifacts/operator_events.jsonl"


def ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def emit_event(kind: str, source: str, message: str, severity: str = "info", run_id: str = "") -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": ts(),
        "kind": kind,
        "source": source,
        "message": message,
        "severity": severity,
        "run_id": run_id,
    }
    with EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def clone_or_update(repo_url: str, branch: str, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        rc, out = run(["git", "fetch", "origin", branch, "--depth", "1"], cwd=target)
        if rc == 0:
            rc2, out2 = run(["git", "checkout", branch], cwd=target)
            rc3, out3 = run(["git", "reset", "--hard", f"origin/{branch}"], cwd=target)
            return {"ok": rc2 == 0 and rc3 == 0, "log": out + out2 + out3}
        return {"ok": False, "log": out}
    rc, out = run(["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(target)])
    return {"ok": rc == 0, "log": out}


def collect_matches(base: Path, patterns: list[str], limit: int = 200) -> list[str]:
    rows: list[str] = []
    for pat in patterns:
        for p in glob.glob(str(base / pat), recursive=True):
            fp = Path(p)
            if fp.is_file():
                rows.append(str(fp.relative_to(base)))
    unique = sorted(set(rows))
    return unique[:limit]


def build_plan(index_rows: list[dict[str, Any]]) -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    priority = 100
    for row in index_rows:
        for i, nb in enumerate(row.get("notebooks", [])[:4], start=1):
            for pset in row.get("paramsets", []):
                jobs.append(
                    {
                        "job_id": f"{row['id']}-{i}-{pset['profile']}",
                        "source_id": row["id"],
                        "source_name": row["name"],
                        "notebook": f"notebooks/external/{row['id']}/{nb}",
                        "param_profile": pset["profile"],
                        "params": pset.get("params", {}),
                        "priority": max(priority, 10),
                        "status": "queued",
                        "techniques": row.get("techniques", []),
                    }
                )
                priority -= 1
    return {
        "generated_at": ts(),
        "run_fabric": "kaggle_parallel",
        "profiles": {
            "three": {"workers": 3, "timeout_seconds": 2700},
            "ten": {"workers": 10, "timeout_seconds": 5400},
            "dozen": {"workers": 12, "timeout_seconds": 7200},
        },
        "jobs": jobs,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Pull external notebook repos and build runnable plan")
    ap.add_argument("--manifest", default=str(MANIFEST_DEFAULT))
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    raw = yaml.safe_load(manifest_path.read_text())
    sources = raw.get("sources", []) if isinstance(raw, dict) else []

    index_rows: list[dict[str, Any]] = []
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    for src in sources:
        sid = src["id"]
        name = src.get("name", sid)
        repo_url = src["repo_url"]
        branch = src.get("branch", "main")
        notebook_globs = src.get("notebook_globs", ["**/*.ipynb"])
        artifact_globs = src.get("artifact_globs", ["README.md"])
        paramsets = src.get("paramsets", [])

        target = EXTERNAL_DIR / sid
        result = clone_or_update(repo_url, branch, target)

        notebooks: list[str] = []
        artifacts: list[str] = []
        if result["ok"]:
            notebooks = collect_matches(target, notebook_globs, limit=50)
            artifacts = collect_matches(target, artifact_globs, limit=120)
            out_dir = ARTIFACT_DIR / sid
            out_dir.mkdir(parents=True, exist_ok=True)
            for rel in artifacts[:30]:
                srcp = target / rel
                dstp = out_dir / rel
                dstp.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(srcp, dstp)
                except Exception:
                    pass
            emit_event("source.pull", sid, f"pulled repo={repo_url} notebooks={len(notebooks)} artifacts={len(artifacts)}")
        else:
            emit_event("source.pull_failed", sid, f"failed repo pull: {repo_url}", severity="warning")

        index_rows.append(
            {
                "id": sid,
                "name": name,
                "repo_url": repo_url,
                "branch": branch,
                "pulled_at": ts(),
                "pull_ok": bool(result["ok"]),
                "notebooks": notebooks,
                "artifacts": artifacts,
                "paramsets": paramsets,
                "techniques": [p.get("profile", "default") for p in paramsets],
            }
        )

    index_payload = {"generated_at": ts(), "sources": index_rows}
    INDEX_PATH.write_text(json.dumps(index_payload, indent=2), encoding="utf-8")

    plan = build_plan(index_rows)
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"wrote {INDEX_PATH}")
    print(f"wrote {PLAN_PATH}")


if __name__ == "__main__":
    main()
