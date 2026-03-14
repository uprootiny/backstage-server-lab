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

kaggle-catalogue:
	. .venv/bin/activate && bash scripts/build_kaggle_catalogue.sh rna 120 artifacts/kaggle_catalogue.json

kaggle-minimap:
	. .venv/bin/activate && labops kaggle-notebook-minimap --search rna --limit 300 --out-json artifacts/kaggle_rna_notebooks_minimap.json --out-md docs/KAGGLE_RNA_NOTEBOOK_MINIMAP.md

submission-profile:
	@if [[ -z "$$INPUT" ]]; then echo "usage: make submission-profile INPUT=/path/submission.csv"; exit 2; fi
	. .venv/bin/activate && labops submission-profile "$$INPUT"

submission-register:
	@if [[ -z "$$NOTEBOOK" || -z "$$INPUT" ]]; then echo "usage: make submission-register NOTEBOOK=user/notebook INPUT=/path/submission.csv [MARK=candidate] [BREADCRUMB=...] [SEQUENCE=...] [MODEL=...] [RUN_ID=...] [SAMPLE_IDX=1] [TARGET_ID=...]"; exit 2; fi
	. .venv/bin/activate && labops submission-register "$$NOTEBOOK" "$$INPUT" --mark "$${MARK:-candidate}" --breadcrumb "$${BREADCRUMB:-}" --sequence "$${SEQUENCE:-}" --model "$${MODEL:-unknown}" --run-id "$${RUN_ID:-}" --sample-idx "$${SAMPLE_IDX:-1}" --target-id "$${TARGET_ID:-}"

submission-list:
	. .venv/bin/activate && labops submission-list

rna-bridge:
	bash scripts/start_rna_artifact_bridge.sh

rna-workbench:
	bash scripts/start_rna_workbench.sh

rna-register:
	@if [[ -z "$$PDB" ]]; then echo "usage: make rna-register PDB=/path/prediction.pdb [RUN_ID=...] [SEQUENCE=...] [MODEL=...]"; exit 2; fi
	bash scripts/register_rna_prediction.sh "$$PDB" "$${RUN_ID:-}" "$${SEQUENCE:-unknown}" "$${MODEL:-unknown}"

rna-ingest:
	@if [[ -z "$$INPUT" ]]; then echo "usage: make rna-ingest INPUT=/path/result.(pdb|csv|json|npy|npz) [RUN_ID=...] [SEQUENCE=...] [MODEL=...]"; exit 2; fi
	. .venv/bin/activate && labops ingest-result "$$INPUT" --run-id "$${RUN_ID:-}" --sequence "$${SEQUENCE:-}" --model "$${MODEL:-unknown}"

technique-list:
	. .venv/bin/activate && labops technique-list

technique-compose:
	@if [[ -z "$$IDS" ]]; then echo "usage: make technique-compose IDS=tbm_ensemble,recycling_refinement,confidence_calibration"; exit 2; fi
	. .venv/bin/activate && labops technique-compose "$$IDS"

kaggle-parallel-init:
	. .venv/bin/activate && labops kaggle-parallel-init --profile "$${PROFILE:-three}" --out "$${PLAN:-artifacts/kaggle_parallel/plan.yaml}" --notebooks-dir "$${NOTEBOOKS_DIR:-notebooks/kaggle}"

kaggle-parallel-dispatch:
	. .venv/bin/activate && labops kaggle-parallel-dispatch --plan "$${PLAN:-artifacts/kaggle_parallel/plan.yaml}" --workers "$${WORKERS:-3}" --ledger "$${LEDGER:-artifacts/kaggle_parallel/ledger.jsonl}" --logs-dir "$${LOGS_DIR:-logs/kaggle_parallel}" --executed-dir "$${EXECUTED_DIR:-artifacts/kaggle_parallel/executed}"

kaggle-parallel-status:
	. .venv/bin/activate && labops kaggle-parallel-status --ledger "$${LEDGER:-artifacts/kaggle_parallel/ledger.jsonl}"

kaggle-parallel-reruns:
	. .venv/bin/activate && labops kaggle-parallel-reruns --ledger "$${LEDGER:-artifacts/kaggle_parallel/ledger.jsonl}" --min-voi "$${MIN_VOI:-0.12}" --limit "$${LIMIT:-12}"

notebook-pull:
	. .venv/bin/activate && python scripts/pull_notebook_sources.py

notebook-interactive:
	. .venv/bin/activate && python scripts/build_interactive_orchestrator_notebook.py

notebook-clickthrough:
	bash scripts/clickthrough_notebook_fabric.sh

obs-setup:
	bash scripts/setup_repo_observability.sh

obs-up:
	bash scripts/start_repo_observability.sh

obs-down:
	bash scripts/stop_repo_observability.sh

obs-probe:
	bash scripts/probe_live_endpoints.sh

tb:
	. .venv/bin/activate && tensorboard --logdir artifacts --host 0.0.0.0 --port 6006

mlflow:
	. .venv/bin/activate && mlflow server --host 0.0.0.0 --port 1111 --backend-store-uri sqlite:///$(LAB_ROOT)/mlflow.db --default-artifact-root $(LAB_ROOT)/artifacts

sync:
	@if [[ -z "$$DEST" ]]; then echo "usage: make sync DEST=user@host:/path"; exit 2; fi
	rsync -avz --delete artifacts/ "$$DEST"/
