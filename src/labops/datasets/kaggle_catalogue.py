from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orjson


RNA_HINTS: dict[str, dict[str, str]] = {
    "stanford-rna-3d-folding": {
        "domain": "rna_3d_folding",
        "data_shape": "sequence -> 3D coordinates",
        "representation": "RNA sequence, atom coordinates (PDB-like)",
        "target": "predict nucleotide 3D structure",
        "validation_dropout": "family/time split + hard-sequence holdout",
    },
    "stanford-rna-3d-folding-part-2": {
        "domain": "rna_3d_folding",
        "data_shape": "sequence -> 3D coordinates",
        "representation": "RNA sequence, atom coordinates (PDB-like)",
        "target": "predict nucleotide 3D structure",
        "validation_dropout": "temporal holdout + motif holdout",
    },
    "stanford-ribonanza-rna-folding": {
        "domain": "rna_folding",
        "data_shape": "sequence -> structure/reactivity",
        "representation": "sequence + structural labels",
        "target": "predict RNA folding behavior",
        "validation_dropout": "family split + sequence-identity holdout",
    },
    "open-problems-multimodal-single-cell-integration": {
        "domain": "single_cell_multimodal",
        "data_shape": "cells x modalities matrix",
        "representation": "DNA/RNA/protein embeddings",
        "target": "predict cross-modal relationships",
        "validation_dropout": "donor/site split",
    },
}


def _to_int(v: Any) -> int:
    try:
        if v is None:
            return 0
        s = str(v).strip()
        if not s:
            return 0
        s = s.replace(",", "")
        if s.isdigit():
            return int(s)
    except Exception:
        return 0
    return 0


def _infer_domain(title: str, ref: str) -> str:
    t = f"{title} {ref}".lower()
    if "rna" in t and "3d" in t:
        return "rna_3d_folding"
    if "rna" in t and "single-cell" in t:
        return "single_cell_rna"
    if "rna" in t:
        return "rna"
    if "single-cell" in t:
        return "single_cell"
    return "other"


def _infer_shape(domain: str) -> tuple[str, str, str]:
    if domain == "rna_3d_folding":
        return (
            "sequence -> 3D coordinates",
            "tokenized sequence + atom coordinate tensors",
            "predict nucleotide 3D structure",
        )
    if domain in {"rna", "single_cell_rna"}:
        return (
            "sequence/matrix -> labels or regressions",
            "sequence tokens or expression matrices",
            "predict structural or expression targets",
        )
    if domain == "single_cell_multimodal":
        return (
            "cells x modalities matrix",
            "multi-omics aligned tensors",
            "predict cross-modal co-variation",
        )
    return ("tabular/text/image mixed", "framework-specific", "task-specific")


def _load_models(api: Any, search: str, limit: int) -> list[Any]:
    for method in ("models_list", "model_list"):
        fn = getattr(api, method, None)
        if fn is None:
            continue
        try:
            rows = fn(search=search)
            return list(rows)[:limit]
        except Exception:
            continue
    return []


def _load_notebooks(api: Any, search: str, limit: int) -> list[Any]:
    fn = getattr(api, "kernels_list", None)
    if fn is None:
        return []
    try:
        rows = fn(search=search)
        return list(rows)[:limit]
    except Exception:
        return []


def build_catalogue(out: Path, search: str = "rna", limit: int = 80) -> Path:
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()

    competitions = list(api.competitions_list(search=search))[:limit]
    datasets = list(api.dataset_list(search=search))[:limit]
    models = _load_models(api, search=search, limit=limit)
    notebooks = _load_notebooks(api, search=search, limit=limit)

    comp_items: list[dict[str, Any]] = []
    for c in competitions:
        ref = str(getattr(c, "ref", ""))
        title = str(getattr(c, "title", ""))
        slug = ref.strip().lower()
        domain = RNA_HINTS.get(slug, {}).get("domain", _infer_domain(title, ref))
        default_shape, default_repr, default_target = _infer_shape(domain)
        hint = RNA_HINTS.get(slug, {})
        comp_items.append(
            {
                "kind": "competition",
                "ref": ref,
                "title": title,
                "host": str(getattr(c, "hostSegmentTitle", "")),
                "reward": str(getattr(c, "reward", "")),
                "teams": _to_int(getattr(c, "teamCount", 0)),
                "deadline": str(getattr(c, "deadline", "")),
                "url": f"https://www.kaggle.com/competitions/{ref}",
                "domain": domain,
                "data_shape": hint.get("data_shape", default_shape),
                "representation": hint.get("representation", default_repr),
                "target": hint.get("target", default_target),
                "validation_dropout": hint.get("validation_dropout", "stratified split + out-of-distribution holdout"),
            }
        )

    ds_items: list[dict[str, Any]] = []
    for d in datasets:
        ref = str(getattr(d, "ref", ""))
        title = str(getattr(d, "title", ""))
        domain = _infer_domain(title, ref)
        default_shape, default_repr, default_target = _infer_shape(domain)
        ds_items.append(
            {
                "kind": "dataset",
                "ref": ref,
                "title": title,
                "size_bytes": int(getattr(d, "totalBytes", 0) or 0),
                "updated": str(getattr(d, "lastUpdated", "")),
                "license": str(getattr(d, "licenseName", "")),
                "url": f"https://www.kaggle.com/datasets/{ref}",
                "domain": domain,
                "data_shape": default_shape,
                "representation": default_repr,
                "target": default_target,
                "validation_dropout": "dataset source holdout + temporal split",
            }
        )

    model_items: list[dict[str, Any]] = []
    for m in models:
        ref = str(getattr(m, "ref", "") or getattr(m, "modelRef", ""))
        title = str(getattr(m, "title", "") or getattr(m, "name", ref))
        domain = _infer_domain(title, ref)
        default_shape, default_repr, default_target = _infer_shape(domain)
        model_items.append(
            {
                "kind": "model",
                "ref": ref,
                "title": title,
                "updated": str(getattr(m, "lastUpdated", "")),
                "url": f"https://www.kaggle.com/models/{ref}" if ref else "",
                "domain": domain,
                "data_shape": default_shape,
                "representation": default_repr,
                "target": default_target,
                "validation_dropout": "challenge-specific external holdout",
            }
        )

    notebook_items: list[dict[str, Any]] = []
    for k in notebooks:
        ref = str(getattr(k, "ref", ""))
        title = str(getattr(k, "title", ""))
        domain = _infer_domain(title, ref)
        default_shape, default_repr, default_target = _infer_shape(domain)
        notebook_items.append(
            {
                "kind": "notebook",
                "ref": ref,
                "title": title,
                "author": str(getattr(k, "author", "")),
                "votes": _to_int(getattr(k, "totalVotes", 0)),
                "last_run": str(getattr(k, "lastRunTime", "")),
                "url": f"https://www.kaggle.com/code/{ref}" if ref else "",
                "domain": domain,
                "data_shape": default_shape,
                "representation": default_repr,
                "target": default_target,
                "validation_dropout": "external leaderboard + local holdout replay",
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "search": search,
        "limit": limit,
        "summary": {
            "competitions": len(comp_items),
            "datasets": len(ds_items),
            "models": len(model_items),
            "notebooks": len(notebook_items),
        },
        "items": comp_items + model_items + notebook_items + ds_items,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
    return out
