"""
GPU Wrangler API - FastAPI backend for ML training control panel.

Serves on port 19842. Provides GPU status, run management, service health
checks, and static file serving for the web UI.

Usage:
    uvicorn api:app --host 0.0.0.0 --port 19842
    # or
    python api.py
"""

import asyncio
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---- Config ----
WORKSPACE = Path("/workspace")
REPO_DIR = WORKSPACE / "backstage-server-lab"
LOGS_DIR = WORKSPACE / "logs" / "rna"
ARTIFACTS_DIR = REPO_DIR / "artifacts"
PIPELINE_RUNS_FILE = ARTIFACTS_DIR / "pipeline_runs.jsonl"
GPU_TRAIN_SCRIPT = REPO_DIR / "src" / "labops" / "gpu_train.py"
STATIC_DIR = Path(__file__).parent
PORT = 8520  # Use 8520 - access via Cloudflare tunnel or direct

# ---- App ----
app = FastAPI(
    title="GPU Wrangler API",
    description="Backend for the ML Training Control Panel",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Models ----
class LaunchParams(BaseModel):
    gc_bias: float = 0.5
    max_depth: int = 6
    wobble_p: float = 0.1
    n_samples: int = 10000
    n_epochs: int = 50
    fp16: bool = True
    grad_ckpt: bool = False
    wandb: bool = True
    autosave: bool = True


# Track running processes
_running_procs: dict[str, subprocess.Popen] = {}


# ---- GPU Status ----
def parse_nvidia_smi() -> dict:
    """Parse nvidia-smi XML output for GPU metrics."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-q", "-x"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {}

        root = ET.fromstring(result.stdout)
        gpu = root.find("gpu")
        if gpu is None:
            return {}

        def text(path: str, default: str = "0") -> str:
            el = gpu.find(path)
            return el.text.strip() if el is not None and el.text else default

        def num(path: str, default: float = 0) -> float:
            t = text(path, str(default))
            # Strip units like "MiB", "W", "%", "C"
            t = t.split()[0] if t else str(default)
            try:
                return float(t)
            except (ValueError, TypeError):
                return default

        vram_used = num("fb_memory_usage/used")
        vram_total = num("fb_memory_usage/total")
        # nvidia-smi reports in MiB, convert to GB
        if vram_used > 100:  # Likely MiB
            vram_used = round(vram_used / 1024, 1)
            vram_total = round(vram_total / 1024, 1)

        return {
            "name": text("product_name", "Unknown GPU"),
            "utilization": int(num("utilization/gpu_util")),
            "vram_used": vram_used,
            "vram_total": vram_total,
            "temperature": int(num("temperature/gpu_temp")),
            "power_draw": int(num("gpu_power_readings/power_draw", 0)
                              or num("power_readings/power_draw", 0)),
            "power_limit": int(num("gpu_power_readings/enforced_power_limit", 450)
                               or num("power_readings/enforced_power_limit", 450)),
            "fan_speed": int(num("fan_speed", 0)),
            "driver": text("driver_version", "???"),
            "cuda": text("cuda_version", "???"),
        }
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"[gpu-status] Error parsing nvidia-smi: {e}")
        return {}


@app.get("/api/gpu-status")
async def gpu_status():
    data = parse_nvidia_smi()
    if not data:
        raise HTTPException(status_code=503, detail="nvidia-smi not available")
    return data


# ---- Runs ----
def load_pipeline_runs() -> list[dict]:
    """Load runs from pipeline_runs.jsonl and TensorBoard event dirs."""
    runs = []

    # Load from JSONL file
    if PIPELINE_RUNS_FILE.exists():
        try:
            with open(PIPELINE_RUNS_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            runs.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"[runs] Error reading {PIPELINE_RUNS_FILE}: {e}")

    # Scan TensorBoard event dirs
    if LOGS_DIR.exists():
        for event_dir in sorted(LOGS_DIR.iterdir()):
            if not event_dir.is_dir():
                continue
            # Check for tfevents files
            has_events = any(f.name.startswith("events.out.tfevents") for f in event_dir.iterdir() if f.is_file())
            if has_events:
                run_id = event_dir.name
                # Skip if already loaded from JSONL
                if any(r.get("id") == run_id for r in runs):
                    continue
                # Get timestamps from event files
                event_files = sorted(event_dir.glob("events.out.tfevents.*"))
                if event_files:
                    mtime = event_files[-1].stat().st_mtime
                    started = datetime.fromtimestamp(event_files[0].stat().st_mtime)
                    runs.append({
                        "id": run_id,
                        "name": run_id,
                        "status": "complete",
                        "epochs": "?/?",
                        "best_loss": 0.0,
                        "duration": "unknown",
                        "started": started.strftime("%Y-%m-%d %H:%M"),
                    })

    # Mark currently running processes
    for run_id, proc in list(_running_procs.items()):
        if proc.poll() is None:  # Still running
            for r in runs:
                if r.get("id") == run_id:
                    r["status"] = "running"
                    break
        else:
            # Process finished
            retcode = proc.returncode
            for r in runs:
                if r.get("id") == run_id:
                    r["status"] = "complete" if retcode == 0 else "failed"
                    break
            del _running_procs[run_id]

    return runs


@app.get("/api/runs")
async def get_runs():
    runs = load_pipeline_runs()
    return {"runs": runs}


# ---- Services ----
async def check_port(port: int, timeout: float = 1.0) -> bool:
    """Check if a port is accepting connections."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (ConnectionRefusedError, asyncio.TimeoutError, OSError):
        return False


SERVICE_DEFS = [
    {"name": "TensorBoard", "port": 6006, "url": "/tensorboard/"},
    {"name": "Jupyter",     "port": 8080, "url": "/jupyter/"},
    {"name": "Streamlit",   "port": 1111, "url": "/streamlit/"},
    {"name": "API Server",  "port": PORT, "url": "/"},
    {"name": "SSH",         "port": 22,   "url": None},
    {"name": "VS Code",     "port": 8443, "url": None},
]


@app.get("/api/services")
async def get_services():
    checks = await asyncio.gather(
        *[check_port(s["port"]) for s in SERVICE_DEFS]
    )
    services = []
    for svc, is_up in zip(SERVICE_DEFS, checks):
        services.append({
            **svc,
            "status": "up" if is_up else "down",
        })
    return {"services": services}


# ---- Launch Run ----
@app.post("/api/launch-run")
async def launch_run(params: LaunchParams):
    run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Build command
    cmd = ["python", str(GPU_TRAIN_SCRIPT)]
    cmd += ["--gc-bias", str(params.gc_bias)]
    cmd += ["--max-depth", str(params.max_depth)]
    cmd += ["--wobble-p", str(params.wobble_p)]
    cmd += ["--n-samples", str(params.n_samples)]
    cmd += ["--n-epochs", str(params.n_epochs)]
    if params.fp16:
        cmd += ["--fp16"]
    if params.grad_ckpt:
        cmd += ["--grad-checkpoint"]
    if params.wandb:
        cmd += ["--wandb"]
    cmd += ["--run-id", run_id]

    # Log the run
    log_entry = {
        "id": run_id,
        "name": run_id,
        "status": "running",
        "epochs": f"0/{params.n_epochs}",
        "best_loss": float("inf"),
        "duration": "0h 00m",
        "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "params": params.model_dump(),
    }

    # Append to JSONL
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(PIPELINE_RUNS_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Launch subprocess
    log_dir = LOGS_DIR / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = open(log_dir / "stdout.log", "w")
    stderr_log = open(log_dir / "stderr.log", "w")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=stdout_log,
            stderr=stderr_log,
            cwd=str(WORKSPACE / "backstage-server-lab"),
            env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"},
        )
        _running_procs[run_id] = proc
        return {"run_id": run_id, "pid": proc.pid, "status": "launched"}
    except FileNotFoundError:
        return JSONResponse(
            status_code=422,
            content={"detail": f"Training script not found: {GPU_TRAIN_SCRIPT}"},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to launch: {str(e)}"},
        )


# ---- Stop All ----
@app.post("/api/stop-all")
async def stop_all():
    stopped = []
    for run_id, proc in list(_running_procs.items()):
        if proc.poll() is None:
            proc.terminate()
            stopped.append(run_id)
    # Give processes a moment, then kill stragglers
    await asyncio.sleep(2)
    for run_id, proc in list(_running_procs.items()):
        if proc.poll() is None:
            proc.kill()
    _running_procs.clear()
    return {"stopped": stopped}


# ---- Notebooks ----
@app.get("/api/notebooks")
async def get_notebooks():
    notebooks_dir = WORKSPACE / "backstage-server-lab" / "notebooks"
    notebooks = []
    if notebooks_dir.exists():
        for nb_file in sorted(notebooks_dir.glob("*.ipynb")):
            try:
                with open(nb_file) as f:
                    data = json.load(f)
                cells = len(data.get("cells", []))
                mtime = datetime.fromtimestamp(nb_file.stat().st_mtime)
                notebooks.append({
                    "name": nb_file.name,
                    "cells": cells,
                    "last_run": mtime.strftime("%Y-%m-%d %H:%M"),
                    "status": "clean",
                })
            except Exception:
                continue
    return {"notebooks": notebooks}


# ---- Static Files + SPA ----
# Mount static files last so API routes take priority
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/{path:path}")
async def catch_all(path: str):
    """Serve static files or fall back to index.html."""
    file_path = STATIC_DIR / path
    if file_path.is_file():
        return FileResponse(str(file_path))
    return FileResponse(str(STATIC_DIR / "index.html"))


# ---- Main ----
if __name__ == "__main__":
    import uvicorn

    print(f"GPU Wrangler API starting on port {PORT}")
    print(f"Open http://localhost:{PORT} in your browser")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
