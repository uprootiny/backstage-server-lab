# Kaggle RNA Catalogue

This catalogue normalizes Kaggle search results into a single structured inventory:

- competitions
- models (when API surface is available)
- notebooks
- datasets

Each item is enriched with:

- `domain`
- `data_shape`
- `representation`
- `target`
- `validation_dropout`

## Build

```bash
cd /workspace/backstage-server-lab
make kaggle-catalogue
```

Output:

- `artifacts/kaggle_catalogue.json`

## Use in UI

```bash
bash scripts/run_kaggle_mashup.sh
```

In the app:

1. Open `Structured Catalogue` tab.
2. Toggle `Refresh structured catalogue`.
3. Filter by domains (e.g. `rna_3d_folding`) and item type (`competition`, `notebook`, `dataset`, `model`).

## Starter notebooks

Local starter templates are versioned under:

- `notebooks/starters/index.json`
- `notebooks/starters/*.ipynb`

These are shown in the `Starter Notebook Library` tab.
