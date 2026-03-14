SHELL := /bin/bash
LAB_ROOT ?= $(CURDIR)

bootstrap:
	bash scripts/bootstrap.sh

up:
	bash scripts/up.sh

down:
	bash scripts/down.sh

sanity:
	bash scripts/sanity.sh

doctor:
	bash scripts/connection_doctor.sh

train-stub:
	. .venv/bin/activate && python -m src.train_stub --config configs/exp1.yaml

bench:
	. .venv/bin/activate && bash scripts/run_validation_bench.sh hypothesis-demo

graph:
	. .venv/bin/activate && labops graph --out artifacts/thesis_graph.json

kaggle-mashup:
	. .venv/bin/activate && bash scripts/run_kaggle_mashup.sh

rna-bridge:
	bash scripts/start_rna_artifact_bridge.sh

rna-register:
	@if [[ -z "$$PDB" ]]; then echo "usage: make rna-register PDB=/path/prediction.pdb [RUN_ID=...] [SEQUENCE=...] [MODEL=...]"; exit 2; fi
	bash scripts/register_rna_prediction.sh "$$PDB" "$${RUN_ID:-}" "$${SEQUENCE:-unknown}" "$${MODEL:-unknown}"

tb:
	. .venv/bin/activate && tensorboard --logdir artifacts --host 0.0.0.0 --port 6006

mlflow:
	. .venv/bin/activate && mlflow server --host 0.0.0.0 --port 1111 --backend-store-uri sqlite:///$(LAB_ROOT)/mlflow.db --default-artifact-root $(LAB_ROOT)/artifacts

sync:
	@if [[ -z "$$DEST" ]]; then echo "usage: make sync DEST=user@host:/path"; exit 2; fi
	rsync -avz --delete artifacts/ "$$DEST"/
