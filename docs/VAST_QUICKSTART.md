# Vast Quickstart

## Clone and bootstrap

```bash
bash scripts/vast_clone_bootstrap.sh https://github.com/uprootiny/backstage-server-lab.git /workspace/backstage-server-lab
```

## Service endpoints

- Jupyter: `:8080`
- MLflow: `:1111`
- TensorBoard: `:6006`

## Safe shutdown

```bash
cd /workspace/backstage-server-lab
bash scripts/down.sh
```

## Durability

- Push code to git remote.
- Sync artifacts off-box regularly:

```bash
make sync DEST=user@host:/path/backups/backstage-server-lab
```
