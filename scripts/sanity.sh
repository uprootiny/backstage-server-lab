#!/usr/bin/env bash
set -euo pipefail

echo "== GPU =="
nvidia-smi || true

echo "== Python/Torch =="
python - <<'PY'
import sys
print("python:", sys.version)
try:
    import torch
    print("torch:", torch.__version__)
    print("cuda_available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("device:", torch.cuda.get_device_name(0))
except Exception as e:
    print("torch_check_error:", e)
PY

echo "== Ports =="
ss -ltn | grep -E ':1111|:6006|:8511|:19999' || true
