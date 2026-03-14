# GPU Worker Operations

Deterministic shell-first workflow for a Vast.ai (or equivalent) GPU node.

## 1. Clone and bootstrap

```bash
cd /workspace
git clone https://github.com/uprootiny/backstage-server-lab.git backstage-server-lab
cd backstage-server-lab
bash scripts/bootstrap.sh
```

## 2. Start services

```bash
cd /workspace/backstage-server-lab
bash scripts/up.sh
bash scripts/sanity.sh
```

Expected listeners:

- `:8080` Jupyter
- `:1111` MLflow
- `:6006` TensorBoard
- `:8511` Kaggle mashup UI (if launched)

## 3. Run validation bench

```bash
cd /workspace/backstage-server-lab
bash scripts/run_validation_bench.sh hypothesis-demo
```

## 4. Run experiment variants

```bash
cd /workspace/backstage-server-lab
source .venv/bin/activate
labops run experiments/exp1.yaml --workers 3
```

## 5. Launch Kaggle mashup UI

Requires `~/.kaggle/kaggle.json` or `KAGGLE_USERNAME` + `KAGGLE_KEY`.

```bash
cd /workspace/backstage-server-lab
bash scripts/run_kaggle_mashup.sh
```

Open `http://<gpu-host>:8511`.

## 6. Stop services cleanly

```bash
cd /workspace/backstage-server-lab
bash scripts/down.sh
```

## 7. Durability discipline

If node disk is ephemeral, sync artifacts and push code regularly.

```bash
cd /workspace/backstage-server-lab
make sync DEST=user@backup-host:/path/backstage-server-lab
git add -A && git commit -m "checkpoint" && git push
```
