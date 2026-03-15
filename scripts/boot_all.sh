#!/usr/bin/env bash
# boot_all.sh — Start everything after instance restart.
# Run: bash /workspace/backstage-server-lab/scripts/boot_all.sh
set -uo pipefail

cd /workspace/backstage-server-lab
echo "=== RNA 3D Lab Boot ==="
echo "  Instance: ${VAST_CONTAINERLABEL:-unknown}"
echo "  Time: $(date -u)"

# 1. Core services (TensorBoard, Streamlit, Portal)
echo "→ Starting supervised services..."
bash scripts/supervisor.sh start_all 2>&1 | grep -E 'started|complete'

# 2. Monitoring stack
echo "→ Starting monitoring..."
nohup node_exporter --web.listen-address=:9100 > /workspace/logs/node_exporter.log 2>&1 &
nohup python3 scripts/gpu_exporter.py > /workspace/logs/gpu_exporter.log 2>&1 &
nohup prometheus --config.file=configs/prometheus.yml --storage.tsdb.path=/workspace/logs/prometheus --web.listen-address=:9090 --storage.tsdb.retention.time=30d > /workspace/logs/prometheus.log 2>&1 &
nohup grafana-server --homepath=/usr/share/grafana web > /workspace/logs/grafana.log 2>&1 &
echo "  monitoring started (Grafana :3000, Prometheus :9090)"

# 3. Notebook Lab
echo "→ Starting Notebook Lab..."
nohup python3 web/notebook-lab/api.py > /workspace/logs/notebook-lab.log 2>&1 &
echo "  notebook lab started (:8521)"

# 4. Validation harness
echo "→ Starting Validation Dashboard..."
PYTHONPATH=src nohup python3 -m labops.validation_harness --molecules 40 --serve --port 8522 > /workspace/logs/validation.log 2>&1 &
echo "  validation dashboard started (:8522)"

# 5. MLOps Lab UI
echo "→ Starting MLOps Lab..."
PYTHONPATH=src nohup streamlit run src/labops/mlops_lab_app.py --server.port 8523 --server.address 0.0.0.0 --server.headless true > /workspace/logs/mlops_lab.log 2>&1 &
echo "  mlops lab started (:8523)"

# 6. Verify
sleep 8
echo ""
echo "=== Service Health ==="
for name_port in "Streamlit:1111" "TensorBoard:6006" "Grafana:3000" "Portal:8520" "NotebookLab:8521" "Validation:8522" "MLOpsLab:8523" "Prometheus:9090"; do
    n=${name_port%%:*}; p=${name_port##*:}
    code=$(curl -sf -o /dev/null -w '%{http_code}' --max-time 3 "http://localhost:$p/" 2>/dev/null || echo "---")
    printf "  %-14s :%-5s %s\n" "$n" "$p" "$code"
done

# 6. GPU check
echo ""
echo "=== GPU ==="
python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')" 2>/dev/null || echo "CUDA check failed"
nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "nvidia-smi failed"

echo ""
echo "=== Boot complete ==="
