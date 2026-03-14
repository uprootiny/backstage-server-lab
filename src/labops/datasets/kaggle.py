from __future__ import annotations

from pathlib import Path

import orjson
from kaggle.api.kaggle_api_extended import KaggleApi


def sync_kaggle(out: Path, search: str = "", limit: int = 50) -> Path:
    api = KaggleApi()
    api.authenticate()

    competitions = api.competitions_list(search=search)[:limit]
    datasets = api.dataset_list(search=search)[:limit]

    payload = {
        "competitions": [
            {
                "ref": getattr(c, "ref", ""),
                "title": getattr(c, "title", ""),
                "reward": getattr(c, "reward", ""),
                "deadline": str(getattr(c, "deadline", "")),
            }
            for c in competitions
        ],
        "datasets": [
            {
                "ref": getattr(d, "ref", ""),
                "title": getattr(d, "title", ""),
                "size": getattr(d, "totalBytes", 0),
                "updated": str(getattr(d, "lastUpdated", "")),
            }
            for d in datasets
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
    return out
