"""
Unified Portal Server — serves all web surfaces from one process.

Mounts:
  /              → Portal dashboard (index.html)
  /wrangler/     → GPU Wrangler UI
  /notebook/     → Notebook Lab UI
  /artifacts/    → Static renders & artifacts
  /api/          → Unified API (GPU status, runs, services, execute, notebooks)

Runs on port 8520.
"""
import asyncio
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

WORKSPACE = Path("/workspace")
REPO = WORKSPACE / "backstage-server-lab"
LOGS_DIR = WORKSPACE / "logs" / "rna"
ARTIFACTS_DIR = REPO / "artifacts"
NOTEBOOKS_DIR = REPO / "notebooks"
WEB_DIR = REPO / "web"

app = FastAPI(title="RNA 3D Lab Portal", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---- Static mounts ----
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_DIR)), name="artifacts")
if (WEB_DIR / "gpu-wrangler").exists():
    app.mount("/wrangler", StaticFiles(directory=str(WEB_DIR / "gpu-wrangler"), html=True), name="wrangler")
if (WEB_DIR / "notebook-lab").exists():
    app.mount("/notebook", StaticFiles(directory=str(WEB_DIR / "notebook-lab"), html=True), name="notebook")

# ---- Routes ----

@app.get("/", response_class=HTMLResponse)
async def portal_index():
    index = WEB_DIR / "portal" / "index.html"
    return index.read_text()

@app.get("/api/gpu-status")
async def gpu_status():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit,fan.speed,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        parts = [p.strip() for p in result.stdout.strip().split(",")]
        return {
            "name": parts[0] if len(parts) > 0 else "Unknown",
            "utilization": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
            "vram_used": float(parts[2]) / 1024 if len(parts) > 2 else 0,
            "vram_total": float(parts[3]) / 1024 if len(parts) > 3 else 32,
            "temperature": int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0,
            "power_draw": float(parts[5]) if len(parts) > 5 else 0,
            "power_limit": float(parts[6]) if len(parts) > 6 else 450,
            "fan_speed": int(parts[7]) if len(parts) > 7 and parts[7].isdigit() else 0,
            "driver": parts[8] if len(parts) > 8 else "?",
        }
    except Exception as e:
        return {"error": str(e), "name": "Unknown", "utilization": 0, "vram_used": 0, "vram_total": 32, "temperature": 0}

@app.get("/api/runs")
async def list_runs():
    runs = []
    if LOGS_DIR.exists():
        for d in sorted(LOGS_DIR.iterdir()):
            if d.is_dir():
                events = list(d.glob("events.out.*"))
                total_size = sum(f.stat().st_size for f in events)
                runs.append({
                    "name": d.name,
                    "n_events": len(events),
                    "size_kb": round(total_size / 1024, 1),
                    "modified": datetime.fromtimestamp(d.stat().st_mtime).isoformat(),
                })
    # Also read pipeline_runs.jsonl
    pipeline_runs = []
    prf = ARTIFACTS_DIR / "pipeline_runs.jsonl"
    if prf.exists():
        for line in prf.read_text().strip().split("\n"):
            if line.strip():
                try:
                    pipeline_runs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return {"tb_runs": runs, "pipeline_runs": pipeline_runs[-20:]}

@app.get("/api/services")
async def service_status():
    services = [
        {"name": "TensorBoard", "port": 6006, "id": "tb"},
        {"name": "GPU Wrangler", "port": 8520, "id": "gw"},
        {"name": "Notebook Lab", "port": 8521, "id": "nb"},
        {"name": "Streamlit", "port": 1111, "id": "st"},
        {"name": "Jupyter", "port": 8080, "id": "jp"},
    ]
    results = []
    for svc in services:
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}",
                f"http://localhost:{svc['port']}/",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=3)
            code = stdout.decode().strip()
            svc["status"] = "up" if code == "200" else f"http_{code}"
        except Exception:
            svc["status"] = "down"
        results.append(svc)
    return results

@app.get("/api/notebooks")
async def list_notebooks():
    nbs = []
    for pattern in ["**/*.ipynb"]:
        for f in NOTEBOOKS_DIR.glob(pattern):
            nbs.append({
                "name": f.name,
                "path": str(f.relative_to(REPO)),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    # Also include executed notebooks
    exec_dir = ARTIFACTS_DIR / "kaggle_parallel" / "executed"
    if exec_dir.exists():
        for f in exec_dir.glob("*.ipynb"):
            nbs.append({
                "name": f.name,
                "path": str(f.relative_to(REPO)),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                "executed": True,
            })
    return sorted(nbs, key=lambda x: x.get("modified", ""), reverse=True)

@app.get("/api/renders")
async def list_renders():
    renders = []
    for f in sorted(ARTIFACTS_DIR.glob("rna_*.png")):
        renders.append({
            "name": f.stem,
            "file": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "url": f"/artifacts/{f.name}",
        })
    return renders

@app.get("/api/checkpoints")
async def list_checkpoints():
    ckpts = []
    ckpt_dir = ARTIFACTS_DIR / "checkpoints"
    if ckpt_dir.exists():
        for f in ckpt_dir.glob("*.pt"):
            ckpts.append({
                "name": f.name,
                "size_mb": round(f.stat().st_size / 1e6, 2),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return ckpts

class RunConfig(BaseModel):
    n_samples: int = 256
    n_epochs: int = 30
    run_name: str = "custom_run"
    batch_size: int = 32
    lr: float = 3e-4

_active_processes: dict[str, subprocess.Popen] = {}

@app.post("/api/launch-run")
async def launch_run(config: RunConfig):
    cmd = [
        "python3", str(REPO / "src" / "labops" / "gpu_train.py"),
        "--samples", str(config.n_samples),
        "--epochs", str(config.n_epochs),
        "--run-name", config.run_name,
        "--log-dir", str(LOGS_DIR),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO / "src")
    proc = subprocess.Popen(cmd, env=env, cwd=str(REPO),
                            stdout=open(f"/workspace/logs/run_{config.run_name}.log", "w"),
                            stderr=subprocess.STDOUT)
    _active_processes[config.run_name] = proc
    return {"status": "launched", "pid": proc.pid, "run_name": config.run_name}

class CellExec(BaseModel):
    code: str
    timeout: int = 60

@app.post("/api/execute")
async def execute_cell(cell: CellExec):
    """Execute a Python code cell and return output."""
    # Wrap code to capture output and matplotlib figures
    wrapper = f"""
import sys, io, base64, json
_old_stdout = sys.stdout
sys.stdout = _buf = io.StringIO()
_images = []
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _orig_show = plt.show
    def _capture_show(*a, **kw):
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#0a0c10')
        _images.append(base64.b64encode(buf.getvalue()).decode())
        plt.close()
    plt.show = _capture_show
except:
    pass
_err = None
try:
    exec(compile('''{cell.code.replace(chr(39)*3, chr(39)*2+chr(92)+chr(39)+chr(39)*2)}''', '<cell>', 'exec'))
except Exception as e:
    _err = str(e)
sys.stdout = _old_stdout
print(json.dumps({{"output": _buf.getvalue(), "images": _images, "error": _err}}))
"""
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO / "src")
        proc = subprocess.run(
            ["python3", "-c", wrapper],
            capture_output=True, text=True, timeout=cell.timeout,
            cwd=str(REPO), env=env,
        )
        if proc.returncode == 0:
            try:
                result = json.loads(proc.stdout.strip().split("\n")[-1])
                return result
            except (json.JSONDecodeError, IndexError):
                return {"output": proc.stdout, "images": [], "error": proc.stderr or None}
        return {"output": proc.stdout, "images": [], "error": proc.stderr}
    except subprocess.TimeoutExpired:
        return {"output": "", "images": [], "error": f"Timeout after {cell.timeout}s"}
    except Exception as e:
        return {"output": "", "images": [], "error": str(e)}

if __name__ == "__main__":
    print(f"Portal server starting on port 8520")
    print(f"  Dashboard: http://localhost:8520/")
    print(f"  Wrangler:  http://localhost:8520/wrangler/")
    print(f"  Notebook:  http://localhost:8520/notebook/")
    print(f"  API:       http://localhost:8520/api/")
    uvicorn.run(app, host="0.0.0.0", port=8520, log_level="info")
