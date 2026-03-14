from __future__ import annotations

from dataclasses import dataclass, asdict
import json


@dataclass
class ProvenanceRecord:
    source: str
    code_rev: str
    dataset_hash: str
    config_hash: str


def to_json(rec: ProvenanceRecord) -> str:
    return json.dumps(asdict(rec), ensure_ascii=True)
