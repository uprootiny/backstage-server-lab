from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json


@dataclass
class RunManifest:
    run_id: str
    experiment_id: str
    repo_rev: str
    dataset_ref: str
    model_ref: str
    validation_spec: str
    status: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=True)


def write_manifest(path: Path, manifest: RunManifest) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(manifest)
    payload["ts"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
