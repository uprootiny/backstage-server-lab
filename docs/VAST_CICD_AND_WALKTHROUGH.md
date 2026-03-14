# Vast CI/CD + Walkthrough

## CI/CD deploy pattern

1. Push to `main`
2. GitHub Actions syncs repo to Vast instance
3. Action restarts Streamlit observatory
4. Action probes live URL + Jupyter + SSH reachability
5. Action stores probe report artifact

## Manual fallback deploy

```bash
rsync -az --delete --exclude '.git' --exclude '.venv' \
  -e 'ssh -i ~/.ssh/gpu_orchestra_ed25519 -p 19636' \
  ./ root@175.155.64.231:/workspace/backstage-server-lab/

ssh -i ~/.ssh/gpu_orchestra_ed25519 -p 19636 root@175.155.64.231 '
  cd /workspace/backstage-server-lab
  pkill -f "streamlit run src/labops/kaggle_mashup_app.py" || true
  nohup /venv/main/bin/streamlit run src/labops/kaggle_mashup_app.py \
    --server.port 8520 --server.address 0.0.0.0 --server.headless true \
    >/workspace/logs/observatory-8520.log 2>&1 &
'
```

## One-click scientific loop

```bash
make notebook-pull
make notebook-interactive
make notebook-clickthrough
```

Outputs:
- `artifacts/top_notebook_analysis.json`
- `docs/TOP_NOTEBOOK_DIGEST.md`
- `artifacts/kaggle_parallel/plan.json`
- `artifacts/kaggle_parallel/ledger.jsonl`

## Live surfaces

- Observatory: `https://generous-ladder-twins-sims.trycloudflare.com`
- Jupyter: `https://175.155.64.231:19808`
- SSH: `ssh -i ~/.ssh/gpu_orchestra_ed25519 -p 19636 root@175.155.64.231`
