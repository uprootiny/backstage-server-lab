# Stack Doctor

- generated_at: 2026-03-14T16:34:14Z
- root: /workspace/backstage-server-lab
- auto_heal: 1

## Required Pieces

```
ok:/workspace/backstage-server-lab/src/labops/cli.py
ok:/workspace/backstage-server-lab/src/labops/kaggle_parallel.py
ok:/workspace/backstage-server-lab/src/labops/kaggle_mashup_app.py
ok:/workspace/backstage-server-lab/notebooks/starters/02_rna_3d_training_filled.ipynb
ok:/workspace/backstage-server-lab/artifacts/kaggle_parallel
```

## Service Matrix

| Surface | URL | State | HTTP |
|---|---|---|---:|
| MLflow local | http://127.0.0.1:1111 | UP | 200 |
| TensorBoard local | http://127.0.0.1:6006 | UP | 200 |
| Jupyter local | https://127.0.0.1:8080 | UP | 302 |
| Mashup local | http://127.0.0.1:8511 | DOWN | 000 |
| RNA bridge local | http://127.0.0.1:19999/index.json | UP | 200 |
| Jupyter public | https://175.155.64.231:19808 | UP | 302 |
| TensorBoard public | http://175.155.64.231:19448 | UP | 200 |
| Research library public | http://175.155.64.231:19121 | UP | 200 |
| Syncthing public | http://175.155.64.231:19753 | DOWN | 000 |
| Open 19842 public | http://175.155.64.231:19842 | DOWN | 000 |

## Harness Readiness

- python_cli_ready: 1
- kaggle_cli_ready: 1
- ledger_lines: 140
- job_end_ok: 23
- job_end_failed: 16

## GPU

```
NVIDIA GeForce RTX 4080 SUPER, 0 %, 15 MiB, 32760 MiB
```
