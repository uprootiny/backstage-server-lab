# Top Kaggle Notebook Digest

- generated_at: 2026-03-14T12:45:00Z
- notebooks: 6

## Through-and-through recap

### Stanford RNA 3D Folding — Top 1 Solution
- ref: `sigmaborov/stanford-rna-3d-folding-top-1-solution`
- pulled: `True`
- local_path: `notebooks/kaggle/sigmaborov-top1/stanford-rna-3d-folding-top-1-solution.ipynb`
- techniques: `tbm_first_routing, protenix_fallback, template_similarity_thresholding`
- key_params: `{"MIN_SIMILARITY": 0.1, "MIN_PERCENT_IDENTITY": 55.0, "MODEL_NAME": "protenix_base_20250630_v1.0.0", "N_SAMPLE": 5}`
- summary: Integrated and reproduced on Vast via local-adapted notebook. Harness run id `kaggle-parallel-20260314T123902Z` completed with `status=ok` and produced submission artifact.
- reproduce: `PYTHONPATH=/workspace/backstage-server-lab/src /venv/main/bin/python -m labops.cli kaggle-parallel-dispatch --plan artifacts/kaggle_parallel/plan_sigmaborov_local.json --workers 1 --ledger artifacts/kaggle_parallel/ledger.jsonl --logs-dir logs/kaggle_parallel --executed-dir artifacts/kaggle_parallel/executed`

### Protenix + TBM (RNA 3D Part 2)
- ref: `llkh0a/stanford-rna-3d-folding-part-2-protenix-tbm`
- pulled: `False`
- local_path: `(not available)`
- techniques: `manual_review_required`
- key_params: `{}`
- summary: Notebook pull failed (auth/network/availability). Kept reproducible stub.
- reproduce: `kaggle kernels pull llkh0a/stanford-rna-3d-folding-part-2-protenix-tbm -p tmp/kaggle_top_notebooks --metadata`

### RNA Starter Baseline
- ref: `iafoss/rna-starter`
- pulled: `False`
- local_path: `(not available)`
- techniques: `manual_review_required`
- key_params: `{}`
- summary: Notebook pull failed (auth/network/availability). Kept reproducible stub.
- reproduce: `kaggle kernels pull iafoss/rna-starter -p tmp/kaggle_top_notebooks --metadata`

### Stanford Ribonanza 2nd Place Summary
- ref: `hoyso48/stanford-ribonanza-2nd-place-solution`
- pulled: `False`
- local_path: `(not available)`
- techniques: `manual_review_required`
- key_params: `{}`
- summary: Notebook pull failed (auth/network/availability). Kept reproducible stub.
- reproduce: `kaggle kernels pull hoyso48/stanford-ribonanza-2nd-place-solution -p tmp/kaggle_top_notebooks --metadata`

### OpenChemFold RNA 3D
- ref: `gosuxd/openchemfold-rna3d`
- pulled: `False`
- local_path: `(not available)`
- techniques: `manual_review_required`
- key_params: `{}`
- summary: Notebook pull failed (auth/network/availability). Kept reproducible stub.
- reproduce: `kaggle kernels pull gosuxd/openchemfold-rna3d -p tmp/kaggle_top_notebooks --metadata`

### RibonanzaNet2 Training Notes
- ref: `shujunhe/ribonanzanet2-training-notes`
- pulled: `False`
- local_path: `(not available)`
- techniques: `manual_review_required`
- key_params: `{}`
- summary: Notebook pull failed (auth/network/availability). Kept reproducible stub.
- reproduce: `kaggle kernels pull shujunhe/ribonanzanet2-training-notes -p tmp/kaggle_top_notebooks --metadata`
