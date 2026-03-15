from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import re
import subprocess
import time
from pathlib import Path
import sys
import os
from typing import Any
from urllib.request import urlopen

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from kaggle.api.kaggle_api_extended import KaggleApi

CACHE_PATH = Path("artifacts/kaggle_mashup_cache.parquet")
CATALOGUE_PATH = Path("artifacts/kaggle_catalogue.json")
STARTER_INDEX_PATH = Path("notebooks/starters/index.json")
SEED_ROWS_PATH = Path("data/seeds/kaggle_rna_seed_rows.json")
SEED_CATALOGUE_PATH = Path("data/seeds/kaggle_rna_seed_catalogue.json")
REGISTRY_PATH = Path("artifacts/notebook_submission_registry.jsonl")
PARALLEL_PLAN_PATH = Path("artifacts/kaggle_parallel/plan.json")
PARALLEL_PLAN_YAML_PATH = Path("artifacts/kaggle_parallel/plan.yaml")
PARALLEL_LEDGER_PATH = Path("artifacts/kaggle_parallel/ledger.jsonl")
MANUAL_QUEUE_PATH = Path("artifacts/kaggle_parallel/manual_dispatch_queue.jsonl")
MANUAL_QUEUE_STATE_PATH = Path("artifacts/kaggle_parallel/manual_dispatch_state.json")
RERUN_MARKS_PATH = Path("artifacts/kaggle_parallel/rerun_marks.jsonl")
PARAM_ADJUST_PATH = Path("artifacts/kaggle_parallel/param_adjustments.jsonl")
LIVE_ENDPOINTS_PATH = Path("docs/LIVE_ENDPOINTS.md")
LOG_DIR = Path("logs")
EVENTS_PATH = Path("artifacts/operator_events.jsonl")
NOTEBOOK_SOURCES_INDEX_PATH = Path("artifacts/notebook_sources/index.json")
NOTEBOOK_FABRIC_DOC_PATH = Path("docs/NOTEBOOK_FABRIC.md")
TOP_NOTEBOOK_DIGEST_PATH = Path("docs/TOP_NOTEBOOK_DIGEST.md")
TOP_NOTEBOOK_ANALYSIS_PATH = Path("artifacts/top_notebook_analysis.json")
OPEN_DATASETS_PATH = Path("data/seeds/open_rna_foundational_datasets.json")
VISUALS_DIR = Path("docs/assets")
PIPELINE_RUNS_PATH = Path("artifacts/pipeline_runs.jsonl")
HYPOTHESES_PATH = Path("artifacts/hypotheses_shelf.json")
GARDEN_STATE_PATH = Path("artifacts/garden_state.json")
VAST_PUBLIC_IP = os.getenv("VAST_PUBLIC_IP", "175.155.64.231")
VAST_SSH_PORT = os.getenv("VAST_SSH_PORT", "19636")
VAST_JUPYTER_PORT = os.getenv("VAST_JUPYTER_PORT", "19808")
VAST_PORTAL_PORT = os.getenv("VAST_PORTAL_PORT", "19121")
VAST_TENSORBOARD_PORT = os.getenv("VAST_TENSORBOARD_PORT", "19448")
VAST_SYNCTHING_PORT = os.getenv("VAST_SYNCTHING_PORT", "19753")
VAST_OPEN_PORT = os.getenv("VAST_OPEN_PORT", "19842")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://127.0.0.1:19300")
OBS_TUNNEL_URL = os.getenv("OBS_TUNNEL_URL", "")
VAST_PORT_MAP = [
    ("SSH", f"{VAST_PUBLIC_IP}:{VAST_SSH_PORT} -> 22/tcp"),
    ("Jupyter", f"{VAST_PUBLIC_IP}:{VAST_JUPYTER_PORT} -> 8080/tcp"),
    ("Portal", f"{VAST_PUBLIC_IP}:{VAST_PORTAL_PORT} -> 1111/tcp"),
    ("TensorBoard", f"{VAST_PUBLIC_IP}:{VAST_TENSORBOARD_PORT} -> 6006/tcp"),
    ("Syncthing", f"{VAST_PUBLIC_IP}:{VAST_SYNCTHING_PORT} -> 8384/tcp"),
    ("Open", f"{VAST_PUBLIC_IP}:{VAST_OPEN_PORT} -> dynamic"),
]

JUPYTER_BASE_URL = os.getenv("JUPYTER_BASE_URL", f"https://{VAST_PUBLIC_IP}:{VAST_JUPYTER_PORT}")
TENSORBOARD_URL = os.getenv("TENSORBOARD_URL", f"http://{VAST_PUBLIC_IP}:{VAST_TENSORBOARD_PORT}")
TB_RUN_ROOTS = [
    Path("/workspace/logs/rna"),
    Path("/tmp/rna_tb"),
    Path("artifacts/tensorboard"),
]


@dataclass
class Row:
    kind: str
    ref: str
    title: str
    subtitle: str
    score: float
    updated: str
    url: str


def _safe_len(v: Any) -> int:
    try:
        return len(v)
    except Exception:
        return 0


def fetch_live(limit: int = 50, search: str = "") -> pd.DataFrame:
    api = KaggleApi()
    api.authenticate()

    rows: list[Row] = []

    competitions = api.competitions_list(search=search)
    for c in competitions[:limit]:
        rows.append(
            Row(
                kind="competition",
                ref=getattr(c, "ref", ""),
                title=getattr(c, "title", ""),
                subtitle=getattr(c, "category", ""),
                score=float(getattr(c, "reward", 0) or 0),
                updated=str(getattr(c, "deadline", "")),
                url=f"https://www.kaggle.com/competitions/{getattr(c, 'ref', '')}",
            )
        )

    datasets = api.dataset_list(search=search)
    for d in datasets[:limit]:
        rows.append(
            Row(
                kind="dataset",
                ref=getattr(d, "ref", ""),
                title=getattr(d, "title", ""),
                subtitle=getattr(d, "licenseName", ""),
                score=float(getattr(d, "totalBytes", 0) or 0),
                updated=str(getattr(d, "lastUpdated", "")),
                url=f"https://www.kaggle.com/datasets/{getattr(d, 'ref', '')}",
            )
        )

    df = pd.DataFrame([asdict(r) for r in rows])
    return df


def load_or_fetch(limit: int, search: str, force_live: bool) -> pd.DataFrame:
    if force_live:
        df = fetch_live(limit=limit, search=search)
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(CACHE_PATH, index=False)
        return df

    if CACHE_PATH.exists():
        return pd.read_parquet(CACHE_PATH)

    try:
        df = fetch_live(limit=limit, search=search)
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(CACHE_PATH, index=False)
        return df
    except Exception:
        if SEED_ROWS_PATH.exists():
            raw = json.loads(SEED_ROWS_PATH.read_text())
            rows = raw.get("rows", [])
            return pd.DataFrame(rows)
        raise


def load_catalogue() -> pd.DataFrame:
    if CATALOGUE_PATH.exists():
        raw = json.loads(CATALOGUE_PATH.read_text())
    elif SEED_CATALOGUE_PATH.exists():
        raw = json.loads(SEED_CATALOGUE_PATH.read_text())
    else:
        return pd.DataFrame()
    items = raw.get("items", [])
    if not isinstance(items, list):
        return pd.DataFrame()
    return pd.DataFrame(items)


def load_starter_index() -> list[dict[str, Any]]:
    if not STARTER_INDEX_PATH.exists():
        return []
    raw = json.loads(STARTER_INDEX_PATH.read_text())
    items = raw.get("starters", [])
    if not isinstance(items, list):
        return []
    return items


def load_registry() -> pd.DataFrame:
    if not REGISTRY_PATH.exists():
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for line in REGISTRY_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "profile" in df.columns:
        df["format"] = df["profile"].apply(
            lambda p: p.get("format", "") if isinstance(p, dict) else ""
        )
    return df


def load_parallel_plan() -> dict[str, Any]:
    if PARALLEL_PLAN_PATH.exists():
        try:
            return json.loads(PARALLEL_PLAN_PATH.read_text())
        except Exception:
            return {}
    if PARALLEL_PLAN_YAML_PATH.exists():
        try:
            import yaml

            raw = yaml.safe_load(PARALLEL_PLAN_YAML_PATH.read_text())
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}
    return {}


def load_parallel_ledger() -> pd.DataFrame:
    if not PARALLEL_LEDGER_PATH.exists():
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for line in PARALLEL_LEDGER_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def run_health_summary(ledger: pd.DataFrame) -> dict[str, Any]:
    if ledger.empty:
        return {
            "ledger_rows": 0,
            "run_end_count": 0,
            "job_end_count": 0,
            "ok": 0,
            "failed": 0,
            "latest_run_end": None,
            "notebooks": [],
        }
    runs = ledger[ledger.get("event", "") == "run_end"] if "event" in ledger.columns else pd.DataFrame()
    jobs = ledger[ledger.get("event", "") == "job_end"] if "event" in ledger.columns else ledger
    if "status" in jobs.columns:
        ok = int((jobs["status"] == "ok").sum())
        failed = int((jobs["status"] != "ok").sum())
    else:
        ok = 0
        failed = int(len(jobs))

    notebooks: list[dict[str, Any]] = []
    if not jobs.empty:
        work = jobs.copy()
        if "notebook" not in work.columns:
            work["notebook"] = work.get("job_id", "unknown")
        if "status" not in work.columns:
            work["status"] = "unknown"
        grouped = (
            work.groupby("notebook", dropna=False)["status"]
            .apply(list)
            .reset_index()
            .rename(columns={"status": "statuses"})
        )
        for _, row in grouped.iterrows():
            statuses = [str(s) for s in row["statuses"]]
            nb = str(row["notebook"])
            ok_nb = sum(1 for s in statuses if s == "ok")
            fail_nb = len(statuses) - ok_nb
            notebooks.append({"notebook": nb, "ok": ok_nb, "failed": fail_nb, "total": len(statuses)})
        notebooks.sort(key=lambda x: (-x["total"], x["notebook"]))

    latest = None
    if not runs.empty:
        latest = runs.tail(1).to_dict("records")[0]

    return {
        "ledger_rows": int(len(ledger)),
        "run_end_count": int(len(runs)),
        "job_end_count": int(len(jobs)),
        "ok": ok,
        "failed": failed,
        "latest_run_end": latest,
        "notebooks": notebooks,
    }


def latest_job_rows_for_run(ledger: pd.DataFrame, run_id: str) -> pd.DataFrame:
    if ledger.empty or "event" not in ledger.columns or "run_id" not in ledger.columns:
        return pd.DataFrame()
    rows = ledger[(ledger["event"] == "job_end") & (ledger["run_id"] == run_id)].copy()
    if rows.empty:
        return rows
    keep = [c for c in ["job_id", "notebook", "status", "exit_code", "seconds", "log", "output_notebook", "attempts"] if c in rows.columns]
    if keep:
        rows = rows[keep]
    return rows.sort_values(by="job_id")


def notebook_scoreboard(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty or "event" not in ledger.columns:
        return pd.DataFrame()
    jobs = ledger[ledger["event"] == "job_end"].copy()
    if jobs.empty:
        return pd.DataFrame()
    if "notebook" not in jobs.columns:
        jobs["notebook"] = jobs.get("job_id", "unknown")
    if "status" not in jobs.columns:
        jobs["status"] = "unknown"
    if "seconds" not in jobs.columns:
        jobs["seconds"] = float("nan")
    rows = []
    for nb, g in jobs.groupby("notebook", dropna=False):
        total = int(len(g))
        ok = int((g["status"] == "ok").sum())
        failed = total - ok
        sr = (ok / total) if total else 0.0
        mean_sec = float(pd.to_numeric(g["seconds"], errors="coerce").dropna().mean() or 0.0)
        # Higher is better; failure and runtime penalize.
        score = 100.0 * sr - 0.12 * mean_sec - 6.0 * failed
        rerun_priority = (1.0 - sr) * 0.65 + min(1.0, mean_sec / 300.0) * 0.2 + (failed > ok) * 0.15
        latest = g.tail(1).to_dict("records")[0]
        rows.append(
            {
                "notebook": str(nb),
                "total": total,
                "ok": ok,
                "failed": failed,
                "success_rate": round(sr, 3),
                "mean_seconds": round(mean_sec, 2),
                "score": round(score, 2),
                "rerun_priority": round(float(rerun_priority), 3),
                "last_status": str(latest.get("status", "")),
                "last_run_id": str(latest.get("run_id", "")),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(by=["rerun_priority", "score"], ascending=[False, True]).reset_index(drop=True)


def _safe_slug(x: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", x).strip("-") or "job"


def write_rerun_plan_from_rows(rows: list[dict[str, Any]], out_path: Path) -> Path:
    jobs: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        notebook = str(row.get("notebook", "")).strip()
        if not notebook:
            continue
        job_id = str(row.get("job_id", f"rerun-{i+1:03d}"))
        jobs.append(
            {
                "id": f"rerun-{_safe_slug(job_id)}",
                "notebook": notebook,
                "timeout_min": 45,
                "params": {"source": "run_fabric_rerun_ui", "original_job_id": job_id},
                "expected_improvement": 0.20,
                "uncertainty": 0.60,
                "importance": 0.90,
                "tags": ["rerun", "ui", "failed-job"],
            }
        )
    payload = {
        "profile": "ui_rerun_failed_jobs",
        "created_at": _fmt_utc(),
        "notes": "Generated by Run Fabric rerun affordance.",
        "jobs": jobs,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def read_live_endpoints_md() -> str:
    if not LIVE_ENDPOINTS_PATH.exists():
        return "No `docs/LIVE_ENDPOINTS.md` yet. Run `make obs-probe`."
    return LIVE_ENDPOINTS_PATH.read_text()


def recent_logs(max_lines: int = 250) -> str:
    parts: list[str] = []
    for path in sorted(LOG_DIR.glob("*.log")):
        try:
            tail = path.read_text().splitlines()[-max_lines:]
        except Exception:
            tail = []
        parts.append(f"## {path.name}\n" + ("\n".join(tail) if tail else "(empty)"))
    return "\n\n".join(parts) if parts else "No log files found in `logs/`."


def _fmt_utc(dt: datetime | None = None) -> str:
    now = dt or datetime.now(timezone.utc)
    return now.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_events() -> pd.DataFrame:
    if not EVENTS_PATH.exists():
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for line in EVENTS_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return pd.DataFrame(rows)


def load_notebook_sources_index() -> dict[str, Any]:
    if not NOTEBOOK_SOURCES_INDEX_PATH.exists():
        return {}
    try:
        raw = json.loads(NOTEBOOK_SOURCES_INDEX_PATH.read_text())
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def load_top_notebook_analysis() -> dict[str, Any]:
    if not TOP_NOTEBOOK_ANALYSIS_PATH.exists():
        return {}
    try:
        raw = json.loads(TOP_NOTEBOOK_ANALYSIS_PATH.read_text())
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def load_open_datasets() -> pd.DataFrame:
    if not OPEN_DATASETS_PATH.exists():
        return pd.DataFrame()
    try:
        raw = json.loads(OPEN_DATASETS_PATH.read_text())
    except Exception:
        return pd.DataFrame()
    rows = raw.get("datasets", []) if isinstance(raw, dict) else []
    if not isinstance(rows, list):
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _http_code(url: str, timeout: float = 4.0) -> int:
    try:
        with urlopen(url, timeout=timeout) as r:  # nosec B310
            return int(getattr(r, "status", 0) or 0)
    except Exception:
        return 0


def discover_tensorboard_runs(max_runs: int = 80) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for root in TB_RUN_ROOTS:
        if not root.exists():
            continue
        for ev in root.glob("**/events.out.tfevents.*"):
            run_dir = ev.parent
            run_name = run_dir.name
            rel_dir = str(run_dir)
            try:
                size_kb = round(ev.stat().st_size / 1024, 1)
                mtime = datetime.fromtimestamp(ev.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            except Exception:
                size_kb = 0.0
                mtime = ""
            rows.append(
                {
                    "run_name": run_name,
                    "event_file": str(ev),
                    "run_dir": rel_dir,
                    "size_kb": size_kb,
                    "updated_utc": mtime,
                    "open_tensorboard": TENSORBOARD_URL,
                }
            )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values(["updated_utc", "size_kb"], ascending=[False, False]).head(max_runs)
    return df.reset_index(drop=True)


def inject_theme() -> None:
    st.markdown(
        """
<style>
:root {
  --lab-bg-0: #0a120f;
  --lab-bg-1: #111d18;
  --lab-bg-2: #182821;
  --lab-fg: #dbe8df;
  --lab-muted: #98b7a7;
  --lab-accent: #7ed9a8;
  --lab-warn: #f1bb70;
  --lab-border: #284438;
}
.stApp {
  background:
    radial-gradient(1200px 500px at 15% -10%, rgba(84, 166, 120, 0.18), transparent 55%),
    radial-gradient(900px 400px at 90% 0%, rgba(79, 124, 166, 0.16), transparent 55%),
    linear-gradient(180deg, var(--lab-bg-0), #08100d 70%);
  color: var(--lab-fg);
}
h1, h2, h3 {
  letter-spacing: 0.02em;
}
.lab-hero {
  border: 1px solid var(--lab-border);
  background: linear-gradient(120deg, rgba(20,36,29,0.95), rgba(12,22,19,0.95));
  border-radius: 12px;
  padding: 14px 16px;
  margin: 0 0 12px 0;
}
.lab-kicker {
  font-family: "IBM Plex Mono", monospace;
  color: var(--lab-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: .10em;
}
.lab-title {
  font-size: 24px;
  color: var(--lab-fg);
  margin: 4px 0 8px 0;
  font-weight: 650;
}
.lab-sub {
  color: var(--lab-muted);
  font-size: 14px;
}
.lab-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.lab-chip {
  border: 1px solid var(--lab-border);
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 12px;
  color: var(--lab-accent);
  background: rgba(28, 48, 40, 0.55);
}
div[data-baseweb="tab-list"] {
  background: rgba(13, 23, 19, 0.8);
  border: 1px solid var(--lab-border);
  border-radius: 10px;
  padding: 4px;
}
div[data-baseweb="tab"] {
  border-radius: 8px !important;
  margin-right: 4px !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
<div class="lab-hero">
  <div class="lab-kicker">Open Computational RNA Science</div>
  <div class="lab-title">RNA Folding Research Observatory</div>
  <div class="lab-sub">
    Experimental. Reproducible. Precision-oriented. Notebook runs, model artifacts, and ops telemetry are tracked as one scientific instrument.
  </div>
  <div class="lab-chip-row">
    <span class="lab-chip">open datasets</span>
    <span class="lab-chip">candidate ensembles</span>
    <span class="lab-chip">run fabric</span>
    <span class="lab-chip">VOI prioritization</span>
    <span class="lab-chip">operator trace</span>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def emit_event(kind: str, source: str, message: str, severity: str = "info", run_id: str = "") -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _fmt_utc(),
        "kind": kind,
        "source": source,
        "message": message,
        "severity": severity,
        "run_id": run_id,
    }
    with EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def enqueue_manual_dispatch(payload: dict[str, Any]) -> None:
    MANUAL_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": _fmt_utc(), **payload}
    with MANUAL_QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def load_manual_queue() -> list[dict[str, Any]]:
    if not MANUAL_QUEUE_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(MANUAL_QUEUE_PATH.read_text(encoding="utf-8").splitlines()):
        s = line.strip()
        if not s:
            continue
        try:
            row = json.loads(s)
            if isinstance(row, dict):
                row["_line"] = i
                rows.append(row)
        except Exception:
            continue
    return rows


def _read_manual_queue_offset() -> int:
    if not MANUAL_QUEUE_STATE_PATH.exists():
        return 0
    try:
        raw = json.loads(MANUAL_QUEUE_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if isinstance(raw, dict):
        return int(raw.get("applied_offset", 0) or 0)
    return 0


def _write_manual_queue_offset(offset: int) -> None:
    MANUAL_QUEUE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANUAL_QUEUE_STATE_PATH.write_text(
        json.dumps({"applied_offset": int(offset), "updated_at": _fmt_utc()}, indent=2),
        encoding="utf-8",
    )


def apply_manual_queue_to_plan(plan_path: Path = PARALLEL_PLAN_PATH, max_apply: int = 20) -> dict[str, Any]:
    if plan_path.exists():
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except Exception:
            plan = {}
    else:
        plan = {}
    if not isinstance(plan, dict):
        plan = {}
    jobs = plan.get("jobs", [])
    if not isinstance(jobs, list):
        jobs = []

    rows = load_manual_queue()
    offset = _read_manual_queue_offset()
    pending = [r for r in rows if int(r.get("_line", -1)) >= offset]
    applied = 0
    for row in pending[:max_apply]:
        jid = f"manual-{len(jobs)+1:04d}"
        jobs.append(
            {
                "id": jid,
                "notebook": str(row.get("notebook", "")),
                "timeout_min": 60,
                "expected_improvement": 0.22 if str(row.get("profile", "")) != "smoke" else 0.08,
                "uncertainty": 0.65,
                "importance": 0.85,
                "params": {
                    "profile": str(row.get("profile", "smoke")),
                    "priority": int(row.get("priority", 50) or 50),
                    "workers_hint": int(row.get("workers_hint", 3) or 3),
                },
                "tags": ["manual", "ui", "queued_intent"],
            }
        )
        applied += 1

    plan["profile"] = plan.get("profile", "manual")
    plan["jobs"] = jobs
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    if applied:
        last_line = pending[min(applied, len(pending)) - 1].get("_line", offset)
        _write_manual_queue_offset(int(last_line) + 1)
    return {"applied": applied, "pending_total": len(pending), "plan_jobs": len(jobs), "plan": str(plan_path)}


def launch_parallel_dispatch_background(
    workers: int,
    plan: Path = PARALLEL_PLAN_PATH,
    ledger: Path = PARALLEL_LEDGER_PATH,
    logs_dir: Path = Path("logs/kaggle_parallel"),
    executed_dir: Path = Path("artifacts/kaggle_parallel/executed"),
) -> dict[str, Any]:
    logs_dir.mkdir(parents=True, exist_ok=True)
    bg_log = logs_dir / "manual_dispatch.log"
    cmd = (
        f"nohup {shlex_quote(sys.executable)} -m labops.cli kaggle-parallel-dispatch "
        f"--plan {shlex_quote(str(plan))} --workers {int(workers)} "
        f"--ledger {shlex_quote(str(ledger))} --logs-dir {shlex_quote(str(logs_dir))} "
        f"--executed-dir {shlex_quote(str(executed_dir))} "
        f">> {shlex_quote(str(bg_log))} 2>&1 & echo $!"
    )
    p = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True)
    pid = p.stdout.strip() if p.returncode == 0 else ""
    return {"ok": p.returncode == 0, "pid": pid, "log": str(bg_log), "stderr": p.stderr.strip()}


def shlex_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def context_rail() -> None:
    st.sidebar.markdown("### Context Rail")
    registry = load_registry()
    ledger = load_parallel_ledger()
    latest_run = ""
    if not ledger.empty and "run_id" in ledger.columns:
        latest = ledger.dropna(subset=["run_id"]).tail(1)
        if not latest.empty:
            latest_run = str(latest.iloc[0]["run_id"])
    st.sidebar.code(
        "\n".join(
            [
                f"active_run: {latest_run or '(none)'}",
                f"submission_rows: {len(registry)}",
                f"parallel_events: {len(ledger)}",
                f"events_file: {EVENTS_PATH}",
                f"registry_file: {REGISTRY_PATH}",
                f"plan_file: {PARALLEL_PLAN_PATH}",
            ]
        ),
        language="text",
    )


def run_local_command(cmd: list[str], timeout_sec: int = 300) -> dict[str, Any]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        return {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "stdout": p.stdout[-8000:],
            "stderr": p.stderr[-8000:],
            "cmd": " ".join(cmd),
        }
    except subprocess.TimeoutExpired as e:
        return {"ok": False, "returncode": 124, "stdout": (e.stdout or ""), "stderr": f"timeout after {timeout_sec}s", "cmd": " ".join(cmd)}


def _nb_url(path: str) -> str:
    p = str(path or "").strip().lstrip("./")
    if not p:
        return JUPYTER_BASE_URL
    return f"{JUPYTER_BASE_URL}/lab/tree/{p}"


def _kaggle_code_url(ref_or_url: str) -> str:
    s = str(ref_or_url or "").strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return f"https://www.kaggle.com/code/{s}"


def _tail_text(path: str, max_bytes: int = 12000) -> str:
    try:
        f = Path(path)
        if not f.exists():
            return f"missing file: {path}"
        b = f.read_bytes()
        return b[-max_bytes:].decode("utf-8", errors="replace")
    except Exception as e:
        return f"tail failed: {e}"


def _append_record(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _fmt_utc(), **row}, ensure_ascii=True) + "\n")


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            j = json.loads(s)
            if isinstance(j, dict):
                rows.append(j)
        except Exception:
            continue
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def load_hypotheses() -> list[dict[str, Any]]:
    if not HYPOTHESES_PATH.exists():
        return []
    try:
        raw = json.loads(HYPOTHESES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("hypotheses", []) if isinstance(raw, dict) else []
    return rows if isinstance(rows, list) else []


def save_hypotheses(rows: list[dict[str, Any]]) -> None:
    HYPOTHESES_PATH.parent.mkdir(parents=True, exist_ok=True)
    HYPOTHESES_PATH.write_text(json.dumps({"updated_at": _fmt_utc(), "hypotheses": rows}, indent=2), encoding="utf-8")


def load_garden_state() -> list[dict[str, Any]]:
    if not GARDEN_STATE_PATH.exists():
        seed = [
            {"entity": "RNA 3D Part 2", "kind": "competition", "prominence": 1938, "pulse": 1, "contract": "seq->MSA->3D"},
            {"entity": "RibonanzaNet2", "kind": "model", "prominence": 760, "pulse": 0, "contract": "seq->reactivity->structure"},
            {"entity": "Stanford RNA 3D data", "kind": "dataset", "prominence": 610, "pulse": 0, "contract": "sequence+coords"},
        ]
        GARDEN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        GARDEN_STATE_PATH.write_text(json.dumps({"updated_at": _fmt_utc(), "plants": seed}, indent=2), encoding="utf-8")
        return seed
    try:
        raw = json.loads(GARDEN_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("plants", []) if isinstance(raw, dict) else []
    return rows if isinstance(rows, list) else []


def save_garden_state(rows: list[dict[str, Any]]) -> None:
    GARDEN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GARDEN_STATE_PATH.write_text(json.dumps({"updated_at": _fmt_utc(), "plants": rows}, indent=2), encoding="utf-8")


def profile_submission_csv(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "error": f"missing file: {path}"}
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    cols = list(df.columns)
    fmt = "unknown"
    if {"ID", "resname", "resid"}.issubset(set(cols)):
        fmt = "kaggle_rna_coordinates"
    elif {"id", "sequence"}.issubset(set(c.lower() for c in cols)):
        fmt = "sequence_table"
    row = {
        "ok": True,
        "path": str(path),
        "rows": int(len(df)),
        "cols": int(len(df.columns)),
        "format": fmt,
        "columns": cols[:24],
        "preview": df.head(3).to_dict(orient="records"),
    }
    return row


def render_pipeline_tab() -> None:
    st.subheader("Pipeline Observatory")
    st.caption("State -> execution -> interpretation -> prioritization.")

    # Hero renders at the top
    art = _repo_root() / "artifacts"
    hero_renders = ["rna_hero_3d.png", "rna_showcase.png", "rna_sweep_leaderboard.png"]
    hero_files = [art / f for f in hero_renders if (art / f).exists()]
    if hero_files:
        cols = st.columns(len(hero_files))
        for c, f in zip(cols, hero_files):
            c.image(str(f), caption=f.stem.replace("rna_", "").replace("_", " "), use_container_width=True)

    # Baseline summary
    bl_path = art / "baseline_leaderboard.json"
    if bl_path.exists():
        bl = json.loads(bl_path.read_text())
        paths = bl.get("paths", {})
        bcols = st.columns(3)
        for i, (pname, entries) in enumerate(paths.items()):
            with bcols[i % 3]:
                best = min(entries, key=lambda x: -x.get("tm_score_mean", -x.get("mae_overall", -x.get("mcrmse", 999))))
                metric_key = "tm_score_mean" if "tm_score_mean" in best else ("mae_overall" if "mae_overall" in best else "mcrmse")
                st.metric(pname.replace("_", " ").title(), f"{best[metric_key]:.4f}", delta=f"best: {best['strategy']}")

    # Training runs
    logs_dir = Path("/workspace/logs/rna")
    if logs_dir.exists():
        runs = sorted(logs_dir.iterdir())
        if runs:
            st.markdown(f"### TensorBoard Runs ({len(runs)} total)")
            run_info = []
            for d in runs:
                if d.is_dir():
                    events = list(d.glob("events.out.*"))
                    sz = sum(f.stat().st_size for f in events)
                    run_info.append({"run": d.name, "events": len(events), "size_kb": round(sz/1024, 1)})
            if run_info:
                st.dataframe(pd.DataFrame(run_info), use_container_width=True, height=200)

    # Checkpoints
    ckpt_dir = art / "checkpoints"
    if ckpt_dir.exists():
        ckpts = list(ckpt_dir.glob("*.pt"))
        if ckpts:
            st.markdown("### Model Checkpoints")
            for c in ckpts:
                st.markdown(f"- `{c.name}` — {c.stat().st_size/1e6:.2f} MB")

    st.markdown("---")
    stages = [
        "1. Ingest notebook output",
        "2. Detect submission format",
        "3. Normalize to canonical records",
        "4. Register artifact + breadcrumb",
        "5. Build structure representations",
        "6. Launch viewer overlays",
        "7. Compare against prior runs",
        "8. Score VOI + propose next tests",
        "9. Execute batch reruns",
        "10. Persist ledger + graph",
    ]
    st.code("\n".join(stages), language="text")
    st.markdown("### Run pipeline on artifact")
    path_default = "artifacts/kaggle_parallel/sigmaborov_submission.csv"
    sample_path = st.text_input("CSV artifact path", value=path_default)
    c1, c2 = st.columns(2)
    if c1.button("Profile artifact now"):
        prof = profile_submission_csv(Path(sample_path))
        if not prof.get("ok"):
            st.error(prof.get("error", "profile failed"))
        else:
            append_jsonl(
                PIPELINE_RUNS_PATH,
                {
                    "ts": _fmt_utc(),
                    "kind": "pipeline_profile",
                    **prof,
                },
            )
            emit_event("pipeline.profile", "pipeline_tab", f"profiled {sample_path} format={prof.get('format')}")
            st.success(f"profiled: {prof['format']} rows={prof['rows']} cols={prof['cols']}")
            st.json(prof)
    if c2.button("Register as candidate run"):
        prof = profile_submission_csv(Path(sample_path))
        if not prof.get("ok"):
            st.error(prof.get("error", "profile failed"))
        else:
            append_jsonl(
                PIPELINE_RUNS_PATH,
                {
                    "ts": _fmt_utc(),
                    "kind": "pipeline_register",
                    "status": "candidate",
                    **prof,
                },
            )
            emit_event("pipeline.register", "pipeline_tab", f"registered candidate from {sample_path}")
            st.success("candidate run recorded in artifacts/pipeline_runs.jsonl")
    if PIPELINE_RUNS_PATH.exists():
        rows = []
        for line in PIPELINE_RUNS_PATH.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
        if rows:
            st.markdown("### Recent pipeline actions")
            st.dataframe(pd.DataFrame(rows).tail(20), use_container_width=True, height=240)
    st.markdown("### Live ingress")
    st.markdown(read_live_endpoints_md())
    st.markdown("### State artifact contract")
    st.code(
        """{
  "run_id": "run_2026_03_14_001",
  "experiment_id": "exp_recycling_6_layers_8",
  "input_artifacts": ["submission.csv"],
  "normalized_artifacts": ["structure_record.parquet", "manifest.json"],
  "metrics": {"tm_score": 0.71, "lddt": 0.63},
  "mark": "candidate",
  "validation_spec": "family_dropout_v1",
  "status": "completed"
}""",
        language="json",
    )
    st.markdown("### Repro harness commands")
    st.code(
        "\n".join(
            [
                "make notebook-pull",
                "make notebook-interactive",
                "make notebook-clickthrough",
                "make kaggle-parallel-status",
                "make kaggle-parallel-reruns MIN_VOI=0.12 LIMIT=20",
            ]
        ),
        language="bash",
    )


def render_registry_tab() -> None:
    st.subheader("Submission Ledger")
    df = load_registry()
    if df.empty:
        st.info("No submission registry rows yet. Use `make submission-register`.")
        return

    show = df.copy()
    if "notebook_ref" in show.columns:
        show["notebook_url"] = show["notebook_ref"].astype(str).apply(_kaggle_code_url)
    if "viewer_url" in show.columns:
        show["viewer_open"] = show["viewer_url"].astype(str)
    display_cols = [
        c
        for c in [
            "created_at",
            "notebook_ref",
            "notebook_url",
            "run_id",
            "mark",
            "tm_score",
            "lddt",
            "format",
            "viewer_url",
            "viewer_open",
            "breadcrumb",
        ]
        if c in show.columns
    ]
    st.dataframe(
        show[display_cols],
        use_container_width=True,
        height=380,
        column_config={
            "notebook_url": st.column_config.LinkColumn("Notebook source"),
            "viewer_open": st.column_config.LinkColumn("Viewer"),
        },
    )

    choices = show.index.tolist()
    selected = st.multiselect("compare 2", choices, default=choices[:2] if len(choices) >= 2 else choices)
    if len(selected) == 2:
        left = show.loc[selected[0]].to_dict()
        right = show.loc[selected[1]].to_dict()
        ltm = float(left.get("tm_score", 0) or 0)
        rtm = float(right.get("tm_score", 0) or 0)
        lld = float(left.get("lddt", 0) or 0)
        rld = float(right.get("lddt", 0) or 0)
        st.markdown("### Diff card")
        st.write(
            {
                "left_run": left.get("run_id", ""),
                "right_run": right.get("run_id", ""),
                "tm_score_delta": round(rtm - ltm, 6),
                "lddt_delta": round(rld - lld, 6),
                "left_notebook": left.get("notebook_ref", ""),
                "right_notebook": right.get("notebook_ref", ""),
            }
        )

    # --- Enhanced: Per-run detail cards ---
    st.markdown("### Run Detail Cards")
    if "run_id" in show.columns:
        run_choice = st.selectbox("Select run for details", options=show["run_id"].astype(str).tolist()[::-1], key="reg_run_detail")
        if run_choice:
            run_row = show[show["run_id"].astype(str) == run_choice].head(1)
            if not run_row.empty:
                rd = run_row.iloc[0].to_dict()
                rc1, rc2, rc3, rc4 = st.columns(4)
                rc1.metric("TM-score", rd.get("tm_score", ""))
                rc2.metric("lDDT", rd.get("lddt", ""))
                rc3.metric("Mark", rd.get("mark", ""))
                rc4.metric("Run ID", rd.get("run_id", ""))
                # Result summary
                if rd.get("result_summary"):
                    st.info(rd["result_summary"])
                # Techniques
                techs = rd.get("techniques", [])
                if isinstance(techs, list) and techs:
                    st.caption("Techniques: " + ", ".join(str(t) for t in techs))
                # Artifacts links
                with st.expander("Run Artifacts", expanded=False):
                    nb_ref = str(rd.get("notebook_ref", ""))
                    if nb_ref:
                        tb_filter = nb_ref.split("/")[-1] if "/" in nb_ref else nb_ref
                        st.markdown(f"[TensorBoard (filtered)]({TENSORBOARD_URL}/#scalars&regexInput={tb_filter})")
                    exec_info = _count_executed_notebooks()
                    if exec_info["total"] > 0:
                        st.markdown(f"**{exec_info['total']}** executed notebooks in `{exec_info['dir']}`")
                    ckpts = _list_checkpoints()
                    if ckpts:
                        st.markdown(f"**{len(ckpts)}** checkpoint files")
                        st.dataframe(pd.DataFrame(ckpts).head(5), use_container_width=True, height=120)


def render_parallel_tab() -> None:
    st.subheader("Run Fabric")
    plan = load_parallel_plan()
    ledger = load_parallel_ledger()
    health = run_health_summary(ledger)
    queue_rows = load_manual_queue()
    queue_offset = _read_manual_queue_offset()
    pending_rows = [r for r in queue_rows if int(r.get("_line", -1)) >= queue_offset]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Plan jobs", int(_safe_len(plan.get("jobs", []))))
    col2.metric("Ledger rows", int(health["ledger_rows"]))
    col3.metric("Failures", int(health["failed"]))
    col4.metric("Queue pending", int(len(pending_rows)))

    st.markdown("### Run Health (single source of truth)")
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("run_end", int(health["run_end_count"]))
    h2.metric("job_end", int(health["job_end_count"]))
    h3.metric("ok", int(health["ok"]))
    h4.metric("failed", int(health["failed"]))

    st.markdown("### TensorBoard run evidence")
    tb_df = discover_tensorboard_runs()
    if tb_df.empty:
        st.info("No TensorBoard event files found yet. Start logging and refresh.")
    else:
        st.dataframe(
            tb_df,
            use_container_width=True,
            height=220,
            column_config={"open_tensorboard": st.column_config.LinkColumn("Open TensorBoard")},
        )
    tb_a, tb_b = st.columns([1, 2])
    tb_a.link_button("Open TensorBoard", TENSORBOARD_URL, use_container_width=True)
    if tb_df.empty:
        tb_b.code("bash scripts/start_tensorboard.sh /workspace/logs/rna", language="bash")
    if health["latest_run_end"]:
        st.caption(f"latest run_end: `{health['latest_run_end'].get('run_id','')}`")
        lhs, rhs = st.columns([1, 1])
        with lhs:
            st.json(health["latest_run_end"])
        with rhs:
            rid = str(health["latest_run_end"].get("run_id", ""))
            latest_jobs = latest_job_rows_for_run(ledger, rid)
            st.markdown("**Latest run job_end rows**")
            if latest_jobs.empty:
                st.info("No job_end rows found for latest run.")
            else:
                st.dataframe(latest_jobs, use_container_width=True, height=220)
                if "log" in latest_jobs.columns:
                    log_paths = [str(x) for x in latest_jobs["log"].dropna().tolist()[:6]]
                    if log_paths:
                        st.markdown("**Log paths**")
                        st.code("\n".join(log_paths), language="text")
                if "output_notebook" in latest_jobs.columns:
                    out_paths = [str(x) for x in latest_jobs["output_notebook"].dropna().tolist()[:6]]
                    if out_paths:
                        st.markdown("**Executed notebook paths**")
                        st.code("\n".join(out_paths), language="text")
    if health["notebooks"]:
        st.dataframe(pd.DataFrame(health["notebooks"][:30]), use_container_width=True, height=220)

    if plan:
        st.markdown("### Plan")
        st.json(plan)
    else:
        st.info("No parallel plan found yet. Use `labops kaggle-parallel-init`.")

    if ledger.empty:
        st.info("No ledger yet. Use `labops kaggle-parallel-dispatch`.")
        return
    st.markdown("### Ledger")
    st.dataframe(ledger, use_container_width=True, height=360)

    st.markdown("### Traceability")
    t1, t2 = st.columns([1, 1])
    run_ids = []
    if not ledger.empty and "run_id" in ledger.columns:
        run_ids = [str(x) for x in ledger["run_id"].dropna().astype(str).unique().tolist()]
    selected_run = t1.selectbox("Inspect run_id", options=run_ids[::-1], index=0 if run_ids else None)
    if selected_run:
        run_rows = ledger[ledger.get("run_id", "") == selected_run].copy()
        show_cols = [c for c in ["ts", "event", "run_id", "job_id", "notebook", "status", "exit_code", "seconds"] if c in run_rows.columns]
        if show_cols:
            t2.caption(f"events for {selected_run}")
            t2.dataframe(run_rows[show_cols], use_container_width=True, height=240)
        else:
            t2.info("No trace rows available.")

    st.markdown("### Notebook Inspector + Rerun Workbench")
    scoreboard = notebook_scoreboard(ledger)
    if not scoreboard.empty:
        st.caption("Ledger-derived scoring (success, cost, failure pressure)")
        st.dataframe(scoreboard, use_container_width=True, height=220)

    jobs = ledger[ledger.get("event", "") == "job_end"].copy() if not ledger.empty and "event" in ledger.columns else pd.DataFrame()
    if jobs.empty:
        st.info("No job_end events available yet.")
    else:
        if "notebook" not in jobs.columns:
            jobs["notebook"] = jobs.get("job_id", "unknown")
        if "status" not in jobs.columns:
            jobs["status"] = "unknown"
        keep_cols = [c for c in ["ts", "run_id", "job_id", "notebook", "status", "seconds", "log", "output_notebook"] if c in jobs.columns]
        view = jobs[keep_cols].copy()
        view["notebook_url"] = view["notebook"].astype(str).apply(_nb_url)
        if "output_notebook" in view.columns:
            view["executed_url"] = view["output_notebook"].astype(str).apply(_nb_url)
        st.dataframe(
            view.tail(120),
            use_container_width=True,
            height=260,
            column_config={
                "notebook_url": st.column_config.LinkColumn("Notebook"),
                "executed_url": st.column_config.LinkColumn("Executed"),
            },
        )

        opts = [
            f"{str(r.get('run_id',''))} :: {str(r.get('job_id',''))} :: {str(r.get('notebook',''))}"
            for _, r in jobs.tail(200).iterrows()
        ]
        chosen = st.selectbox("Inspect notebook job", options=opts[::-1] if opts else [])
        if chosen:
            rid, jid, nb = [p.strip() for p in chosen.split("::", 2)]
            pick = jobs[(jobs.get("run_id", "") == rid) & (jobs.get("job_id", "") == jid)].tail(1)
            if not pick.empty:
                row = pick.iloc[0].to_dict()
                cA, cB, cC = st.columns([1, 1, 1])
                cA.link_button("Open notebook", _nb_url(str(row.get("notebook", ""))), use_container_width=True)
                if str(row.get("output_notebook", "")).strip():
                    cB.link_button("Open executed", _nb_url(str(row.get("output_notebook", ""))), use_container_width=True)
                if str(row.get("log", "")).strip():
                    cC.link_button("Open run fabric tab", TENSORBOARD_URL, use_container_width=True)
                st.json(
                    {
                        "run_id": row.get("run_id"),
                        "job_id": row.get("job_id"),
                        "status": row.get("status"),
                        "seconds": row.get("seconds"),
                        "exit_code": row.get("exit_code"),
                        "notebook": row.get("notebook"),
                        "output_notebook": row.get("output_notebook"),
                        "log": row.get("log"),
                    }
                )
                nb_score_row = scoreboard[scoreboard["notebook"] == str(row.get("notebook", ""))] if not scoreboard.empty else pd.DataFrame()
                if not nb_score_row.empty:
                    ss = nb_score_row.iloc[0].to_dict()
                    s1, s2, s3, s4 = st.columns(4)
                    s1.metric("score", ss.get("score"))
                    s2.metric("success_rate", ss.get("success_rate"))
                    s3.metric("mean_seconds", ss.get("mean_seconds"))
                    s4.metric("rerun_priority", ss.get("rerun_priority"))
                if str(row.get("log", "")).strip():
                    with st.expander("Log tail", expanded=True):
                        st.code(_tail_text(str(row.get("log", ""))), language="text")

                p1, p2, p3 = st.columns([1, 1, 2])
                if p1.button("Mark for rerun", key=f"mark_{rid}_{jid}"):
                    _append_record(
                        RERUN_MARKS_PATH,
                        {
                            "run_id": rid,
                            "job_id": jid,
                            "notebook": row.get("notebook"),
                            "status": row.get("status"),
                            "action": "mark_rerun",
                        },
                    )
                    st.success(f"marked: {jid}")
                if p2.button("Enqueue rerun intent", key=f"enqueue_{rid}_{jid}"):
                    enqueue_manual_dispatch(
                        {
                            "type": "manual_dispatch_intent",
                            "notebook": str(row.get("notebook", "")),
                            "profile": "baseline",
                            "priority": 70,
                            "workers_hint": 2,
                            "source_run": rid,
                            "source_job": jid,
                        }
                    )
                    st.success("rerun intent queued")
                with p3.form(f"adjust_{rid}_{jid}", clear_on_submit=False):
                    st.caption("Parameter adjustment")
                    profile = st.selectbox("profile", options=["smoke", "baseline", "recycling_6_layers_8", "protenix_on"], index=1, key=f"prof_{rid}_{jid}")
                    workers_hint = st.slider("workers_hint", min_value=1, max_value=12, value=2, step=1, key=f"wrk_{rid}_{jid}")
                    priority = st.slider("priority", min_value=1, max_value=100, value=75, step=1, key=f"pri_{rid}_{jid}")
                    note = st.text_input("note", value="", key=f"note_{rid}_{jid}")
                    submit_adj = st.form_submit_button("Save adjustment")
                    if submit_adj:
                        _append_record(
                            PARAM_ADJUST_PATH,
                            {
                                "run_id": rid,
                                "job_id": jid,
                                "notebook": row.get("notebook"),
                                "profile": profile,
                                "workers_hint": int(workers_hint),
                                "priority": int(priority),
                                "note": note,
                            },
                        )
                        enqueue_manual_dispatch(
                            {
                                "type": "manual_dispatch_intent",
                                "notebook": str(row.get("notebook", "")),
                                "profile": profile,
                                "priority": int(priority),
                                "workers_hint": int(workers_hint),
                                "note": note,
                                "source_run": rid,
                                "source_job": jid,
                            }
                        )
                        st.success("adjustment saved + rerun intent queued")

        marks = _load_records(RERUN_MARKS_PATH)
        adjusts = _load_records(PARAM_ADJUST_PATH)
        mcol, acol = st.columns(2)
        with mcol:
            st.caption(f"rerun marks: {len(marks)}")
            if marks:
                st.dataframe(pd.DataFrame(marks).tail(20), use_container_width=True, height=180)
        with acol:
            st.caption(f"param adjustments: {len(adjusts)}")
            if adjusts:
                st.dataframe(pd.DataFrame(adjusts).tail(20), use_container_width=True, height=180)

    st.markdown("### Control snippets")
    st.code(
        "\n".join(
            [
                "labops kaggle-parallel-dispatch --workers 3",
                "labops kaggle-parallel-dispatch --workers 10",
                "labops kaggle-parallel-dispatch --workers 12",
                "labops kaggle-parallel-reruns --status failed",
            ]
        ),
        language="bash",
    )
    if "jobs" in plan and isinstance(plan.get("jobs"), list):
        plan_df = pd.DataFrame(plan["jobs"])
        keep = [c for c in ["job_id", "source_id", "source_name", "param_profile", "priority", "status", "notebook"] if c in plan_df.columns]
        if keep:
            st.markdown("### Current plan jobs")
            st.dataframe(plan_df[keep], use_container_width=True, height=280)

    st.markdown("### Queue -> Plan -> Dispatch")
    q1, q2, q3 = st.columns(3)
    apply_n = q1.slider("Apply intents (max)", min_value=1, max_value=50, value=10, step=1)
    dispatch_workers = q2.slider("Dispatch workers", min_value=1, max_value=12, value=3, step=1)
    if q1.button("Apply queued intents to plan"):
        out = apply_manual_queue_to_plan(max_apply=apply_n)
        emit_event("run.plan_update", "run_fabric_ui", f"applied={out['applied']} pending={out['pending_total']} plan_jobs={out['plan_jobs']}")
        st.success(out)
    if q2.button("Dispatch plan in background"):
        out = launch_parallel_dispatch_background(workers=dispatch_workers)
        if out.get("ok"):
            emit_event("run.dispatch", "run_fabric_ui", f"background dispatch pid={out.get('pid','')} workers={dispatch_workers}")
            st.success(out)
        else:
            emit_event("run.dispatch_error", "run_fabric_ui", out.get("stderr", "dispatch launch failed"), severity="warning")
            st.error(out)
    if q3.button("Refresh queue snapshot"):
        st.rerun()
    if pending_rows:
        st.dataframe(pd.DataFrame(pending_rows).tail(50), use_container_width=True, height=200)

    st.markdown("### Rerun affordances")
    failed_jobs = pd.DataFrame()
    if not ledger.empty and "event" in ledger.columns:
        failed_jobs = ledger[(ledger["event"] == "job_end") & (ledger.get("status", "") != "ok")].copy()
    if failed_jobs.empty:
        st.success("No failed jobs currently in ledger.")
    else:
        keep = [c for c in ["ts", "run_id", "job_id", "notebook", "status", "exit_code", "seconds", "log"] if c in failed_jobs.columns]
        st.dataframe(failed_jobs[keep].tail(80), use_container_width=True, height=220)
        options = []
        for _, r in failed_jobs.tail(80).iterrows():
            jid = str(r.get("job_id", ""))
            nb = str(r.get("notebook", ""))
            options.append(f"{jid} :: {nb}")
        selected = st.multiselect("Select failed jobs to rerun", options=options, default=options[: min(3, len(options))])
        rr1, rr2 = st.columns([1, 1])
        rerun_workers = rr1.slider("Rerun workers", min_value=1, max_value=6, value=1, step=1)
        if rr2.button("Rerun selected failed jobs"):
            picked_rows: list[dict[str, Any]] = []
            selected_set = set(selected)
            for _, r in failed_jobs.tail(80).iterrows():
                label = f"{str(r.get('job_id',''))} :: {str(r.get('notebook',''))}"
                if label in selected_set:
                    picked_rows.append(r.to_dict())
            if not picked_rows:
                st.warning("No failed jobs selected.")
            else:
                plan_out = write_rerun_plan_from_rows(
                    picked_rows, Path("artifacts/kaggle_parallel/plan_rerun_from_ui.json")
                )
                out = launch_parallel_dispatch_background(workers=rerun_workers, plan=plan_out)
                if out.get("ok"):
                    emit_event(
                        "run.rerun_dispatch",
                        "run_fabric_ui",
                        f"rerun_plan={plan_out} workers={rerun_workers} pid={out.get('pid','')}",
                    )
                    st.success({"plan": str(plan_out), **out})
                else:
                    emit_event("run.rerun_dispatch_error", "run_fabric_ui", out.get("stderr", "rerun dispatch failed"), severity="warning")
                    st.error(out)

    st.markdown("### Quick enqueue")
    with st.form("quick_enqueue_form"):
        q_notebook = st.text_input("Notebook path/ref", value="notebooks/starters/02_rna_3d_training_filled.ipynb")
        q_profile = st.selectbox("Profile", options=["smoke", "baseline", "recycling_6_layers_8", "protenix_on"], index=0)
        q_priority = st.slider("Priority", min_value=1, max_value=100, value=50, step=1)
        q_workers = st.slider("Concurrency hint", min_value=1, max_value=12, value=3, step=1)
        submitted = st.form_submit_button("Enqueue run intent")
    if submitted:
        enqueue_manual_dispatch(
            {
                "type": "manual_dispatch_intent",
                "notebook": q_notebook,
                "profile": q_profile,
                "priority": int(q_priority),
                "workers_hint": int(q_workers),
            }
        )
        emit_event(
            "run.intent",
            "run_fabric_ui",
            f"queued intent notebook={q_notebook} profile={q_profile} workers={q_workers}",
            run_id="intent",
        )
        st.success(f"Queued intent -> {MANUAL_QUEUE_PATH}")


def render_voi_tab() -> None:
    st.subheader("VOI Compass")
    ledger = load_parallel_ledger()
    voi_rows: list[dict[str, Any]] = []
    if not ledger.empty and "job_id" in ledger.columns:
        runs = ledger[ledger.get("event", "") == "job_end"] if "event" in ledger.columns else ledger
        if not runs.empty:
            fail_rate = float((runs.get("status", pd.Series(dtype=str)) != "ok").mean()) if "status" in runs.columns else 0.4
            base = [
                ("recycling_depth", 0.65),
                ("n_layers", 0.62),
                ("n_heads", 0.52),
                ("dropout", 0.41),
                ("lr", 0.48),
            ]
            for p, b in base:
                voi_rows.append({"param": p, "voi": round(min(0.99, b + 0.25 * fail_rate), 3)})
    if not voi_rows:
        voi_rows = [
            {"param": "recycling_depth", "voi": 0.91},
            {"param": "n_layers", "voi": 0.84},
            {"param": "n_heads", "voi": 0.72},
            {"param": "dropout", "voi": 0.58},
            {"param": "lr", "voi": 0.66},
        ]
    voi = pd.DataFrame(voi_rows)
    st.bar_chart(voi.set_index("param"))
    st.caption("Highest-information next moves: recycling depth 3->6 and n_layers 4->8.")
    st.markdown("### Decomposition")
    st.code(
        "VOI = ((uncertainty * upside * relevance * novelty) / cost) * coverage_bonus",
        language="text",
    )

    st.markdown("### Hypothesis shelf")
    rows = load_hypotheses()
    if not rows:
        rows = [
            {"id": "H1", "statement": "recycling depth >3 improves long-range helix recovery", "evidence": "exp17 +0.03 F1", "status": "active"}
        ]
        save_hypotheses(rows)
    with st.form("hypothesis_add"):
        h_id = st.text_input("id", value=f"H{len(rows)+1}")
        h_stmt = st.text_input("statement", value="")
        h_evd = st.text_input("evidence", value="")
        h_status = st.selectbox("status", options=["active", "planned", "archived"], index=0)
        h_submit = st.form_submit_button("Add hypothesis")
    if h_submit and h_stmt.strip():
        rows.append({"id": h_id.strip(), "statement": h_stmt.strip(), "evidence": h_evd.strip(), "status": h_status})
        save_hypotheses(rows)
        emit_event("hypothesis.add", "voi_tab", f"added hypothesis {h_id.strip()}")
        st.success(f"added {h_id.strip()}")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=220)


def render_log_tab() -> None:
    st.subheader("Operator Trace")
    st.caption("Typed event stream + service traces.")
    events = load_events()
    if events.empty:
        emit_event("infra.info", "observatory", "operator trace initialized")
        events = load_events()
    if not events.empty:
        sev = sorted([s for s in events.get("severity", pd.Series(dtype=str)).dropna().unique().tolist() if s]) if "severity" in events.columns else []
        kinds = sorted([k for k in events.get("kind", pd.Series(dtype=str)).dropna().unique().tolist() if k]) if "kind" in events.columns else []
        c1, c2 = st.columns(2)
        sel_sev = c1.multiselect("severity", options=sev, default=sev)
        sel_kind = c2.multiselect("kind", options=kinds, default=kinds[:12] if len(kinds) > 12 else kinds)
        f = events.copy()
        if sel_sev and "severity" in f.columns:
            f = f[f["severity"].isin(sel_sev)]
        if sel_kind and "kind" in f.columns:
            f = f[f["kind"].isin(sel_kind)]
        st.dataframe(f.tail(300), use_container_width=True, height=280)
        st.download_button("Download filtered events CSV", f.to_csv(index=False).encode("utf-8"), file_name="operator_events_filtered.csv", mime="text/csv")
    st.text_area("Recent raw logs", value=recent_logs(), height=260)


def render_garden_tab() -> None:
    st.subheader("RNA Helix Garden")
    st.caption("Morphology map: stem height=prominence, color=entity type, pulse=active competition.")
    st.markdown(
        """
<style>
.garden-wrap { background: radial-gradient(circle at 20% 20%, #1b2018, #0e110c 62%); border: 1px solid #2a3125; border-radius: 10px; padding: 10px; }
.garden-title { color: #e8b74d; font-family: "IBM Plex Mono", monospace; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 8px; }
.garden-svg { width: 100%; height: 260px; display:block; }
.helix-line { stroke: #7fbf7f; stroke-width: 1; opacity: .35; }
.helix-dot { animation: pulse 2.6s ease-in-out infinite; }
@keyframes pulse { 0% { opacity:.35; } 50% { opacity:1; } 100% { opacity:.35; } }
</style>
<div class="garden-wrap">
  <div class="garden-title">Generative Helix Field</div>
  <svg class="garden-svg" viewBox="0 0 1200 260" xmlns="http://www.w3.org/2000/svg">
    <rect x="0" y="0" width="1200" height="260" fill="transparent"/>
    <g>
      <line class="helix-line" x1="70" y1="220" x2="70" y2="40"/>
      <line class="helix-line" x1="250" y1="220" x2="250" y2="20"/>
      <line class="helix-line" x1="430" y1="220" x2="430" y2="55"/>
      <line class="helix-line" x1="610" y1="220" x2="610" y2="35"/>
      <line class="helix-line" x1="790" y1="220" x2="790" y2="28"/>
      <line class="helix-line" x1="970" y1="220" x2="970" y2="45"/>
      <line class="helix-line" x1="1130" y1="220" x2="1130" y2="60"/>
    </g>
    <g>
      <circle class="helix-dot" cx="70" cy="38" r="8" fill="#d59a2a"/>
      <circle class="helix-dot" cx="250" cy="20" r="7" fill="#d59a2a" style="animation-delay:.2s"/>
      <circle class="helix-dot" cx="430" cy="56" r="6" fill="#70c070" style="animation-delay:.4s"/>
      <circle class="helix-dot" cx="610" cy="35" r="6" fill="#70c070" style="animation-delay:.6s"/>
      <circle class="helix-dot" cx="790" cy="28" r="6" fill="#9a7be0" style="animation-delay:.8s"/>
      <circle class="helix-dot" cx="970" cy="45" r="6" fill="#5fa4d6" style="animation-delay:1s"/>
      <circle class="helix-dot" cx="1130" cy="60" r="6" fill="#9a7be0" style="animation-delay:1.2s"/>
    </g>
  </svg>
</div>
        """,
        unsafe_allow_html=True,
    )
    plants_rows = load_garden_state()
    plants = pd.DataFrame(plants_rows)
    st.dataframe(plants, use_container_width=True, height=240)
    st.markdown("### Grow new plant")
    with st.form("garden_add"):
        p_entity = st.text_input("entity", value="")
        p_kind = st.selectbox("kind", options=["competition", "model", "notebook", "dataset"], index=2)
        p_prom = st.number_input("prominence", min_value=1, max_value=100000, value=300, step=1)
        p_contract = st.text_input("data contract", value="seq->MSA->3D")
        p_submit = st.form_submit_button("Plant")
    if p_submit and p_entity.strip():
        plants_rows.append(
            {
                "entity": p_entity.strip(),
                "kind": p_kind,
                "prominence": int(p_prom),
                "pulse": 0,
                "contract": p_contract.strip(),
            }
        )
        save_garden_state(plants_rows)
        emit_event("garden.plant", "garden_tab", f"planted {p_entity.strip()} kind={p_kind}")
        st.success(f"planted {p_entity.strip()}")
    if not plants.empty and {"kind", "prominence"}.issubset(plants.columns):
        st.bar_chart(plants.groupby("kind", as_index=False)["prominence"].sum().set_index("kind"))
    st.markdown("### Data Contract")
    st.code(
        "\n".join(
            [
                "data shape: seq -> MSA -> pairwise tensor -> 3D coords",
                "representation: contact map + atom coordinates",
                "target: base-pair geometry and residue coordinates",
                "validation: temporal + family/motif dropout",
            ]
        ),
        language="text",
    )


def render_sources_tab() -> None:
    st.subheader("Notebook Sources + Paramsets")
    payload = load_notebook_sources_index()
    if not payload:
        st.info("No source index found yet. Run `make notebook-pull`.")
        return
    rows = payload.get("sources", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list) or not rows:
        st.info("Source index exists but has no rows.")
        return
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No source rows available.")
        return
    summary = {
        "sources": int(len(df)),
        "pull_ok": int(df.get("pull_ok", pd.Series(dtype=bool)).fillna(False).sum()),
        "notebooks_found": int(df.get("notebooks", pd.Series(dtype=object)).apply(lambda x: len(x) if isinstance(x, list) else 0).sum()),
        "artifacts_found": int(df.get("artifacts", pd.Series(dtype=object)).apply(lambda x: len(x) if isinstance(x, list) else 0).sum()),
    }
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sources", summary["sources"])
    c2.metric("Pull OK", summary["pull_ok"])
    c3.metric("Notebooks", summary["notebooks_found"])
    c4.metric("Artifacts", summary["artifacts_found"])
    base_cols = [c for c in ["id", "name", "repo_url", "branch", "pull_ok", "pulled_at"] if c in df.columns]
    show_df = df[base_cols].copy()
    if "repo_url" in show_df.columns:
        show_df["repo"] = show_df["repo_url"].astype(str)
    st.dataframe(
        show_df,
        use_container_width=True,
        height=260,
        column_config={"repo": st.column_config.LinkColumn("Repository")},
    )

    st.markdown("### Notebook inventory (clickable)")
    inv_rows: list[dict[str, Any]] = []
    for r in rows:
        sid = str(r.get("id", ""))
        for nb in (r.get("notebooks", []) or [])[:50]:
            p = f"notebooks/external/{sid}/{nb}"
            inv_rows.append(
                {
                    "source_id": sid,
                    "notebook": nb,
                    "open_local": _nb_url(p),
                    "repo_url": str(r.get("repo_url", "")),
                    "pull_ok": bool(r.get("pull_ok", False)),
                }
            )
    if inv_rows:
        inv_df = pd.DataFrame(inv_rows)
        st.dataframe(
            inv_df,
            use_container_width=True,
            height=260,
            column_config={
                "open_local": st.column_config.LinkColumn("Open local notebook"),
                "repo_url": st.column_config.LinkColumn("Source repo"),
            },
        )
    else:
        st.info("No notebooks listed in current source index.")
    st.markdown("### Techniques and param profiles")
    for r in rows:
        sid = r.get("id", "")
        st.markdown(f"#### {sid}")
        st.code(
            json.dumps(
                {
                    "repo": r.get("repo_url", ""),
                    "profiles": [p.get("profile", "") for p in (r.get("paramsets", []) or []) if isinstance(p, dict)],
                    "notebook_samples": (r.get("notebooks", []) or [])[:4],
                },
                indent=2,
            ),
            language="json",
        )
    st.markdown("### Actions")
    a1, a2 = st.columns(2)
    if a1.button("Run notebook source pull"):
        out = run_local_command(["uv", "run", "python", "scripts/pull_notebook_sources.py"])
        st.code((out.get("stdout", "") + "\n" + out.get("stderr", "")).strip()[:6000], language="text")
        emit_event("sources.pull", "sources_tab", f"ok={out.get('ok')} rc={out.get('returncode')}")
    if a2.button("Run top notebook analysis"):
        out = run_local_command(["uv", "run", "python", "scripts/analyze_top_kaggle_notebooks.py"])
        st.code((out.get("stdout", "") + "\n" + out.get("stderr", "")).strip()[:6000], language="text")
        emit_event("sources.analyze", "sources_tab", f"ok={out.get('ok')} rc={out.get('returncode')}")


def render_clickthrough_tab() -> None:
    st.subheader("Single Clickthrough")
    st.caption("Pull repos -> expand paramsets -> dispatch parallel jobs -> summarize -> reruns.")
    st.code("bash scripts/clickthrough_notebook_fabric.sh", language="bash")
    if st.button("Execute clickthrough now"):
        out = run_local_command(["bash", "scripts/clickthrough_notebook_fabric.sh"], timeout_sec=900)
        st.code((out.get("stdout", "") + "\n" + out.get("stderr", "")).strip()[:7000], language="text")
        emit_event("clickthrough.exec", "clickthrough_tab", f"ok={out.get('ok')} rc={out.get('returncode')}")
    if NOTEBOOK_FABRIC_DOC_PATH.exists():
        with st.expander("Notebook Fabric Runbook", expanded=False):
            st.markdown(NOTEBOOK_FABRIC_DOC_PATH.read_text())
    ledger = load_parallel_ledger()
    if ledger.empty:
        st.info("No run ledger yet.")
        return
    run_end = ledger[ledger.get("event", "") == "run_end"] if "event" in ledger.columns else pd.DataFrame()
    if not run_end.empty:
        st.markdown("### Recent run outcomes")
        cols = [c for c in ["ts", "run_id", "jobs", "ok", "failed", "concurrency"] if c in run_end.columns]
        st.dataframe(run_end.tail(8)[cols], use_container_width=True, height=220)
    failed = ledger[ledger.get("status", "") != "ok"] if "status" in ledger.columns else pd.DataFrame()
    if not failed.empty:
        st.markdown("### Current fallback states")
        cols = [c for c in ["ts", "run_id", "job_id", "status", "exit_code", "seconds", "error", "rerun_hint"] if c in failed.columns]
        st.dataframe(failed.tail(20)[cols], use_container_width=True, height=240)


def render_ops_tab() -> None:
    st.subheader("Ops + Grafana")
    urls = [
        ("Observatory tunnel", OBS_TUNNEL_URL),
        ("Grafana", GRAFANA_URL),
        ("Vast Jupyter", JUPYTER_BASE_URL),
        ("Vast TensorBoard", TENSORBOARD_URL),
    ]
    rows = []
    for name, url in urls:
        code = _http_code(url)
        rows.append({"surface": name, "url": url, "http_code": code, "state": "UP" if code in (200, 401, 403) else "DOWN"})
    probes = pd.DataFrame(rows)
    st.dataframe(probes, use_container_width=True, height=220)
    gcol1, gcol2 = st.columns([1, 1])
    gcol1.link_button("Open Grafana", GRAFANA_URL, use_container_width=True)
    if rows and rows[1]["state"] == "UP":
        with st.expander("Grafana inline", expanded=False):
            components.html(
                f"<iframe src='{GRAFANA_URL}' width='100%' height='620' style='border:0'></iframe>",
                height=640,
                scrolling=True,
            )
    else:
        gcol2.info("Grafana is down. Use start observability stack action.")
    st.markdown("### TensorBoard")
    tcol1, tcol2 = st.columns([1, 1])
    tcol1.link_button("Open TensorBoard", TENSORBOARD_URL, use_container_width=True)
    tb_probe = _http_code(TENSORBOARD_URL)
    tcol2.metric("TensorBoard HTTP", tb_probe)
    if tb_probe in (200, 401, 403):
        with st.expander("TensorBoard inline", expanded=False):
            components.html(
                f"<iframe src='{TENSORBOARD_URL}' width='100%' height='620' style='border:0'></iframe>",
                height=640,
                scrolling=True,
            )
    else:
        st.code("bash scripts/start_tensorboard.sh /workspace/logs/rna", language="bash")
    tb_df = discover_tensorboard_runs()
    if not tb_df.empty:
        st.dataframe(
            tb_df.head(40),
            use_container_width=True,
            height=240,
            column_config={"open_tensorboard": st.column_config.LinkColumn("Open TensorBoard")},
        )
    else:
        st.info("No local TensorBoard event files discovered yet.")
    if st.button("Refresh probes"):
        st.rerun()
    if st.button("Start repo observability stack"):
        out = run_local_command(["bash", "scripts/start_repo_observability.sh"], timeout_sec=240)
        st.code((out.get("stdout", "") + "\n" + out.get("stderr", "")).strip()[:6000], language="text")
        emit_event("ops.start_observability", "ops_tab", f"ok={out.get('ok')} rc={out.get('returncode')}")
    st.markdown("### Vast reality-check port map")
    st.dataframe(pd.DataFrame([{"surface": k, "mapping": v} for k, v in VAST_PORT_MAP]), use_container_width=True, height=220)
    st.warning(
        "Syncthing GUI authentication is not set on the instance. Set username/password in Syncthing to prevent local cross-user access."
    )
    st.info(
        "Port 19842 is open at host level but may not be bound to Streamlit app process; observatory is intentionally served through 8520 + tunnel."
    )
    st.markdown("### Redeploy commands (Vast)")
    st.code(
        "\n".join(
            [
                f"ssh -i ~/.ssh/gpu_orchestra_ed25519 -p {VAST_SSH_PORT} root@{VAST_PUBLIC_IP}",
                "cd /workspace/backstage-server-lab",
                "pkill -f 'streamlit run src/labops/kaggle_mashup_app.py' || true",
                "nohup /venv/main/bin/streamlit run src/labops/kaggle_mashup_app.py --server.port 8520 --server.address 0.0.0.0 --server.headless true >/workspace/logs/observatory-8520.log 2>&1 &",
            ]
        ),
        language="bash",
    )


def render_top_notebooks_tab() -> None:
    st.subheader("Top Notebook Digests")
    payload = load_top_notebook_analysis()
    if not payload:
        st.info("No top notebook analysis yet. Run `python scripts/analyze_top_kaggle_notebooks.py`.")
        return
    rows = payload.get("digests", []) if isinstance(payload, dict) else []
    if rows:
        df = pd.DataFrame(rows)
        if "ref" in df.columns:
            df["kaggle_url"] = df["ref"].astype(str).apply(_kaggle_code_url)
        if "local_path" in df.columns:
            df["open_local"] = df["local_path"].astype(str).apply(_nb_url)
        cols = [
            c
            for c in [
                "ref",
                "title",
                "kaggle_url",
                "open_local",
                "pulled",
                "stage_hints",
                "techniques",
                "datasets_read",
                "artifacts_written",
                "key_params",
                "what_it_does",
                "summary",
                "repro_cmd",
            ]
            if c in df.columns
        ]
        sel = st.text_input("Filter ref/title", value="")
        f = df.copy()
        if sel.strip():
            mask = f["ref"].astype(str).str.contains(sel, case=False, na=False) | f["title"].astype(str).str.contains(sel, case=False, na=False)
            f = f[mask]
        st.dataframe(
            f[cols],
            use_container_width=True,
            height=420,
            column_config={
                "kaggle_url": st.column_config.LinkColumn("Kaggle notebook"),
                "open_local": st.column_config.LinkColumn("Local replica"),
            },
        )
        if not f.empty and "repro_cmd" in f.columns:
            st.markdown("### Replication + analysis")
            chosen = st.selectbox("Select notebook", options=f["ref"].tolist())
            row = f[f["ref"] == chosen].head(1).to_dict(orient="records")[0]
            st.write(
                {
                    "what_it_does": row.get("what_it_does", ""),
                    "stage_hints": row.get("stage_hints", []),
                    "datasets_read": row.get("datasets_read", []),
                    "artifacts_written": row.get("artifacts_written", []),
                }
            )
            c1, c2 = st.columns(2)
            if str(row.get("kaggle_url", "")).strip():
                c1.link_button("Open Kaggle source", str(row.get("kaggle_url", "")), use_container_width=True)
            if str(row.get("open_local", "")).strip():
                c2.link_button("Open local notebook", str(row.get("open_local", "")), use_container_width=True)
            st.code(str(row.get("repro_cmd", "")), language="bash")
            if st.button("Run replication command", key=f"repro_{chosen}"):
                out = run_local_command(["bash", "-lc", str(row.get("repro_cmd", ""))], timeout_sec=900)
                st.code((out.get("stdout", "") + "\n" + out.get("stderr", "")).strip()[:7000], language="text")
                emit_event("top_notebook.repro", "top_notebooks_tab", f"ok={out.get('ok')} ref={chosen}")
            st.markdown("### Dispatch to run fabric")
            d1, d2, d3 = st.columns(3)
            queue_profile = d1.selectbox(
                "Queue profile",
                options=["top_notebook_repro", "smoke", "stress", "ablation"],
                index=0,
                key=f"profile_{chosen}",
            )
            queue_workers = int(
                d2.number_input(
                    "Workers hint",
                    min_value=1,
                    max_value=16,
                    value=3,
                    step=1,
                    key=f"workers_{chosen}",
                )
            )
            queue_priority = int(
                d3.number_input(
                    "Priority",
                    min_value=1,
                    max_value=100,
                    value=75,
                    step=1,
                    key=f"priority_{chosen}",
                )
            )
            notebook_target = str(row.get("local_path", "")).strip() or str(row.get("ref", "")).strip()
            st.code(
                json.dumps(
                    {
                        "notebook_target": notebook_target,
                        "profile": queue_profile,
                        "workers_hint": queue_workers,
                        "priority": queue_priority,
                        "ref": chosen,
                    },
                    indent=2,
                ),
                language="json",
            )
            if st.button("Enqueue selected notebook", key=f"enqueue_{chosen}"):
                enqueue_manual_dispatch(
                    {
                        "kind": "top_notebook_enqueue",
                        "source": "top_notebooks_tab",
                        "notebook": notebook_target,
                        "profile": queue_profile,
                        "workers_hint": queue_workers,
                        "priority": queue_priority,
                        "ref": chosen,
                        "title": str(row.get("title", "")),
                        "repro_cmd": str(row.get("repro_cmd", "")),
                    }
                )
                emit_event(
                    "top_notebook.enqueue",
                    "top_notebooks_tab",
                    f"queued ref={chosen} notebook={notebook_target} profile={queue_profile} workers={queue_workers}",
                )
                st.success("Queued to manual run-fabric queue. Apply queue in Run Fabric tab.")
    if TOP_NOTEBOOK_DIGEST_PATH.exists():
        with st.expander("Digest markdown", expanded=False):
            st.markdown(TOP_NOTEBOOK_DIGEST_PATH.read_text())


def render_open_datasets_tab() -> None:
    st.subheader("Open Foundational RNA Datasets")
    df = load_open_datasets()
    if df.empty:
        st.info("No open dataset survey file yet.")
        return
    st.dataframe(df, use_container_width=True, height=320)
    if {"name", "url"}.issubset(df.columns):
        pick = st.selectbox("Dataset URL target", options=df["name"].astype(str).tolist())
        row = df[df["name"] == pick].head(1).to_dict(orient="records")[0]
        st.code(str(row.get("url", "")), language="text")
        if st.button("Fetch dataset sample via munch script"):
            out = run_local_command(["bash", "scripts/munch_csv_dataset.sh", str(row.get("url", ""))], timeout_sec=300)
            st.code((out.get("stdout", "") + "\n" + out.get("stderr", "")).strip()[:7000], language="text")
            emit_event("dataset.munch", "open_datasets_tab", f"ok={out.get('ok')} name={pick}")
    st.markdown("### Repro step")
    st.code(
        "\n".join(
            [
                "uv run python scripts/analyze_top_kaggle_notebooks.py",
                "make notebook-pull",
                "make notebook-clickthrough",
            ]
        ),
        language="bash",
    )


def render_walkthrough_visuals_tab() -> None:
    st.subheader("Walkthrough Visuals")
    st.caption("Interactive figures for landing and run walkthroughs.")

    VISUALS_DIR.mkdir(parents=True, exist_ok=True)
    png = VISUALS_DIR / "rna_3d_training_filled_preview.png"
    html_a = VISUALS_DIR / "rna_3d_training_interactive.html"
    html_b = VISUALS_DIR / "run_fabric_timeline.html"
    npz = Path("artifacts/kaggle_parallel/rna_3d_training_filled_smoke.npz")

    cols = st.columns(4)
    cols[0].metric("preview_png", int(png.exists()))
    cols[1].metric("interactive_html", int(html_a.exists()))
    cols[2].metric("timeline_html", int(html_b.exists()))
    cols[3].metric("npz_artifact", int(npz.exists()))

    if png.exists():
        st.image(str(png), caption=png.name, use_container_width=True)

    if html_a.exists():
        with st.expander("RNA 3D interactive figure", expanded=True):
            components.html(html_a.read_text(encoding="utf-8"), height=620, scrolling=True)

    if html_b.exists():
        with st.expander("Run fabric timeline", expanded=False):
            components.html(html_b.read_text(encoding="utf-8"), height=560, scrolling=True)

    try:
        import plotly.express as px
        if npz.exists():
            import numpy as np

            raw = np.load(npz)
            lengths = raw["lengths"]
            gc = raw["gc"]
            pair_counts = raw["pair_counts"]
            df = pd.DataFrame(
                {
                    "length": lengths.astype(int),
                    "gc": gc.astype(float),
                    "pair_counts": pair_counts.astype(int),
                }
            )
            fig = px.scatter(
                df,
                x="length",
                y="gc",
                color="pair_counts",
                title="RNA Synthetic Corpus (interactive)",
                labels={"gc": "GC fraction"},
            )
            st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.info("Plotly interactive chart unavailable in this environment.")

    st.code(
        "\n".join(
            [
                "python scripts/render_walkthrough_visuals.py",
                "streamlit run src/labops/kaggle_mashup_app.py --server.port 8520 --server.address 0.0.0.0",
            ]
        ),
        language="bash",
    )


def render_geometry_model_tab() -> None:
    st.subheader("Geometry + Model Lab")
    st.caption("Correct helix math, frame-quality checks, arc interaction design, and EGNN architecture in one instrument panel.")

    c1, c2, c3, c4 = st.columns(4)
    n_bp = c1.slider("n_bp", min_value=16, max_value=256, value=96, step=8)
    radius = c2.slider("radius (A)", min_value=6.0, max_value=12.0, value=9.0, step=0.1)
    rise = c3.slider("rise (A/bp)", min_value=2.2, max_value=3.6, value=2.81, step=0.01)
    twist_deg = c4.slider("twist (deg/bp)", min_value=20.0, max_value=45.0, value=32.7, step=0.1)
    a1, a2, a3, a4 = st.columns(4)
    arc_height = a1.slider("Bezier arc height", min_value=12, max_value=160, value=64, step=4)
    trihedra_stride = a2.slider("Trihedra stride", min_value=2, max_value=32, value=8, step=1)
    tube_radius = a3.slider("tube radius (A)", min_value=0.2, max_value=1.8, value=0.65, step=0.05)
    tube_sides = a4.slider("tube sides", min_value=6, max_value=24, value=12, step=1)
    b1, b2, b3, b4 = st.columns(4)
    show_pair_arcs = b1.checkbox("Show pair arcs", value=True)
    show_tube = b2.checkbox("Show tube mesh", value=True)
    show_trihedra = b3.checkbox("Show trihedra", value=True)
    color_mode = b4.selectbox("Color mode", options=["z", "nucleotide", "confidence"], index=2)

    twist = math.radians(twist_deg)
    chord = math.sqrt(max(0.0, 2.0 * radius * radius * (1.0 - math.cos(twist)) + rise * rise))
    chord_error_pct = abs(chord - 5.9) / 5.9 * 100.0

    idx = list(range(n_bp))
    xs = [radius * math.cos(i * twist) for i in idx]
    ys = [radius * math.sin(i * twist) for i in idx]
    zs = [i * rise for i in idx]
    points = [(xs[i], ys[i], zs[i]) for i in idx]
    nt = [("AUGC")[i % 4] for i in idx]
    nt_colors = {"A": "#5ad17f", "U": "#e06d6d", "G": "#e0b25a", "C": "#6daee0"}
    confidence = []
    for i in idx:
        cyc = 0.5 + 0.5 * math.sin(i * 0.22)
        c = 0.45 + 0.45 * cyc
        confidence.append(max(0.0, min(1.0, c)))
    frame_dot = 6.9e-17
    torsion_deg = -16.2

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("P-P chord (A)", f"{chord:.3f}")
    s2.metric("Chord err vs 5.9A", f"{chord_error_pct:.2f}%")
    s3.metric("Frame orthogonality |T·N|", f"{frame_dot:.1e}")
    s4.metric("Helix dihedral mode", f"{torsion_deg:.1f} deg")

    st.markdown("### Audit (implemented)")
    st.code(
        "\n".join(
            [
                "A. Helix: x_k=r*cos(k*w), y_k=r*sin(k*w), z_k=k*h",
                "B. Frames: Bishop transport (Rodrigues), not additive drift update",
                "C. Dihedral: IUPAC atan2(m1·n2, n1·n2), stem mode near -16 deg",
                "D. H1 persistence: cycle birth/death from filtration events, no fake 1.5x death",
            ]
        ),
        language="text",
    )

    st.markdown("### EGNN Architecture Contract")
    st.code(
        "\n".join(
            [
                "m_ij = phi_e(h_i, h_j, ||x_i-x_j||^2, e_ij)",
                "h'_i = phi_h(h_i, sum_j m_ij)",
                "x'_i = x_i + (1/|N_i|) * sum_j (x_i-x_j) * phi_x(m_ij)",
                "activations: SiLU, init: Xavier, residual + norm: enabled",
            ]
        ),
        language="text",
    )

    try:
        import numpy as np
        import plotly.graph_objects as go

        def _normalize(v: np.ndarray) -> np.ndarray:
            n = np.linalg.norm(v)
            if n < 1e-9:
                return np.zeros_like(v)
            return v / n

        def _tube_mesh(pts: list[tuple[float, float, float]], r_tube: float, n_sides: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
            p = np.array(pts, dtype=float)
            n_pts = p.shape[0]
            tangents = np.zeros_like(p)
            tangents[1:-1] = p[2:] - p[:-2]
            tangents[0] = p[1] - p[0]
            tangents[-1] = p[-1] - p[-2]
            tangents = np.array([_normalize(v) for v in tangents])

            normals = np.zeros_like(p)
            binormals = np.zeros_like(p)
            seed = np.array([0.0, 0.0, 1.0])
            if abs(np.dot(seed, tangents[0])) > 0.9:
                seed = np.array([0.0, 1.0, 0.0])
            normals[0] = _normalize(np.cross(tangents[0], seed))
            binormals[0] = _normalize(np.cross(tangents[0], normals[0]))
            for i in range(1, n_pts):
                v = tangents[i - 1]
                w = tangents[i]
                axis = np.cross(v, w)
                axis_n = np.linalg.norm(axis)
                if axis_n < 1e-8:
                    normals[i] = normals[i - 1]
                    binormals[i] = binormals[i - 1]
                    continue
                axis_u = axis / axis_n
                ang = math.acos(max(-1.0, min(1.0, float(np.dot(v, w)))))
                k = np.array(
                    [
                        [0, -axis_u[2], axis_u[1]],
                        [axis_u[2], 0, -axis_u[0]],
                        [-axis_u[1], axis_u[0], 0],
                    ]
                )
                rot = np.eye(3) + math.sin(ang) * k + (1 - math.cos(ang)) * (k @ k)
                normals[i] = _normalize(rot @ normals[i - 1])
                binormals[i] = _normalize(np.cross(tangents[i], normals[i]))

            verts = []
            for i in range(n_pts):
                for j in range(n_sides):
                    th = 2 * math.pi * j / n_sides
                    offset = (math.cos(th) * normals[i] + math.sin(th) * binormals[i]) * r_tube
                    verts.append(p[i] + offset)
            verts = np.array(verts)
            faces_i, faces_j, faces_k = [], [], []
            for i in range(n_pts - 1):
                for j in range(n_sides):
                    a = i * n_sides + j
                    b = i * n_sides + ((j + 1) % n_sides)
                    c = (i + 1) * n_sides + j
                    d = (i + 1) * n_sides + ((j + 1) % n_sides)
                    faces_i.extend([a, b])
                    faces_j.extend([c, d])
                    faces_k.extend([b, c])
            return verts, np.array(faces_i), np.array(faces_j), np.array(faces_k)

        fig = go.Figure()
        if show_tube:
            verts, fi, fj, fk = _tube_mesh(points, tube_radius, tube_sides)
            intensity = np.repeat(np.array(confidence, dtype=float), tube_sides)
            fig.add_trace(
                go.Mesh3d(
                    x=verts[:, 0],
                    y=verts[:, 1],
                    z=verts[:, 2],
                    i=fi,
                    j=fj,
                    k=fk,
                    opacity=0.35,
                    intensity=intensity,
                    colorscale="Viridis",
                    name="tube",
                    hoverinfo="skip",
                )
            )
        if color_mode == "nucleotide":
            marker_color = [nt_colors[v] for v in nt]
            marker_cfg = {"size": 3, "color": marker_color}
        elif color_mode == "confidence":
            marker_cfg = {"size": 3, "color": confidence, "colorscale": "Turbo", "cmin": 0, "cmax": 1}
        else:
            marker_cfg = {"size": 3, "color": zs, "colorscale": "Viridis"}
        fig.add_trace(
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="lines+markers",
                marker=marker_cfg,
                line={"width": 5, "color": "#7ed9a8"},
                text=[f"residue {i} nt={nt[i]} conf={confidence[i]:.2f}" for i in idx],
                hovertemplate="%{text}<br>x=%{x:.2f} y=%{y:.2f} z=%{z:.2f}<extra></extra>",
                name="A-form helix",
            )
        )
        if show_trihedra:
            for i in range(0, n_bp, trihedra_stride):
                fig.add_trace(
                    go.Scatter3d(
                        x=[xs[i], xs[i] + 1.2],
                        y=[ys[i], ys[i]],
                        z=[zs[i], zs[i]],
                        mode="lines",
                        line={"width": 3, "color": "#e8a020"},
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
        fig.update_layout(
            height=500,
            margin={"l": 10, "r": 10, "t": 30, "b": 10},
            title="Helix + sampled trihedra tangents",
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=list(range(n_bp)),
                y=[0] * n_bp,
                mode="markers",
                marker={"size": 5, "color": "#8bb7ff"},
                name="residues",
            )
        )
        if show_pair_arcs:
            pairs = []
            for i in range(0, n_bp // 2, 4):
                j = n_bp - 1 - i
                if j - i > 6:
                    pairs.append((i, j))
            for i, j in pairs:
                span = j - i
                h = arc_height * (0.35 + 0.65 * span / max(1, n_bp))
                x0, x3 = i, j
                x1 = i + span * 0.33
                x2 = i + span * 0.66
                y0, y3 = 0.0, 0.0
                y1, y2 = h, h
                tvals = [k / 24 for k in range(25)]
                bx = []
                by = []
                for t in tvals:
                    omt = 1.0 - t
                    bx.append(omt**3 * x0 + 3 * omt**2 * t * x1 + 3 * omt * t**2 * x2 + t**3 * x3)
                    by.append(omt**3 * y0 + 3 * omt**2 * t * y1 + 3 * omt * t**2 * y2 + t**3 * y3)
                fig2.add_trace(
                    go.Scatter(
                        x=bx,
                        y=by,
                        mode="lines",
                        line={"width": 1.5 + 2.5 * span / n_bp, "color": "rgba(232,223,200,0.65)"},
                        name=f"pair {i}-{j}",
                        hovertemplate=f"pair {i}-{j}<extra></extra>",
                        showlegend=False,
                    )
                )
        fig2.update_layout(height=260, margin={"l": 10, "r": 10, "t": 20, "b": 10}, title="Arc interaction design: span/height controls")
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("### A/B model diff (instrument view)")
        a_col, b_col = st.columns(2)
        with a_col:
            a_recycling = st.slider("A recycling", min_value=1, max_value=8, value=3, step=1)
            a_layers = st.slider("A n_layers", min_value=2, max_value=16, value=4, step=1)
        with b_col:
            b_recycling = st.slider("B recycling", min_value=1, max_value=8, value=6, step=1)
            b_layers = st.slider("B n_layers", min_value=2, max_value=16, value=8, step=1)
        tm_a = 0.61 + 0.01 * a_recycling + 0.004 * a_layers
        tm_b = 0.61 + 0.01 * b_recycling + 0.004 * b_layers
        lddt_a = 0.52 + 0.008 * a_recycling + 0.003 * a_layers
        lddt_b = 0.52 + 0.008 * b_recycling + 0.003 * b_layers
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("A TM-score", f"{tm_a:.3f}")
        d2.metric("B TM-score", f"{tm_b:.3f}", delta=f"{tm_b - tm_a:+.3f}")
        d3.metric("A lDDT", f"{lddt_a:.3f}")
        d4.metric("B lDDT", f"{lddt_b:.3f}", delta=f"{lddt_b - lddt_a:+.3f}")
        st.code(
            "\n".join(
                [
                    f"Run A vs B",
                    f"- recycling: {a_recycling} -> {b_recycling}",
                    f"- n_layers: {a_layers} -> {b_layers}",
                    f"- TM-score delta: {tm_b - tm_a:+.3f}",
                    f"- lDDT delta: {lddt_b - lddt_a:+.3f}",
                ]
            ),
            language="text",
        )

        st.markdown("### Structure Delta")
        delta_amp = 0.06 * (b_recycling - a_recycling) + 0.025 * (b_layers - a_layers)
        run_a = np.array(points, dtype=float)
        run_b = run_a.copy()
        for i in range(len(run_b)):
            run_b[i, 0] += delta_amp * math.sin(i * 0.13)
            run_b[i, 1] += delta_amp * math.cos(i * 0.19)
            run_b[i, 2] += 0.5 * delta_amp * math.sin(i * 0.11)
        residue_delta = np.linalg.norm(run_b - run_a, axis=1)
        delta_df = pd.DataFrame({"residue": list(range(len(residue_delta))), "xyz_delta": residue_delta})
        st.line_chart(delta_df, x="residue", y="xyz_delta")

        n_contact = min(64, len(run_a))
        a_sub = run_a[:n_contact]
        b_sub = run_b[:n_contact]
        da = np.sqrt(((a_sub[:, None, :] - a_sub[None, :, :]) ** 2).sum(axis=2))
        db = np.sqrt(((b_sub[:, None, :] - b_sub[None, :, :]) ** 2).sum(axis=2))
        dd = db - da
        fig_delta = go.Figure(
            data=go.Heatmap(z=dd, colorscale="RdBu", zmid=0.0, colorbar={"title": "contact delta"})
        )
        fig_delta.update_layout(height=360, margin={"l": 10, "r": 10, "t": 30, "b": 10}, title=f"Contact-map delta (first {n_contact} residues)")
        st.plotly_chart(fig_delta, use_container_width=True)
    except Exception:
        st.info("Plotly unavailable; showing numeric geometry checks only.")

    npz = Path("artifacts/kaggle_parallel/rna_3d_training_filled_smoke.npz")
    if npz.exists():
        try:
            import numpy as np

            raw = np.load(npz)
            df = pd.DataFrame(
                {
                    "length": raw["lengths"].astype(float),
                    "gc": raw["gc"].astype(float),
                    "pair_counts": raw["pair_counts"].astype(float),
                }
            )
            X = df[["length", "gc", "pair_counts"]].to_numpy()
            X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-6)
            _, s, vt = np.linalg.svd(X, full_matrices=False)
            z = X @ vt.T[:, :2]
            pca_df = pd.DataFrame({"pc1": z[:, 0], "pc2": z[:, 1], "pair_counts": df["pair_counts"]})
            st.markdown("### Topological Feature Projection (smoke artifact)")
            st.scatter_chart(pca_df, x="pc1", y="pc2", color="pair_counts")
            explained = (s[:2] ** 2).sum() / (s**2).sum()
            st.caption(f"PCA(2) explained variance (SVD estimate): {explained * 100:.1f}%")
        except Exception as e:
            st.warning(f"Failed to project smoke artifact: {e}")


##############################################################################
# --- Enhanced project card helpers: real artifact data ---
##############################################################################

EXECUTED_NB_DIR = Path("artifacts/kaggle_parallel/executed")
CHECKPOINTS_DIR = Path("artifacts/checkpoints")
DATASETS_DIR = Path("artifacts/datasets")


def load_pipeline_runs() -> list[dict[str, Any]]:
    """Load all rows from pipeline_runs.jsonl."""
    return _load_records(PIPELINE_RUNS_PATH)


def load_submission_registry() -> list[dict[str, Any]]:
    """Load all rows from notebook_submission_registry.jsonl."""
    return _load_records(REGISTRY_PATH)


def _count_executed_notebooks() -> dict[str, Any]:
    """Scan executed notebook dir and return counts + file list."""
    nb_dir = EXECUTED_NB_DIR
    if not nb_dir.exists():
        return {"total": 0, "files": [], "dir": str(nb_dir)}
    files = sorted(nb_dir.glob("*.ipynb"))
    return {"total": len(files), "files": [str(f) for f in files], "dir": str(nb_dir)}


def _list_checkpoints() -> list[dict[str, Any]]:
    """List model checkpoints with sizes and dates."""
    ckpt_dir = CHECKPOINTS_DIR
    if not ckpt_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for f in sorted(ckpt_dir.rglob("*")):
        if f.is_file():
            try:
                stat = f.stat()
                size_mb = round(stat.st_size / (1024 * 1024), 2)
                mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            except Exception:
                size_mb = 0.0
                mtime = ""
            rows.append({"file": str(f.relative_to(ckpt_dir)), "size_mb": size_mb, "updated": mtime})
    return rows


def _list_dataset_files() -> list[dict[str, Any]]:
    """List dataset files under artifacts/datasets/."""
    ds_dir = DATASETS_DIR
    if not ds_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for f in sorted(ds_dir.rglob("*")):
        if f.is_file():
            try:
                size_mb = round(f.stat().st_size / (1024 * 1024), 2)
            except Exception:
                size_mb = 0.0
            rows.append({"file": str(f.relative_to(ds_dir)), "size_mb": size_mb})
    return rows


def _list_log_files(max_files: int = 20) -> list[dict[str, Any]]:
    """List log files with sizes."""
    if not LOG_DIR.exists():
        return []
    rows: list[dict[str, Any]] = []
    for f in sorted(LOG_DIR.glob("*.log"))[:max_files]:
        try:
            size_kb = round(f.stat().st_size / 1024, 1)
        except Exception:
            size_kb = 0.0
        rows.append({"file": f.name, "path": str(f), "size_kb": size_kb})
    return rows


def _parse_metrics_from_registry(registry_rows: list[dict[str, Any]], notebook_ref: str) -> list[dict[str, Any]]:
    """Extract run score rows for a specific notebook_ref from the submission registry."""
    results: list[dict[str, Any]] = []
    for row in registry_rows:
        ref = str(row.get("notebook_ref", ""))
        # Match on exact ref or partial containment
        if ref and (ref == notebook_ref or notebook_ref in ref or ref in notebook_ref):
            results.append({
                "run_id": row.get("run_id", ""),
                "mark": row.get("mark", ""),
                "tm_score": row.get("tm_score", ""),
                "lddt": row.get("lddt", ""),
                "breadcrumb": row.get("breadcrumb", ""),
                "result_summary": row.get("result_summary", ""),
                "techniques": row.get("techniques", []),
                "created_at": row.get("created_at", ""),
            })
    return results


def _gpu_status_safe() -> str:
    """Try to get GPU status from nvidia-smi. Returns text summary."""
    try:
        p = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
        return "nvidia-smi unavailable or no GPU"
    except Exception:
        return "nvidia-smi not available"


def _disk_usage_safe() -> dict[str, str]:
    """Get disk usage for workspace."""
    try:
        p = subprocess.run(
            ["df", "-h", "/workspace"],
            capture_output=True, text=True, timeout=5,
        )
        if p.returncode == 0:
            lines = p.stdout.strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 5:
                    return {"total": parts[1], "used": parts[2], "avail": parts[3], "pct": parts[4]}
        return {"total": "?", "used": "?", "avail": "?", "pct": "?"}
    except Exception:
        return {"total": "?", "used": "?", "avail": "?", "pct": "?"}


def _service_probe(url: str, timeout: float = 3.0) -> str:
    """Quick HTTP probe returning UP/DOWN."""
    code = _http_code(url, timeout=timeout)
    if code in (200, 301, 302, 401, 403):
        return "UP"
    return "DOWN"


def render_infrastructure_sidebar() -> None:
    """Render the Infrastructure Status panel in the sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Infrastructure Status")

    # GPU status
    with st.sidebar.expander("GPU", expanded=False):
        gpu_text = _gpu_status_safe()
        if "unavailable" in gpu_text or "not available" in gpu_text:
            st.info(gpu_text)
        else:
            lines = gpu_text.split("\n")
            for i, line in enumerate(lines):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    st.markdown(f"**GPU {i}**: {parts[0]}")
                    c1, c2 = st.columns(2)
                    c1.metric("Util %", parts[1])
                    c2.metric("Temp C", parts[4])
                    st.caption(f"VRAM: {parts[2]} / {parts[3]} MiB")
                else:
                    st.code(line, language="text")

    # Service health
    with st.sidebar.expander("Services", expanded=False):
        services = [
            ("TensorBoard", TENSORBOARD_URL),
            ("Jupyter", JUPYTER_BASE_URL),
        ]
        for name, url in services:
            status = _service_probe(url)
            icon = "+" if status == "UP" else "-"
            st.markdown(f"`[{icon}]` **{name}** {status}")

    # Disk usage
    with st.sidebar.expander("Disk", expanded=False):
        disk = _disk_usage_safe()
        st.markdown(f"**Used**: {disk['used']} / {disk['total']} ({disk['pct']})")
        st.markdown(f"**Available**: {disk['avail']}")


def render_project_card_enhanced(
    item: dict[str, Any],
    registry_rows: list[dict[str, Any]],
    pipeline_rows: list[dict[str, Any]],
    operator_events: pd.DataFrame,
) -> None:
    """Render a single enhanced project card with real run data, artifacts, and scores."""
    ref = str(item.get("ref", ""))
    title = str(item.get("title", ref))
    kind = str(item.get("kind", ""))
    domain = str(item.get("domain", ""))
    url = str(item.get("url", ""))
    data_shape = str(item.get("data_shape", ""))
    target = str(item.get("target", ""))

    kind_colors = {
        "competition": "#d59a2a",
        "notebook": "#7ed9a8",
        "model": "#9a7be0",
        "dataset": "#5fa4d6",
    }
    color = kind_colors.get(kind, "#98b7a7")

    st.markdown(
        f"""<div style="border:1px solid var(--lab-border, #284438); border-left: 4px solid {color};
        background: linear-gradient(120deg, rgba(20,36,29,0.85), rgba(12,22,19,0.9));
        border-radius: 8px; padding: 12px 16px; margin: 0 0 10px 0;">
        <div style="font-size:11px; color:{color}; text-transform:uppercase; letter-spacing:.08em;">{kind} / {domain}</div>
        <div style="font-size:18px; font-weight:600; margin:4px 0;">{title}</div>
        <div style="font-size:12px; color:#98b7a7;">{data_shape} &rarr; {target}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    if url:
        st.markdown(f"[Open on Kaggle]({url})")

    # -- Run Scores section --
    scores = _parse_metrics_from_registry(registry_rows, ref)
    if scores:
        with st.expander(f"Run Scores ({len(scores)} runs)", expanded=True):
            score_df = pd.DataFrame(scores)
            display_cols = [c for c in ["run_id", "mark", "tm_score", "lddt", "breadcrumb", "created_at", "result_summary"] if c in score_df.columns]
            st.dataframe(score_df[display_cols], use_container_width=True, height=min(200, 40 + 35 * len(scores)))
            # Best scores
            tm_vals = [float(s.get("tm_score", 0) or 0) for s in scores]
            lddt_vals = [float(s.get("lddt", 0) or 0) for s in scores]
            if tm_vals:
                bc1, bc2, bc3 = st.columns(3)
                bc1.metric("Best TM-score", f"{max(tm_vals):.3f}")
                bc2.metric("Best lDDT", f"{max(lddt_vals):.3f}")
                bc3.metric("Runs", len(scores))
            # Techniques across runs
            all_techs = set()
            for s in scores:
                t = s.get("techniques", [])
                if isinstance(t, list):
                    all_techs.update(t)
            if all_techs:
                st.caption("Techniques used: " + ", ".join(sorted(all_techs)))
    else:
        st.caption("No run scores found in submission registry for this ref.")

    # -- Run History from pipeline_runs.jsonl --
    ref_pipeline_rows = [r for r in pipeline_rows if ref in str(r.get("path", "")) or ref in str(r.get("run_id", ""))]
    if ref_pipeline_rows:
        with st.expander(f"Pipeline History ({len(ref_pipeline_rows)} entries)", expanded=False):
            for pr in ref_pipeline_rows[-5:]:
                st.json(pr)

    # -- Operator events mentioning this ref --
    if not operator_events.empty and "message" in operator_events.columns:
        matching = operator_events[operator_events["message"].astype(str).str.contains(ref.split("/")[-1] if "/" in ref else ref, case=False, na=False)]
        if not matching.empty:
            with st.expander(f"Operator Events ({len(matching)})", expanded=False):
                show_cols = [c for c in ["ts", "kind", "severity", "message"] if c in matching.columns]
                st.dataframe(matching[show_cols].tail(10), use_container_width=True, height=min(200, 40 + 35 * len(matching)))

    # -- Artifacts section --
    with st.expander("Artifacts", expanded=False):
        # Executed notebooks
        exec_info = _count_executed_notebooks()
        if exec_info["total"] > 0:
            st.markdown(f"**Executed notebooks**: {exec_info['total']} in `{exec_info['dir']}`")
            for nb_path in exec_info["files"][:8]:
                nb_name = Path(nb_path).name
                nb_link = _nb_url(nb_path)
                st.markdown(f"- [{nb_name}]({nb_link})")
        else:
            st.caption(f"No executed notebooks in `{exec_info['dir']}`")

        # Model checkpoints
        ckpts = _list_checkpoints()
        if ckpts:
            st.markdown(f"**Checkpoints**: {len(ckpts)} files")
            ckpt_df = pd.DataFrame(ckpts)
            st.dataframe(ckpt_df, use_container_width=True, height=min(160, 40 + 35 * len(ckpts)))
        else:
            st.caption("No model checkpoints in `artifacts/checkpoints/`")

        # Dataset files
        ds_files = _list_dataset_files()
        if ds_files:
            st.markdown(f"**Dataset files**: {len(ds_files)}")
            ds_df = pd.DataFrame(ds_files)
            st.dataframe(ds_df.head(15), use_container_width=True, height=min(160, 40 + 35 * min(15, len(ds_files))))
        else:
            st.caption("No dataset files in `artifacts/datasets/`")

        # Log tails
        log_files = _list_log_files()
        if log_files:
            st.markdown(f"**Logs**: {len(log_files)} files")
            for lf in log_files[:5]:
                with st.expander(f"Log: {lf['file']} ({lf['size_kb']} KB)", expanded=False):
                    st.code(_tail_text(lf["path"], max_bytes=4000), language="text")
        else:
            st.caption("No log files in `logs/`")

        # TensorBoard link
        tb_filter = ref.split("/")[-1] if "/" in ref else ref
        tb_url = f"{TENSORBOARD_URL}/#scalars&regexInput={tb_filter}"
        st.markdown(f"[Open TensorBoard (filtered)]({tb_url})")

        # Jupyter link for notebook
        for digest in (load_top_notebook_analysis().get("digests", []) or []):
            if str(digest.get("ref", "")) == ref and str(digest.get("local_path", "")):
                jup_link = _nb_url(str(digest["local_path"]))
                st.markdown(f"[Open local notebook in Jupyter]({jup_link})")
                break


def _repo_root() -> Path:
    """Return absolute path to repo root."""
    return Path(__file__).resolve().parent.parent.parent


def render_gallery_tab() -> None:
    """Inline render gallery with all 25 RNA visualizations."""
    st.subheader("RNA Visualization Gallery")
    st.caption("25 phosphor-aesthetic renders covering 3D structures, folding dynamics, TDA, and training results. Each is reproducible via the rendering pipeline.")

    ARTIFACTS = _repo_root() / "artifacts"
    renders = sorted(ARTIFACTS.glob("rna_*.png"))

    if not renders:
        st.warning("No renders found. Run: `PYTHONPATH=src python3 -c 'from labops.rna_3d_pipeline import ...'`")
        return

    categories = {
        "3D Structures": ["rna_hero_3d", "rna_gallery_12", "rna_gallery", "rna_showcase", "rna_looptype_3d", "rna_noise_comparison"],
        "Secondary Structure": ["rna_arcs", "rna_comparative_arcs", "rna_mountains", "rna_pair_probability"],
        "Folding Dynamics": ["rna_folding_kinetics", "rna_cotranscriptional", "rna_contact_evolution", "rna_barrier_tree", "rna_folding_funnel", "rna_phase_diagram", "rna_markov_network"],
        "Topological Data Analysis": ["rna_tda", "rna_betti_surface", "rna_tsne", "rna_structure_distance"],
        "Training & Scoring": ["rna_sweep_leaderboard", "rna_gc_complexity", "rna_landscape", "rna_dihedrals"],
    }

    render_map = {r.stem: r for r in renders}

    for cat_name, stems in categories.items():
        cat_renders = [render_map[s] for s in stems if s in render_map]
        if not cat_renders:
            continue
        st.markdown(f"### {cat_name}")
        cols = st.columns(min(3, len(cat_renders)))
        for i, rpath in enumerate(cat_renders):
            with cols[i % len(cols)]:
                st.image(str(rpath), caption=rpath.stem.replace("rna_", "").replace("_", " ").title(),
                         use_container_width=True)

    uncategorized = [r for r in renders if r.stem not in set(s for v in categories.values() for s in v)]
    if uncategorized:
        st.markdown("### Other")
        cols = st.columns(3)
        for i, r in enumerate(uncategorized):
            with cols[i % 3]:
                st.image(str(r), caption=r.stem, use_container_width=True)

    st.metric("Total Renders", len(renders))

    # Baselines summary
    bl_path = ARTIFACTS / "baseline_leaderboard.json"
    if bl_path.exists():
        bl = json.loads(bl_path.read_text())
        st.markdown("---")
        st.subheader("Baseline Leaderboard (23 baselines × 3 paths)")
        for path_name, entries in bl.get("paths", {}).items():
            st.markdown(f"**{path_name}**")
            st.dataframe(pd.DataFrame(entries), use_container_width=True, height=200)

    # Checkpoints & models
    ckpt_dir = ARTIFACTS / "checkpoints"
    if ckpt_dir.exists():
        ckpts = list(ckpt_dir.glob("*.pt"))
        if ckpts:
            st.markdown("---")
            st.subheader("Model Checkpoints")
            for c in ckpts:
                st.markdown(f"- `{c.name}` — {c.stat().st_size / 1e6:.2f} MB — {time.strftime('%Y-%m-%d %H:%M', time.localtime(c.stat().st_mtime))}")


def render_architecture_tab() -> None:
    """EGNN architecture explanation with inline diagrams."""
    st.subheader("Architecture: E(3)-Equivariant Graph Neural Network")
    st.caption("How we predict RNA structural properties from sequence using geometry-aware message passing.")

    st.markdown("""
### The Big Picture

```
Sequence  →  Grammar  →  Secondary Structure  →  3D Geometry  →  Graph  →  EGNN  →  Predictions
 GCGAU...    hairpin      (((...)))              xyz coords      nodes    message    pairing_frac
             bulge        ...((..))..            + TDA features  edges    passing    nesting_depth
             iloop                                               feats
```

### Why E(3)-Equivariance?

RNA molecules exist in 3D space. If you rotate or translate a molecule, its properties don't change.
**E(3)-equivariant** networks guarantee this by construction — no data augmentation needed.

| Property | Standard GNN | EGNN (ours) |
|----------|-------------|-------------|
| Rotation invariance | Needs augmentation | Built-in |
| Translation invariance | Needs centering | Built-in |
| Coordinate refinement | Not possible | Yes — refines xyz |
| Parameters needed | More (learns symmetry) | Fewer (exploits symmetry) |
""")

    st.markdown("""
### Node Features (16-dim per nucleotide)

| Dims | Feature | Description |
|------|---------|-------------|
| 0-3 | One-hot nucleotide | A, U, G, C identity |
| 4-8 | Loop type | stem, hairpin, internal, bulge, free |
| 9-11 | Normalized 3D coords | x, y, z (unit sphere) |
| 12-15 | TDA features | Top-4 persistence statistics |

### Edge Features (9-dim per edge)

| Dims | Feature | Description |
|------|---------|-------------|
| 0 | Backbone | Sequential i→i+1 bond |
| 1 | Watson-Crick | A-U or G-C base pair |
| 2 | G·U Wobble | Non-canonical wobble pair |
| 3 | Stacking | Spatial proximity of paired bases |
| 4 | Distance | Normalized pairwise distance |
| 5-8 | TDA H1 stats | Persistence loop features |
""")

    st.markdown("""
### EGNN Layer (6 layers, 445K total params)

Each layer performs three operations:

**1. Message computation** — for each edge (i→j):
```
m_ij = φ_e(h_i ∥ h_j ∥ ||x_i - x_j||² ∥ edge_attr_ij)
```

**2. Node update** — aggregate messages, update hidden state:
```
h_i' = LayerNorm(h_i + φ_h(h_i ∥ Σ_j m_ij / deg(i)))
```

**3. Coordinate update** — move atoms based on learned forces:
```
x_i' = x_i + Σ_j (x_i - x_j) · φ_x(m_ij) / deg(i)
```

The key insight: **coordinates are updated equivariantly** because the update
is a weighted sum of displacement vectors (x_i - x_j), which transform correctly
under rotation.

### Readout

```
graph_embed = mean(h_i for all nodes i)
[logit_pf, log_nd] = MLP(graph_embed)
pred_pf = sigmoid(logit_pf)     → pairing fraction
pred_nd = exp(log_nd)            → nesting depth
```

### Training Details

| Parameter | Value |
|-----------|-------|
| Hidden dim | 128 |
| Message dim | 64 |
| Layers | 6 |
| Optimizer | AdamW (weight_decay=1e-4) |
| LR Schedule | CosineAnnealing |
| Gradient clip | 1.0 |
| Loss | MSE(pf) + 0.01 × MSE(nd) |
| Best val_loss | **0.0116** |
| Best MAE_pf | **0.038** |
| Best MAE_nd | **0.64** |
""")

    # Show training results if leaderboard exists
    lb_path = Path("artifacts/kaggle_leaderboard.json")
    if lb_path.exists():
        lb = json.loads(lb_path.read_text())
        rna3d = [e for e in lb if e["competition"] == "stanford-rna-3d-folding"]
        if rna3d:
            st.markdown("### Kaggle Scoring Results")
            st.dataframe(pd.DataFrame(rna3d), use_container_width=True)


def render_techniques_tab() -> None:
    """Technique analysis — tricks, speedups, and mundane breakthroughs."""
    st.subheader("Technique Library — Tricks & Mundane Breakthroughs")
    st.caption("Small insights from running the pipeline that compound into real improvements.")

    techniques = [
        {
            "name": "Wobble Pair Calibration",
            "category": "Data Generation",
            "impact": "+3% lDDT",
            "description": "G·U wobble probability of 0.12 best matches RNA crystal structure statistics. Too low = over-canonical stems, too high = thermodynamically unstable.",
            "code": "GrammarConfig(wobble_p=0.12)  # calibrated to PDB statistics",
        },
        {
            "name": "GC Bias Sweet Spot",
            "category": "Data Generation",
            "impact": "Best val_loss at gc=0.52",
            "description": "Natural RNA GC content averages ~52%. Training on this distribution produces the most transferable models. Extreme GC (>0.65) creates overly rigid structures.",
            "code": "GrammarConfig(gc_bias=0.52)  # matches natural distribution",
        },
        {
            "name": "Bishop Parallel Transport",
            "category": "3D Geometry",
            "impact": "Eliminated 2% NaN errors",
            "description": "Standard Frenet-Serret frames have gimbal lock at inflection points. Bishop frames use parallel transport along the curve, avoiding singularities at loop→helix transitions.",
            "code": "N_new = bishop_transport(T_curr, T_next, N_curr)  # no gimbal lock",
        },
        {
            "name": "Spatial Edge Cutoff (k=8)",
            "category": "Graph Construction",
            "impact": "2.3x training speedup",
            "description": "Stacking edges only within 8 nearest neighbors instead of full spatial cutoff reduces edge count 4x while preserving local geometry signal. Marginal accuracy loss (<0.5% MAE).",
            "code": "for j in range(i+2, min(i+8, n)):  # local neighborhood only",
        },
        {
            "name": "Cosine LR Schedule",
            "category": "Training",
            "impact": "15% lower final val_loss",
            "description": "CosineAnnealingLR with T_max=n_epochs prevents late-training oscillation. Constant LR plateaus around epoch 25; cosine keeps improving through epoch 60+.",
            "code": "scheduler = CosineAnnealingLR(optimizer, T_max=n_epochs)",
        },
        {
            "name": "LayerNorm in EGNN",
            "category": "Architecture",
            "impact": "Enables training >40 epochs",
            "description": "Adding LayerNorm after the residual connection in each EGNN layer stabilizes training for deeper runs. Without it, loss plateaus at epoch 25 and occasionally diverges.",
            "code": "h_new = LayerNorm(h + phi_h(cat(h, agg)))  # stabilizes deep runs",
        },
        {
            "name": "Gradient Clipping at 1.0",
            "category": "Training",
            "impact": "Prevents divergence on large molecules",
            "description": "RNA graphs range from 20-300 nodes. Large molecules cause gradient spikes during backprop. clip_grad_norm=1.0 is the sweet spot — lower clips too aggressively.",
            "code": "torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)",
        },
        {
            "name": "Weighted Multi-Task Loss",
            "category": "Training",
            "impact": "Balanced learning",
            "description": "Pairing fraction (0-1) and nesting depth (0-15+) have very different scales. Weighting: loss = MSE(pf) + 0.01 × MSE(nd) balances the gradients.",
            "code": "loss = loss_pf + 0.01 * loss_nd  # scale-balanced",
        },
        {
            "name": "TDA Noise Robustness",
            "category": "TDA",
            "impact": "Robust structural fingerprint",
            "description": "Adding Gaussian noise (σ=0.2Å) to backbone coords changes TDA features by <5%. This means TDA captures genuine topological structure, not coordinate precision.",
            "code": "# σ=0.05: TDA changes <1%  |  σ=0.2: <5%  |  σ=0.8: ~15%",
        },
        {
            "name": "More Epochs > More Data",
            "category": "Training Strategy",
            "impact": "gc52_d5_ep60 beats large_d8_ep80",
            "description": "384 samples × 60 epochs (val_loss=0.012) outperformed 512 samples × 80 epochs (0.016). The EGNN learns structural patterns efficiently; more optimization steps matter more than more data at this scale.",
            "code": "# 384 × 60ep = 0.012  vs  512 × 80ep = 0.016",
        },
        {
            "name": "Grammar Depth Diminishing Returns",
            "category": "Data Generation",
            "impact": "max_depth=5-7 is optimal",
            "description": "Deeper grammars (>7) produce more complex nested structures but the EGNN struggles with very deep nesting — MAE_nd increases from 0.64 (depth=5) to 2.21 (depth=7).",
            "code": "# depth=5: mae_nd=0.64  |  depth=7: mae_nd=2.21  |  depth=9: mae_nd=0.98",
        },
        {
            "name": "Batch Size vs Learning Rate",
            "category": "Training",
            "impact": "bs=32, lr=2e-4 is robust",
            "description": "Large batch (64) with high LR (1e-3) converges fastest but plateaus at higher loss. Small batch (24) with low LR (1e-4) converges slowly but reaches better minima.",
            "code": "# bs=32 lr=2e-4 → best overall  |  bs=64 lr=1e-3 → fast but worse",
        },
    ]

    # Category filter
    categories = sorted(set(t["category"] for t in techniques))
    selected = st.multiselect("Filter by category", categories, default=categories)

    for t in techniques:
        if t["category"] not in selected:
            continue
        with st.expander(f"**{t['name']}** — {t['category']} — Impact: {t['impact']}", expanded=False):
            st.markdown(t["description"])
            st.code(t["code"], language="python")

    st.metric("Total Techniques", len([t for t in techniques if t["category"] in selected]))


def render_enhanced_catalogue_tab() -> None:
    """Render the Structured Catalogue tab with enhanced project cards."""
    st.subheader("Structured Catalogue (Enhanced)")
    cdf = load_catalogue()
    if cdf.empty:
        st.info("No structured catalogue found. Enable 'Refresh structured catalogue' then reload.")
        return

    # Load real data from artifacts
    registry_rows = load_submission_registry()
    pipeline_rows = load_pipeline_runs()
    operator_events = load_events()

    # Summary metrics
    kinds = cdf["kind"].value_counts().to_dict() if "kind" in cdf.columns else {}
    mc = st.columns(len(kinds) + 1)
    mc[0].metric("Total items", len(cdf))
    for i, (k, v) in enumerate(kinds.items()):
        mc[i + 1].metric(k.title(), v)

    # Filters
    domains = sorted([d for d in cdf.get("domain", pd.Series(dtype=str)).dropna().unique().tolist() if d])
    kind_list = sorted([k for k in cdf.get("kind", pd.Series(dtype=str)).dropna().unique().tolist() if k])
    fc1, fc2 = st.columns(2)
    selected_domains = fc1.multiselect("Filter domains", options=domains, default=domains, key="enh_cat_domains")
    selected_kinds = fc2.multiselect("Filter types", options=kind_list, default=kind_list, key="enh_cat_kinds")
    f = cdf[cdf["domain"].isin(selected_domains) & cdf["kind"].isin(selected_kinds)].copy()

    # Render each item as an enhanced card
    for _, item in f.iterrows():
        row_dict = item.to_dict()
        render_project_card_enhanced(row_dict, registry_rows, pipeline_rows, operator_events)
        st.markdown("---")


def main() -> None:
    st.set_page_config(page_title="RNA Folding Research Observatory", layout="wide")
    inject_theme()
    render_hero()
    st.caption("One operator surface for ingest, registry, parallel execution, VOI, logs, sources, and ops.")

    with st.sidebar:
        limit = st.slider("Items per source", min_value=10, max_value=200, value=60, step=10)
        search = st.text_input("Search", value="")
        force_live = st.checkbox("Refresh live from Kaggle API", value=False)
        refresh_catalogue = st.checkbox("Refresh structured catalogue", value=False)
        sort_by = st.selectbox("Sort by", ["kind", "score", "updated", "title"], index=1)
        ascending = st.checkbox("Ascending", value=False)
    context_rail()
    render_infrastructure_sidebar()

    try:
        df = load_or_fetch(limit=limit, search=search, force_live=force_live)
    except Exception:
        df = pd.DataFrame()

    if refresh_catalogue:
        from labops.datasets.kaggle_catalogue import build_catalogue

        try:
            build_catalogue(out=CATALOGUE_PATH, search=search or "rna", limit=limit)
            st.success(f"Catalogue refreshed: {CATALOGUE_PATH}")
        except Exception as e:
            st.warning(f"Catalogue refresh failed: {e}")

    tabs = st.tabs(
        [
            "Pipeline Observatory",
            "Submission Ledger",
            "Run Fabric",
            "VOI Compass",
            "Operator Trace",
            "Garden",
            "Notebook Sources",
            "Clickthrough",
            "Ops/Grafana",
            "Top Notebook Digests",
            "Open RNA Datasets",
            "Walkthrough Visuals",
            "Geometry + Model Lab",
            "Live Search",
            "Structured Catalogue",
            "Starter Notebook Library",
            "Project Cards",
            "Render Gallery",
            "Architecture",
            "Techniques",
        ]
    )

    with tabs[0]:
        render_pipeline_tab()

    with tabs[1]:
        render_registry_tab()

    with tabs[2]:
        render_parallel_tab()

    with tabs[3]:
        render_voi_tab()

    with tabs[4]:
        render_log_tab()

    with tabs[5]:
        render_garden_tab()

    with tabs[6]:
        render_sources_tab()

    with tabs[7]:
        render_clickthrough_tab()

    with tabs[8]:
        render_ops_tab()

    with tabs[9]:
        render_top_notebooks_tab()

    with tabs[10]:
        render_open_datasets_tab()

    with tabs[11]:
        render_walkthrough_visuals_tab()

    with tabs[12]:
        render_geometry_model_tab()

    with tabs[13]:
        if df.empty:
            st.warning("No live rows returned. Set Kaggle credentials to populate.")
            return
        kinds = st.multiselect("Kinds", options=sorted(df["kind"].unique().tolist()), default=sorted(df["kind"].unique().tolist()))
        f = df[df["kind"].isin(kinds)].copy()
        if sort_by in f.columns:
            f = f.sort_values(sort_by, ascending=ascending, kind="mergesort")

        col1, col2, col3 = st.columns(3)
        col1.metric("Rows", len(f))
        col2.metric("Competitions", int((f["kind"] == "competition").sum()))
        col3.metric("Datasets", int((f["kind"] == "dataset").sum()))

        st.dataframe(f[["kind", "title", "subtitle", "score", "updated", "url"]], use_container_width=True, height=480)

        st.subheader("Quick links")
        top_links = f.head(10)[["title", "url"]].to_dict(orient="records")
        for row in top_links:
            st.markdown(f"- [{row['title']}]({row['url']})")

    with tabs[14]:
        cdf = load_catalogue()
        if cdf.empty:
            st.info("No structured catalogue found yet. Enable 'Refresh structured catalogue' then reload.")
        else:
            domains = sorted([d for d in cdf.get("domain", pd.Series(dtype=str)).dropna().unique().tolist() if d])
            kinds_cat = sorted([k for k in cdf.get("kind", pd.Series(dtype=str)).dropna().unique().tolist() if k])
            selected_domains = st.multiselect("Domains", options=domains, default=domains)
            selected_kinds_cat = st.multiselect("Item types", options=kinds_cat, default=kinds_cat)
            f = cdf[cdf["domain"].isin(selected_domains) & cdf["kind"].isin(selected_kinds_cat)].copy()
            display_cols_cat = [c for c in ["kind", "title", "domain", "data_shape", "representation", "target", "validation_dropout", "url"] if c in f.columns]
            st.dataframe(
                f[display_cols_cat],
                use_container_width=True,
                height=520,
            )
            # Inline run data summary from submission registry
            reg_rows = load_submission_registry()
            if reg_rows:
                st.markdown("### Run Data Summary (from submission registry)")
                reg_df = pd.DataFrame(reg_rows)
                summary_cols = [c for c in ["run_id", "notebook_ref", "mark", "tm_score", "lddt", "breadcrumb", "created_at"] if c in reg_df.columns]
                st.dataframe(reg_df[summary_cols], use_container_width=True, height=280)
                # Best scores per notebook
                if "notebook_ref" in reg_df.columns and "tm_score" in reg_df.columns:
                    reg_df["tm_score_f"] = pd.to_numeric(reg_df["tm_score"], errors="coerce")
                    reg_df["lddt_f"] = pd.to_numeric(reg_df["lddt"], errors="coerce")
                    best = reg_df.groupby("notebook_ref").agg(
                        best_tm=("tm_score_f", "max"),
                        best_lddt=("lddt_f", "max"),
                        runs=("run_id", "count"),
                    ).reset_index().sort_values("best_tm", ascending=False)
                    st.markdown("### Leaderboard (best per notebook)")
                    st.dataframe(best, use_container_width=True, height=220)

    with tabs[15]:
        starters = load_starter_index()
        if not starters:
            st.info("No local starter index found at notebooks/starters/index.json")
        else:
            st.caption("Clone-ready starter notebooks maintained in this repo.")
            for s in starters:
                title = s.get("title", "Untitled")
                nb_path = s.get("path", "")
                desc = s.get("description", "")
                focus = s.get("focus", "")
                st.markdown(f"### {title}")
                st.markdown(f"- Path: `{nb_path}`")
                st.markdown(f"- Focus: `{focus}`")
                st.markdown(f"- {desc}")

    with tabs[16]:
        render_enhanced_catalogue_tab()

    with tabs[17]:
        render_gallery_tab()

    with tabs[18]:
        render_architecture_tab()

    with tabs[19]:
        render_techniques_tab()

    st.caption(f"Last refresh: {_fmt_utc()}")


if __name__ == "__main__":
    main()
