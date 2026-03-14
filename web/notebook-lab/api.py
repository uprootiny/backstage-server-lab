"""
Notebook Lab API - FastAPI backend for the RNA 3D Lab notebook interface.

Serves on port 8521. Provides notebook listing, loading, cell execution,
GPU status, and static file serving.

Usage:
    uvicorn api:app --host 0.0.0.0 --port 8521
    # or
    python api.py
"""

import base64
import json
import os
import subprocess
import tempfile
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
NOTEBOOKS_DIR = REPO_DIR / "notebooks"
SRC_DIR = REPO_DIR / "src"
STATIC_DIR = Path(__file__).parent
PORT = 8521

# ---- App ----
app = FastAPI(
    title="Notebook Lab API",
    description="Backend for the RNA 3D Lab notebook interface",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Models ----
class ExecuteRequest(BaseModel):
    code: str


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
            t = t.split()[0] if t else str(default)
            try:
                return float(t)
            except (ValueError, TypeError):
                return default

        vram_used = num("fb_memory_usage/used")
        vram_total = num("fb_memory_usage/total")
        if vram_used > 100:  # Likely MiB
            vram_used = round(vram_used / 1024, 1)
            vram_total = round(vram_total / 1024, 1)

        return {
            "name": text("product_name", "Unknown GPU"),
            "utilization": int(num("utilization/gpu_util")),
            "vram_used": vram_used,
            "vram_total": vram_total,
            "temperature": int(num("temperature/gpu_temp")),
            "power_draw": int(
                num("gpu_power_readings/power_draw", 0)
                or num("power_readings/power_draw", 0)
            ),
            "power_limit": int(
                num("gpu_power_readings/enforced_power_limit", 450)
                or num("power_readings/enforced_power_limit", 450)
            ),
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


# ---- Notebook Listing ----
@app.get("/api/notebooks")
async def list_notebooks():
    """Scan notebooks/ directory for .ipynb files."""
    notebooks = []

    for search_dir in [NOTEBOOKS_DIR, REPO_DIR]:
        if not search_dir.exists():
            continue
        for nb_file in sorted(search_dir.rglob("*.ipynb")):
            # Skip checkpoints
            if ".ipynb_checkpoints" in str(nb_file):
                continue
            try:
                stat = nb_file.stat()
                rel_path = str(nb_file.relative_to(REPO_DIR))
                notebooks.append({
                    "name": nb_file.name,
                    "path": rel_path,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "size": stat.st_size,
                })
            except Exception:
                continue

    # Deduplicate by name
    seen = set()
    unique = []
    for nb in notebooks:
        if nb["name"] not in seen:
            seen.add(nb["name"])
            unique.append(nb)

    return unique


# ---- Load Notebook ----
@app.get("/api/notebook/{path:path}")
async def load_notebook(path: str):
    """Read an .ipynb file and return parsed cells."""
    nb_path = REPO_DIR / path
    if not nb_path.exists():
        # Try under notebooks/
        nb_path = NOTEBOOKS_DIR / path
    if not nb_path.exists():
        raise HTTPException(status_code=404, detail=f"Notebook not found: {path}")

    try:
        with open(nb_path) as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read notebook: {e}")

    cells = []
    for cell in data.get("cells", []):
        cell_type = cell.get("cell_type", "code")
        if cell_type not in ("code", "markdown"):
            cell_type = "code"

        source = cell.get("source", [])
        if isinstance(source, list):
            source = "".join(source)

        outputs = []
        for out in cell.get("outputs", []):
            out_type = out.get("output_type", "")
            if out_type == "stream":
                text = out.get("text", [])
                if isinstance(text, list):
                    text = "".join(text)
                outputs.append({"text": text})
            elif out_type in ("execute_result", "display_data"):
                odata = out.get("data", {})
                if "image/png" in odata:
                    outputs.append({"image": odata["image/png"]})
                elif "text/plain" in odata:
                    text = odata["text/plain"]
                    if isinstance(text, list):
                        text = "".join(text)
                    outputs.append({"text": text})
            elif out_type == "error":
                tb = out.get("traceback", [])
                # Strip ANSI codes
                import re
                clean = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(tb))
                outputs.append({"text": clean, "error": True})

        cells.append({
            "type": cell_type,
            "source": source,
            "outputs": outputs,
            "execution_count": cell.get("execution_count"),
        })

    return {"cells": cells}


# ---- Execute Code ----
@app.post("/api/execute")
async def execute_code(req: ExecuteRequest):
    """Execute a code cell via subprocess, capturing stdout, stderr, and images."""
    # Wrap code to capture matplotlib figures
    wrapper = _build_exec_wrapper(req.code)

    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "cell.py")
        with open(script_path, "w") as f:
            f.write(wrapper)

        env = {
            **os.environ,
            "PYTHONPATH": str(SRC_DIR) + ":" + os.environ.get("PYTHONPATH", ""),
            "MPLBACKEND": "Agg",
            "_NOTEBOOK_TMPDIR": tmpdir,
        }

        start = time.time()
        try:
            result = subprocess.run(
                ["python", script_path],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(REPO_DIR),
                env=env,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start) * 1000)
            return {
                "output": "",
                "images": [],
                "error": "Execution timed out (60s limit)",
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return {
                "output": "",
                "images": [],
                "error": f"Execution failed: {e}",
                "duration_ms": duration_ms,
            }

        duration_ms = int((time.time() - start) * 1000)

        # Collect images
        images = []
        img_dir = os.path.join(tmpdir, "figures")
        if os.path.exists(img_dir):
            for fname in sorted(os.listdir(img_dir)):
                if fname.endswith(".png"):
                    fpath = os.path.join(img_dir, fname)
                    with open(fpath, "rb") as img_f:
                        images.append(base64.b64encode(img_f.read()).decode())

        output = result.stdout or ""
        error = result.stderr or ""

        # If return code is non-zero and there's stderr, treat as error
        if result.returncode != 0 and error:
            return {
                "output": output,
                "images": images,
                "error": error,
                "duration_ms": duration_ms,
            }

        return {
            "output": output,
            "images": images,
            "error": None,
            "duration_ms": duration_ms,
        }


def _build_exec_wrapper(code: str) -> str:
    """Wrap user code to intercept matplotlib savefig/show calls."""
    return f'''
import os
import sys

# Setup figure capture directory
_tmpdir = os.environ.get("_NOTEBOOK_TMPDIR", "/tmp")
_fig_dir = os.path.join(_tmpdir, "figures")
os.makedirs(_fig_dir, exist_ok=True)
_fig_counter = [0]

# Monkey-patch matplotlib if available
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _orig_show = plt.show
    _orig_savefig = plt.savefig

    def _patched_show(*args, **kwargs):
        for fig_num in plt.get_fignums():
            fig = plt.figure(fig_num)
            _fig_counter[0] += 1
            path = os.path.join(_fig_dir, f"fig_{{_fig_counter[0]:03d}}.png")
            fig.savefig(path, dpi=150, bbox_inches="tight",
                        facecolor="#0a0c10", edgecolor="none")
        plt.close("all")

    plt.show = _patched_show
except ImportError:
    pass

# Execute user code
{code}

# Auto-save any remaining figures
try:
    import matplotlib.pyplot as plt
    if plt.get_fignums():
        _patched_show()
except (ImportError, NameError):
    pass
'''


# ---- Static Files ----
@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


# Mount static after API routes
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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

    print(f"Notebook Lab API starting on port {PORT}")
    print(f"Open http://localhost:{PORT} in your browser")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
