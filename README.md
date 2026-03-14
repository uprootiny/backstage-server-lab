# Backstage Server Lab

A clone-friendly, single-node ML/dev workspace optimized for Vast.ai Jupyter boxes and SSH-driven operations.

## Design goals

- one-command bootstrap on a fresh GPU worker
- reproducible Python/toolchain via `mise` + `uv`
- comfy terminal/Jupyter setup (`tmux`, sensible defaults, aliases)
- minimal MLOps spine (MLflow + TensorBoard + run logs)
- explicit durability hooks (artifact sync)

## Quick start (on Vast / Jupyter terminal)

```bash
git clone https://github.com/uprootiny/backstage-server-lab.git backstage-server-lab
cd backstage-server-lab
bash scripts/bootstrap.sh
make up
make sanity
```

## Daily workflow

```bash
cd backstage-server-lab
make up
make train-stub
make down
```

## Layout

- `scripts/` setup and service management
- `src/` training and utility code
- `configs/` experiment configs
- `artifacts/` checkpoints/models/tb logs
- `logs/` service and run logs
- `docs/` operational notes

## Notes

- If the Vast instance has no attached volume, treat local state as ephemeral.
- Use `make sync DEST=user@host:/path/backup` frequently.
