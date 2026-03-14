from __future__ import annotations

from pathlib import Path
import hashlib


def semantic_cache_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


def cache_path(root: Path, key: str, ext: str = "json") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{key}.{ext}"
