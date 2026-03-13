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

train-stub:
	. .venv/bin/activate && python -m src.train_stub --config configs/exp1.yaml

tb:
	. .venv/bin/activate && tensorboard --logdir artifacts --host 0.0.0.0 --port 6006

mlflow:
	. .venv/bin/activate && mlflow server --host 0.0.0.0 --port 1111 --backend-store-uri sqlite:///$(LAB_ROOT)/mlflow.db --default-artifact-root $(LAB_ROOT)/artifacts

sync:
	@if [[ -z "$$DEST" ]]; then echo "usage: make sync DEST=user@host:/path"; exit 2; fi
	rsync -avz --delete artifacts/ "$$DEST"/
