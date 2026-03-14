# Reading Track: RNA Research Playground (From Kaggle Artifact to Legible Science)

This reading track is meant to be used while operating the repo, not as abstract theory.
It maps exactly to commands and files in this workspace.

## Stage 1: Why this system exists

Most Kaggle RNA notebooks are useful but opaque.
They blend assumptions, architecture, and post-processing into one artifact.
The core goal of this repo is to split that opacity into reusable parts:

- identify what a notebook is doing
- normalize output into stable intermediate representations
- render outputs in one shared viewer stack
- compare runs and techniques in context
- carry validated methods into new experiments

Key command families:

- catalogue + minimap: `make kaggle-catalogue`, `make kaggle-minimap`
- ingestion: `make rna-ingest`, `make submission-profile`, `make submission-register`
- orchestration: `labops run`, `labops run-bench`, `labops validate`
- rendering: `make rna-workbench`, `make rna-bridge`

## Stage 2: Representation discipline

The system is built around representation bridges.
Notebook outputs differ wildly: CSV coordinates, pairwise matrices, confidence vectors, PDB-like dumps.
Everything should converge toward a stable record shape.

Operational rule:

1. profile artifact format
2. infer conversion route
3. normalize into viewer-ready structure
4. register provenance + breadcrumb + mark status

Use:

```bash
make submission-profile INPUT=/path/to/submission.csv
make submission-register NOTEBOOK=user/notebook INPUT=/path/to/submission.csv MARK=review BREADCRUMB="candidate for template+recycling"
make submission-list
```

## Stage 3: Technique recomposition

The minimap and technique library support extraction of reusable method blocks.
Do not copy full notebooks mechanically; compose techniques into explicit experiment plans.

Technique flow:

```bash
make technique-list
make technique-compose IDS=tbm_ensemble,pairwise_distogram_head,recycling_refinement,confidence_calibration
labops run artifacts/technique_compositions/composed_experiment.yaml --workers 3
```

This gives you:

- explicit hypothesis
- selected techniques
- knobs to perturb
- generated experiment template

## Stage 4: High-level playground behavior

The target UX is a scientific instrument panel:

- Atlas: challenge/model/notebook discovery
- Pipeline: stage-level influence view
- Viewer: sequence/contact-map/3D shape alignment
- Registry: mark/shelve/breadcrumb and return to key runs

The current repo already ships core pieces for this behavior:

- RNA workbench page (`rna_workbench.html`)
- artifact bridge index (`artifacts/rna_predictions/index.json`)
- notebook registry (`artifacts/notebook_submission_registry.jsonl`)
- minimap docs (`docs/KAGGLE_RNA_NOTEBOOK_MINIMAP.md`)

## Stage 5: Validation as first-class object

Do not optimize only for public leaderboard movement.
Every experiment should be tied to a validation claim and VOI.

Use:

```bash
labops formulate --hypothesis-id h1 --statement "Recycling improves local loop geometry" --question "Does recycling reduce RMSD on held-out families?" --voi-prior 0.7
labops run-bench --hypothesis-id h1
labops validate --min-metric 0.70
labops graph --out artifacts/thesis_graph.json
```

This keeps progress cumulative and inspectable.

## Stage 6: Observability coupling

A research playground without observability drifts into untraceable behavior.
Use repo observability to monitor the engineering surface while RNA metrics monitor the model surface.

- engineering surface: commits, PRs, workflows, failure rates
- modeling surface: run quality, validation pass rates, confidence distributions

Start with:

```bash
make obs-setup
make obs-probe
```

Then connect this with run artifacts and benchmark summaries.

## Stage 7: Operational loop (daily)

```bash
git pull
make sanity
make kaggle-minimap
make technique-compose IDS=tbm_ensemble,recycling_refinement,confidence_calibration
labops run artifacts/technique_compositions/composed_experiment.yaml --workers 3
make obs-probe
```

If you ingest a new notebook result:

```bash
make submission-profile INPUT=/path/to/submission.csv
make submission-register NOTEBOOK=user/notebook INPUT=/path/to/submission.csv MARK=candidate BREADCRUMB="interesting confidence head"
make rna-workbench
```

## Stage 8: Free-stack mode

When compute must be minimized:

- keep observability on a cheap/free CPU host
- pause heavy GPU services
- continue catalogue, minimap, and submission profiling locally
- queue experiments for when high-memory GPUs are available

This preserves research continuity without wasting GPU time.

## Stage 9: Recommended next implementation slice

- parse top 50 Kaggle RNA submissions into typed profiles
- create conversion adapters for contact maps and dot-bracket outputs
- auto-link registered submissions into workbench compare dropdown
- attach benchmark metric summary next to each registered run

This gives immediate legibility gains without massive infra changes.
