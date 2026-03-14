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
START_KAGGLE_MASHUP=1 bash scripts/up.sh
bash scripts/sanity.sh
bash scripts/connection_doctor.sh
```

Expected listeners:

- `:8080` Jupyter
- `:1111` MLflow
- `:6006` TensorBoard
- `:8511` Kaggle mashup UI (if launched)
- `:19999` RNA artifact bridge
- `:8522` RNA workbench

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
make kaggle-catalogue
bash scripts/run_kaggle_mashup.sh
```

Open `http://<gpu-host>:8511`.

## 5b. Register RNA prediction outputs for workbench loaders

```bash
cd /workspace/backstage-server-lab
make rna-register PDB=/workspace/path/to/prediction.pdb RUN_ID=exp42 SEQUENCE=AUGC MODEL=baseline-v1
```

Then consume:

- `http://<gpu-host>:19999/index.json`
- `http://<gpu-host>:19999/exp42/prediction.pdb`

## 5c. Launch RNA workbench

```bash
cd /workspace/backstage-server-lab
make rna-workbench
```

Open:

- `http://<gpu-host>:8522/rna_workbench.html`

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

## 8. Public tunnel checks (optional)

Set any/all of these before running the doctor:

```bash
export MLFLOW_PUBLIC_URL="https://<mlflow-tunnel>"
export TENSORBOARD_PUBLIC_URL="https://<tb-tunnel>"
export JUPYTER_PUBLIC_URL="https://<jupyter-tunnel>"
export KAGGLE_MASHUP_PUBLIC_URL="https://<kaggle-tunnel>"
export RNA_BRIDGE_PUBLIC_URL="https://<rna-tunnel>"
bash scripts/connection_doctor.sh
```
