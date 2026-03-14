from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .rna_ingest import ingest_result


REGISTRY_PATH = Path("artifacts/notebook_submission_registry.jsonl")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def profile_submission(path: Path, sample_rows: int = 200) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)

    ext = path.suffix.lower()
    if ext not in {".csv", ".parquet", ".json", ".jsonl"}:
        return {
            "path": str(path),
            "format": "unknown",
            "hint": "supported: csv/parquet/json/jsonl",
            "created_at": _now(),
        }

    if ext == ".csv":
        df = pd.read_csv(path, nrows=sample_rows)
    elif ext == ".parquet":
        df = pd.read_parquet(path).head(sample_rows)
    else:
        raw = json.loads(path.read_text())
        if isinstance(raw, list):
            df = pd.DataFrame(raw).head(sample_rows)
        elif isinstance(raw, dict):
            if "rows" in raw and isinstance(raw["rows"], list):
                df = pd.DataFrame(raw["rows"]).head(sample_rows)
            else:
                df = pd.DataFrame([raw]).head(sample_rows)
        else:
            df = pd.DataFrame()

    cols = [str(c) for c in df.columns.tolist()]
    lc = {c.lower() for c in cols}

    kind = "tabular_unknown"
    if {"id", "structure"}.issubset(lc):
        kind = "dot_bracket_submission"
    elif {"x", "y", "z"}.issubset(lc):
        kind = "coordinate_rows"
    elif any(c.startswith("x_") for c in lc) and any(c.startswith("y_") for c in lc) and any(c.startswith("z_") for c in lc):
        kind = "flattened_coordinate_vectors"
    elif "contact_map" in lc or "distance_matrix" in lc:
        kind = "pairwise_matrix_like"

    id_col = None
    for c in cols:
        if c.lower() in {"id", "sequence_id", "target_id"}:
            id_col = c
            break

    unique_ids = int(df[id_col].nunique()) if id_col and id_col in df.columns else 0

    return {
        "path": str(path),
        "format": kind,
        "row_count_sampled": int(len(df)),
        "columns": cols,
        "id_column": id_col,
        "unique_ids_sampled": unique_ids,
        "viewer_ready": kind in {"coordinate_rows"},
        "normalization_route": "ingest_result" if kind in {"coordinate_rows", "flattened_coordinate_vectors", "dot_bracket_submission", "pairwise_matrix_like"} else "manual_adapter_needed",
        "created_at": _now(),
    }


def register_submission(
    notebook_ref: str,
    submission_path: Path,
    mark: str,
    breadcrumb: str,
    sequence: str,
    model: str,
    run_id: str,
    bridge_base: str = "http://127.0.0.1:19999",
) -> dict[str, Any]:
    prof = profile_submission(submission_path)

    ingested_pdb = ""
    viewer_url = ""
    if prof.get("format") in {"coordinate_rows", "flattened_coordinate_vectors"}:
        out_root = Path("artifacts/rna_predictions")
        rid = run_id or f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        out_pdb = out_root / rid / "prediction.pdb"
        ingest_result(input_path=submission_path, out_pdb=out_pdb, default_seq=sequence)
        ingested_pdb = str(out_pdb)
        viewer_url = f"{bridge_base.rstrip('/')}/{rid}/prediction.pdb"

        idx_path = out_root / "index.json"
        out_root.mkdir(parents=True, exist_ok=True)
        if idx_path.exists():
            idx = json.loads(idx_path.read_text())
        else:
            idx = {"predictions": []}
        preds = idx.get("predictions", [])
        if not isinstance(preds, list):
            preds = []
        preds.append(
            {
                "run_id": rid,
                "sequence": sequence or "unknown",
                "model": model or "unknown",
                "pdb_url": viewer_url,
                "created_at": _now(),
                "source": str(submission_path),
                "notebook_ref": notebook_ref,
            }
        )
        idx["predictions"] = preds
        idx_path.write_text(json.dumps(idx, indent=2))

    row = {
        "created_at": _now(),
        "notebook_ref": notebook_ref,
        "submission_path": str(submission_path),
        "profile": prof,
        "mark": mark,
        "breadcrumb": breadcrumb,
        "ingested_pdb": ingested_pdb,
        "viewer_url": viewer_url,
    }

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row


def list_registry(path: Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out
