"""
MLOps Hub — FastAPI backend serving the research workspace dashboard.

Provides JSON APIs for:
  - GPU metrics & VRAM history
  - Service health checks
  - Event timeline (operator, parallel, scoring ledgers)
  - Dev journal (parsed markdown sections)
  - Log file browser
  - Docs index & content

Run:
    uvicorn web.mlops-hub.app:app --host 0.0.0.0 --port 8525
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
ARTIFACTS = ROOT / "artifacts"
EVENTS_PATH = ARTIFACTS / "operator_events.jsonl"
PARALLEL_LEDGER = ARTIFACTS / "kaggle_parallel" / "ledger.jsonl"
SCORING_LEDGER = ARTIFACTS / "kaggle_scoring_ledger.jsonl"
LOGS_DIR = Path("/workspace/logs")
REPO_LOGS = ROOT / "logs"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="MLOps Hub")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── in-memory VRAM history for sparkline ─────────────────────────────────────
vram_history: list[dict] = []
MAX_VRAM_HISTORY = 120  # ~10 min at 5s intervals


def _run(cmd: str, timeout: int = 8) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except Exception as e:
        return f"ERROR: {e}"


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


# ── API: GPU ─────────────────────────────────────────────────────────────────
@app.get("/api/gpu")
async def gpu_status():
    smi_csv = _run(
        "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,"
        "memory.used,memory.free,memory.total,power.draw,power.limit "
        "--format=csv,noheader,nounits 2>/dev/null"
    )
    gpu = {}
    if smi_csv and "ERROR" not in smi_csv and "failed" not in smi_csv.lower():
        parts = [p.strip() for p in smi_csv.split(",")]
        if len(parts) >= 6:
            gpu = {
                "name": parts[0],
                "temp_c": _safe_float(parts[1]),
                "util_pct": _safe_float(parts[2]),
                "vram_used_mb": _safe_float(parts[3]),
                "vram_free_mb": _safe_float(parts[4]),
                "vram_total_mb": _safe_float(parts[5]),
                "power_w": _safe_float(parts[6]) if len(parts) > 6 else None,
                "power_limit_w": _safe_float(parts[7]) if len(parts) > 7 else None,
                "healthy": True,
            }
            # record history
            vram_history.append({
                "t": datetime.now(timezone.utc).isoformat(),
                "used": gpu["vram_used_mb"],
                "util": gpu["util_pct"],
                "temp": gpu["temp_c"],
            })
            if len(vram_history) > MAX_VRAM_HISTORY:
                vram_history.pop(0)
    else:
        gpu = {"healthy": False, "error": smi_csv}

    # processes
    procs_raw = _run(
        "nvidia-smi --query-compute-apps=pid,process_name,used_memory "
        "--format=csv,noheader,nounits 2>/dev/null"
    )
    procs = []
    if procs_raw and "no processes" not in procs_raw.lower() and "ERROR" not in procs_raw:
        for line in procs_raw.splitlines():
            pp = [p.strip() for p in line.split(",")]
            if len(pp) >= 3:
                procs.append({"pid": pp[0], "name": pp[1], "vram_mb": _safe_float(pp[2])})

    # xid
    xid = _run("dmesg 2>/dev/null | grep -i xid | tail -10 || echo ''")

    return {
        "gpu": gpu,
        "processes": procs,
        "xid_errors": [l for l in xid.splitlines() if l.strip()],
        "vram_history": vram_history[-60:],
    }


def _safe_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# ── API: Services ────────────────────────────────────────────────────────────
@app.get("/api/services")
async def service_health():
    services = [
        {"name": "Vast Portal", "port": 1111, "internal": 11111, "ext": 19121, "path": "/"},
        {"name": "TensorBoard", "port": 6006, "internal": 16006, "ext": 19448, "path": "/"},
        {"name": "Jupyter", "port": 8080, "ext": 19808, "path": "/"},
        {"name": "Syncthing", "port": 8384, "internal": 18384, "ext": 19753, "path": "/"},
        {"name": "MLOps Hub", "port": 8525, "ext": None, "path": "/"},
        {"name": "MLOps Lab (Streamlit)", "port": 8523, "ext": None, "path": "/"},
        {"name": "Portal Dashboard", "port": 8520, "ext": 19842, "path": "/"},
        {"name": "Notebook Lab", "port": 8521, "ext": None, "path": "/"},
        {"name": "Validation Harness", "port": 8522, "ext": None, "path": "/"},
        {"name": "Grafana", "port": 3000, "ext": None, "path": "/api/health"},
        {"name": "Prometheus", "port": 9090, "ext": None, "path": "/-/healthy"},
    ]

    async def check(svc):
        port = svc.get("internal", svc["port"])
        code = _run(
            f"curl -sf -o /dev/null -w '%{{http_code}}' --max-time 2 "
            f"http://localhost:{port}{svc['path']} 2>/dev/null || echo '000'"
        )
        svc["status"] = code.strip()
        svc["up"] = code.strip().startswith("2") or code.strip().startswith("3")
        return svc

    results = []
    for s in services:
        results.append(await check(s))
    return results


# ── API: Events / Timeline ───────────────────────────────────────────────────
@app.get("/api/events")
async def events(source: Optional[str] = None, kind: Optional[str] = None):
    all_events = []
    for ev in _load_jsonl(EVENTS_PATH):
        ev["_source"] = "operator"
        all_events.append(ev)
    for ev in _load_jsonl(PARALLEL_LEDGER):
        ev["_source"] = "parallel"
        all_events.append(ev)
    for ev in _load_jsonl(SCORING_LEDGER):
        ev["_source"] = "scoring"
        all_events.append(ev)

    if source:
        all_events = [e for e in all_events if e.get("_source") == source]
    if kind:
        all_events = [e for e in all_events if kind in e.get("kind", e.get("event", ""))]

    all_events.sort(key=lambda e: e.get("ts", e.get("timestamp", "")), reverse=True)
    return all_events[:300]


# ── API: Dev Journal ─────────────────────────────────────────────────────────
@app.get("/api/journal")
async def journal():
    path = DOCS_DIR / "DEV_JOURNAL.md"
    if not path.exists():
        return {"sections": []}
    text = path.read_text()
    sections = []
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                sections.append(current)
            current = {"title": line.lstrip("# ").strip(), "body": ""}
        elif current is not None:
            current["body"] += line + "\n"
    if current:
        sections.append(current)
    return {"sections": sections}


# ── API: Git log ─────────────────────────────────────────────────────────────
@app.get("/api/git-log")
async def git_log(n: int = 40):
    raw = _run(f"git -C {ROOT} log --oneline --date=short --format='%h|%ad|%s' -{n}")
    commits = []
    for line in raw.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append({"sha": parts[0], "date": parts[1], "msg": parts[2]})
    return commits


# ── API: Logs ────────────────────────────────────────────────────────────────
@app.get("/api/logs")
async def list_logs():
    files = []
    for d in [LOGS_DIR, REPO_LOGS]:
        if d.exists():
            for f in sorted(d.glob("*.log")):
                files.append({
                    "name": f.name,
                    "path": str(f),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "mtime": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
                })
    return files


@app.get("/api/logs/{filename}")
async def read_log(filename: str, tail: int = 150, grep: Optional[str] = None):
    # search both log dirs
    for d in [LOGS_DIR, REPO_LOGS]:
        p = d / filename
        if p.exists():
            lines = p.read_text(errors="replace").splitlines()
            lines = lines[-tail:]
            if grep:
                lines = [l for l in lines if grep.lower() in l.lower()]
            return {"filename": filename, "lines": lines}
    return {"filename": filename, "lines": ["(file not found)"]}


# ── API: Docs ────────────────────────────────────────────────────────────────
@app.get("/api/docs")
async def list_docs():
    if not DOCS_DIR.exists():
        return []
    docs = []
    for f in sorted(DOCS_DIR.glob("*.md")):
        docs.append({
            "name": f.stem,
            "size_kb": round(f.stat().st_size / 1024, 1),
        })
    return docs


@app.get("/api/docs/{name}")
async def read_doc(name: str):
    p = DOCS_DIR / f"{name}.md"
    if not p.exists():
        return {"name": name, "content": "(not found)"}
    return {"name": name, "content": p.read_text(errors="replace")}


# ── Serve index.html ─────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8525)
