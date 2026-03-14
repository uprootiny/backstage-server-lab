from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

import orjson
from kaggle.api.kaggle_api_extended import KaggleApi


SEED_ROWS = Path("data/seeds/kaggle_rna_seed_rows.json")

TAG_RULES: list[tuple[str, list[str]]] = [
    ("template_based_modeling", ["template", "tbm", "protenix"]),
    ("ensemble_methods", ["ensemble", "blend", "stack", "mixture"]),
    ("eda_exploration", ["eda", "exploration", "distribution", "analysis"]),
    ("loss_engineering", ["loss", "objective", "metric learning"]),
    ("confidence_calibration", ["confidence", "plddt", "b-factor", "uncertainty"]),
    ("geometry_head", ["3d", "structure", "coords", "coordinate", "distance"]),
    ("submission_optimization", ["submission", "lb", "leaderboard", "stable"]),
    ("augmentation", ["augment", "noise", "perturb"]),
    ("single_cell_adjacent", ["single-cell", "scrna", "rna-seq"]),
]


def _fetch_notebooks(search: str, limit: int) -> list[dict[str, Any]]:
    api = KaggleApi()
    api.authenticate()
    rows = list(api.kernels_list(search=search))[:limit]
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "ref": str(getattr(r, "ref", "")),
                "title": str(getattr(r, "title", "")),
                "author": str(getattr(r, "author", "")),
                "votes": int(getattr(r, "totalVotes", 0) or 0),
                "last_run": str(getattr(r, "lastRunTime", "")),
                "url": f"https://www.kaggle.com/code/{getattr(r, 'ref', '')}",
            }
        )
    return out


def _seed_notebooks(limit: int) -> list[dict[str, Any]]:
    if not SEED_ROWS.exists():
        return []
    raw = json.loads(SEED_ROWS.read_text())
    rows = raw.get("rows", [])
    out = []
    for r in rows:
        if r.get("kind") != "notebook":
            continue
        out.append(
            {
                "ref": str(r.get("ref", "")),
                "title": str(r.get("title", "")),
                "author": "seed",
                "votes": int(r.get("score", 0) or 0),
                "last_run": str(r.get("updated", "")),
                "url": str(r.get("url", "")),
            }
        )
    return out[:limit]


def _tags_for(title: str) -> list[str]:
    t = title.lower()
    tags = []
    for tag, words in TAG_RULES:
        if any(w in t for w in words):
            tags.append(tag)
    if not tags:
        tags.append("general_rna_pipeline")
    return tags


def build_notebook_minimap(search: str, limit: int, out_json: Path, out_md: Path) -> tuple[Path, Path]:
    try:
        notebooks = _fetch_notebooks(search=search, limit=limit)
        source = "kaggle_api"
    except Exception:
        notebooks = _seed_notebooks(limit=limit)
        source = "seed_rows"

    enriched: list[dict[str, Any]] = []
    tag_counter: Counter[str] = Counter()
    trick_examples: dict[str, list[str]] = defaultdict(list)

    for nb in notebooks:
        title = nb.get("title", "")
        tags = _tags_for(title)
        tag_counter.update(tags)
        for tag in tags:
            if len(trick_examples[tag]) < 5:
                trick_examples[tag].append(title)
        enriched.append({**nb, "tags": tags})

    known_tricks = [
        {
            "id": "template_plus_refinement",
            "concept": "Use template retrieval for coarse fold and iterative refinement for local geometry",
            "arrangement": ["template_based_modeling", "geometry_head", "submission_optimization"],
        },
        {
            "id": "ensemble_then_calibrate",
            "concept": "Blend diverse runs, then calibrate residue confidence",
            "arrangement": ["ensemble_methods", "confidence_calibration", "submission_optimization"],
        },
        {
            "id": "eda_to_loss_loop",
            "concept": "Use EDA to isolate hard motifs and redesign loss around them",
            "arrangement": ["eda_exploration", "loss_engineering", "geometry_head"],
        },
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "search": search,
        "limit": limit,
        "source": source,
        "count": len(enriched),
        "tag_distribution": dict(tag_counter.most_common()),
        "algorithmic_minimap": [
            {
                "tag": tag,
                "count": count,
                "examples": trick_examples[tag],
                "summary": f"{tag.replace('_', ' ')} appears in {count} notebooks",
            }
            for tag, count in tag_counter.most_common()
        ],
        "known_tricks": known_tricks,
        "notebooks": enriched,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))

    lines = [
        "# Kaggle RNA Notebook Mass Study",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- source: {source}",
        f"- notebook_count: {len(enriched)}",
        "",
        "## Technique Distribution",
        "",
        "| Tag | Count |",
        "|---|---|",
    ]
    for tag, count in tag_counter.most_common():
        lines.append(f"| {tag} | {count} |")

    lines += ["", "## Algorithmic Minimap", ""]
    for item in payload["algorithmic_minimap"]:
        lines.append(f"- **{item['tag']}** ({item['count']}): {item['summary']}")
        for ex in item["examples"][:3]:
            lines.append(f"  - {ex}")

    lines += ["", "## Known Trick Arrangements", ""]
    for trick in known_tricks:
        lines.append(f"- **{trick['id']}**: {trick['concept']}")
        lines.append(f"  - arrangement: {', '.join(trick['arrangement'])}")

    out_md.write_text("\n".join(lines) + "\n")
    return out_json, out_md
