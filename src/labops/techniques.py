from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_TECHNIQUE_FILE = Path("catalogue/techniques/rna_notebook_techniques.yaml")


def load_techniques(path: Path = DEFAULT_TECHNIQUE_FILE) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text()) if path.exists() else {}
    items = raw.get("techniques", []) if isinstance(raw, dict) else []
    return [dict(x) for x in items if isinstance(x, dict)]


def compose_techniques(
    selected_ids: list[str],
    all_techniques: list[dict[str, Any]],
    hypothesis: str,
    dataset: str,
    out: Path,
) -> Path:
    idx = {str(t.get("id", "")): t for t in all_techniques}
    picked = [idx[i] for i in selected_ids if i in idx]
    if not picked:
        raise ValueError("no matching techniques selected")

    knobs: list[str] = []
    stages: list[str] = []
    sources: list[str] = []
    for t in picked:
        stages.append(str(t.get("stage", "unknown")))
        for k in t.get("knobs", []) or []:
            if isinstance(k, str) and k not in knobs:
                knobs.append(k)
        src = str(t.get("source", ""))
        if src and src not in sources:
            sources.append(src)

    payload = {
        "composition_id": f"compose-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": hypothesis,
        "dataset": dataset,
        "selected_techniques": selected_ids,
        "stages": stages,
        "knobs": knobs,
        "sources": sources,
        "techniques": picked,
        "suggested_experiment": {
            "name": "composed-rna-experiment",
            "hypothesis": hypothesis,
            "dataset": dataset,
            "variants": [
                {"lr": 0.0001, "batch_size": 16},
                {"lr": 0.0003, "batch_size": 32},
                {"lr": 0.0010, "batch_size": 64},
            ],
            "metrics": ["score", "rmsd", "contact_f1"],
            "validation": "family_dropout_validation",
            "composition_ref": None,
        },
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(payload, sort_keys=False))

    exp = payload["suggested_experiment"]
    exp["composition_ref"] = str(out)
    exp_path = out.parent / "composed_experiment.yaml"
    exp_path.write_text(yaml.safe_dump(exp, sort_keys=False))
    return out
