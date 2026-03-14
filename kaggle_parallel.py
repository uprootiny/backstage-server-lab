from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class NotebookJob:
    job_id: str
    notebook: str
    timeout_min: int = 60
    params: dict[str, Any] | None = None
    expected_improvement: float = 0.2
    uncertainty: float = 0.6
    importance: float = 0.9
    tags: list[str] | None = None

    @property
    def voi(self) -> float:
        return float(self.expected_improvement) * float(self.uncertainty) * float(self.importance)


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event: dict[str, Any]) -> None:
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=True) + "\n")

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out


def _build_nbconvert_cmd(job: NotebookJob, output_nb: Path) -> list[str]:
    # Always execute nbconvert via the current Python environment to avoid
    # picking a mismatched system jupyter binary from PATH.
    cmd = [sys.executable, "-m", "nbconvert"]
    cmd.extend(
        [
        "--to",
        "notebook",
        "--execute",
        job.notebook,
        "--output",
        output_nb.name,
        "--output-dir",
        str(output_nb.parent),
        f"--ExecutePreprocessor.timeout={int(job.timeout_min) * 60}",
        ]
    )
    if job.params:
        for k, v in job.params.items():
            cmd.extend(["--ExecutePreprocessor.kernel_name", str(v)]) if k == "kernel_name" else None
    return cmd


def _ensure_nbconvert() -> bool:
    probe = subprocess.run([sys.executable, "-m", "nbconvert", "--version"], capture_output=True, text=True)
    if probe.returncode == 0:
        return True
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "nbconvert", "nbformat", "jupyter"],
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        return False
    probe2 = subprocess.run([sys.executable, "-m", "nbconvert", "--version"], capture_output=True, text=True)
    return probe2.returncode == 0


def _read_any_plan(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        raw = json.loads(text)
    else:
        raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("plan must be a mapping")
    return raw


def load_plan(path: Path) -> tuple[dict[str, Any], list[NotebookJob]]:
    raw = _read_any_plan(path)
    jobs_raw = raw.get("jobs", [])
    if not isinstance(jobs_raw, list):
        raise ValueError("plan 'jobs' must be a list")

    jobs: list[NotebookJob] = []
    for i, j in enumerate(jobs_raw):
        if not isinstance(j, dict):
            continue
        jobs.append(
            NotebookJob(
                job_id=str(j.get("id", f"job-{i+1:03d}")),
                notebook=str(j.get("notebook", "")),
                timeout_min=int(j.get("timeout_min", 60)),
                params=dict(j.get("params", {})) if isinstance(j.get("params", {}), dict) else {},
                expected_improvement=float(j.get("expected_improvement", 0.2)),
                uncertainty=float(j.get("uncertainty", 0.6)),
                importance=float(j.get("importance", 0.9)),
                tags=list(j.get("tags", [])) if isinstance(j.get("tags", []), list) else [],
            )
        )
    return raw, jobs


def _cache_dataset(url: str, cache_dir: Path, retries: int, backoff_sec: float) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / Path(url.split("?")[0]).name
    if target.exists() and target.stat().st_size > 0:
        return {"url": url, "path": str(target), "status": "cached", "bytes": int(target.stat().st_size)}

    for attempt in range(1, retries + 1):
        try:
            with urlopen(url, timeout=60) as r:  # nosec B310
                payload = r.read()
            target.write_bytes(payload)
            return {"url": url, "path": str(target), "status": "downloaded", "bytes": len(payload)}
        except URLError as e:
            if attempt >= retries:
                return {"url": url, "path": str(target), "status": "failed", "error": str(e)}
            time.sleep(backoff_sec * (2 ** (attempt - 1)))
    return {"url": url, "path": str(target), "status": "failed", "error": "unknown"}


def dispatch(
    plan_path: Path,
    concurrency: int,
    ledger_path: Path,
    logs_dir: Path,
    executed_dir: Path,
) -> dict[str, Any]:
    cfg, jobs = load_plan(plan_path)
    if not jobs:
        raise ValueError("no jobs in plan")

    logs_dir.mkdir(parents=True, exist_ok=True)
    executed_dir.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(ledger_path)

    retry_cfg = cfg.get("retries", {}) if isinstance(cfg.get("retries", {}), dict) else {}
    max_attempts = int(retry_cfg.get("max_attempts", 3))
    backoff_sec = float(retry_cfg.get("backoff_sec", 4.0))

    datasets_cfg = cfg.get("datasets", [])
    cache_dir = Path(cfg.get("dataset_cache_dir", "artifacts/datasets/cache"))

    has_nbconvert = _ensure_nbconvert()
    # Run metadata event
    run_id = f"kaggle-parallel-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    ledger.append(
        {
            "ts": _now(),
            "event": "run_start",
            "run_id": run_id,
            "plan": str(plan_path),
            "concurrency": int(concurrency),
            "job_count": len(jobs),
            "profile": cfg.get("profile", "custom"),
            "max_attempts": max_attempts,
            "nbconvert_ready": has_nbconvert,
        }
    )

    if isinstance(datasets_cfg, list):
        for d in datasets_cfg:
            if not isinstance(d, dict):
                continue
            url = str(d.get("url", "")).strip()
            if not url:
                continue
            cache_res = _cache_dataset(url=url, cache_dir=cache_dir, retries=max_attempts, backoff_sec=backoff_sec)
            ledger.append(
                {
                    "ts": _now(),
                    "event": "dataset_cache",
                    "run_id": run_id,
                    **cache_res,
                }
            )

    def run_job(job: NotebookJob) -> dict[str, Any]:
        started = time.time()
        output_nb = executed_dir / f"{job.job_id}.executed.ipynb"
        log_file = logs_dir / f"{job.job_id}.log"

        cmd = _build_nbconvert_cmd(job, output_nb)
        ledger.append(
            {
                "ts": _now(),
                "event": "job_start",
                "run_id": run_id,
                "job_id": job.job_id,
                "notebook": job.notebook,
                "voi": job.voi,
                "cmd": " ".join(shlex.quote(x) for x in cmd),
            }
        )

        if not job.notebook or not Path(job.notebook).exists():
            ended = time.time()
            res = {
                "job_id": job.job_id,
                "status": "missing_notebook",
                "exit_code": 127,
                "seconds": round(ended - started, 2),
                "log": str(log_file),
                "output_notebook": str(output_nb),
                "voi": round(job.voi, 6),
            }
            ledger.append({"ts": _now(), "event": "job_end", "run_id": run_id, **res})
            return res
        if not has_nbconvert:
            ended = time.time()
            res = {
                "job_id": job.job_id,
                "status": "missing_executor",
                "exit_code": 127,
                "seconds": round(ended - started, 2),
                "log": str(log_file),
                "output_notebook": str(output_nb),
                "voi": round(job.voi, 6),
            }
            ledger.append({"ts": _now(), "event": "job_end", "run_id": run_id, **res})
            return res

        attempts: list[dict[str, Any]] = []
        code = 1
        with log_file.open("w", encoding="utf-8") as lf:
            lf.write(f"# job={job.job_id}\n# ts={_now()}\n# cmd={' '.join(shlex.quote(x) for x in cmd)}\n\n")
            for attempt in range(1, max_attempts + 1):
                lf.write(f"\n# attempt={attempt}/{max_attempts} ts={_now()}\n")
                proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)
                code = int(proc.returncode)
                attempts.append({"attempt": attempt, "exit_code": code})
                if code == 0:
                    break
                if attempt < max_attempts:
                    sleep_for = backoff_sec * (2 ** (attempt - 1))
                    lf.write(f"# backoff_sleep={sleep_for}s\n")
                    time.sleep(sleep_for)

        ended = time.time()
        status = "ok" if code == 0 else "failed"
        res = {
            "job_id": job.job_id,
            "status": status,
            "exit_code": code,
            "seconds": round(ended - started, 2),
            "log": str(log_file),
            "output_notebook": str(output_nb),
            "voi": round(job.voi, 6),
            "attempts": attempts,
        }
        ledger.append({"ts": _now(), "event": "job_end", "run_id": run_id, **res})
        return res

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(concurrency))) as ex:
        fut_map = {ex.submit(run_job, j): j.job_id for j in jobs}
        for fut in as_completed(fut_map):
            results.append(fut.result())

    ok = sum(1 for r in results if r.get("status") == "ok")
    failed = len(results) - ok
    out = {
        "run_id": run_id,
        "plan": str(plan_path),
        "concurrency": int(concurrency),
        "jobs": len(results),
        "ok": ok,
        "failed": failed,
    }
    ledger.append({"ts": _now(), "event": "run_end", **out})
    return out


def summarize_ledger(ledger_path: Path) -> dict[str, Any]:
    rows = Ledger(ledger_path).read()
    job_ends = [r for r in rows if r.get("event") == "job_end"]
    run_ends = [r for r in rows if r.get("event") == "run_end"]
    if not job_ends:
        return {"events": len(rows), "job_runs": 0}

    ok = sum(1 for r in job_ends if r.get("status") == "ok")
    failed = sum(1 for r in job_ends if r.get("status") != "ok")
    avg_sec = round(sum(float(r.get("seconds", 0)) for r in job_ends) / len(job_ends), 2)

    by_job: dict[str, dict[str, Any]] = {}
    for r in job_ends:
        by_job[str(r.get("job_id", ""))] = r

    top_voi = sorted(job_ends, key=lambda x: float(x.get("voi", 0)), reverse=True)[:10]

    return {
        "events": len(rows),
        "run_count": len(run_ends),
        "job_runs": len(job_ends),
        "ok": ok,
        "failed": failed,
        "avg_seconds": avg_sec,
        "latest_jobs": sorted(by_job.values(), key=lambda x: x.get("job_id", ""))[:50],
        "top_voi": top_voi,
    }


def suggest_reruns(ledger_path: Path, min_voi: float = 0.12, limit: int = 12) -> list[dict[str, Any]]:
    rows = Ledger(ledger_path).read()
    job_ends = [r for r in rows if r.get("event") == "job_end"]
    candidates = []
    for r in job_ends:
        status = str(r.get("status", ""))
        voi = float(r.get("voi", 0.0))
        if status != "ok" and voi >= min_voi:
            candidates.append(r)
    candidates.sort(key=lambda x: (float(x.get("voi", 0.0)), -float(x.get("seconds", 0.0))), reverse=True)
    return candidates[:limit]


def init_plan(profile: str, out: Path, notebooks_dir: Path) -> Path:
    presets = {"three": 3, "ten": 10, "dozen": 12}
    n = presets.get(profile, 3)
    jobs: list[dict[str, Any]] = []
    for i in range(n):
        nb = notebooks_dir / f"job_{i+1:02d}.ipynb"
        jobs.append(
            {
                "id": f"job-{i+1:02d}",
                "notebook": str(nb),
                "timeout_min": 45,
                "params": {},
                "expected_improvement": 0.15 + (0.01 * (i % 5)),
                "uncertainty": 0.5 + (0.03 * (i % 4)),
                "importance": 0.9,
                "tags": ["kaggle", "rna", profile],
            }
        )

    payload = {
        "profile": profile,
        "created_at": _now(),
        "notes": "Edit notebook paths and timeouts before dispatch.",
        "jobs": jobs,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return out
