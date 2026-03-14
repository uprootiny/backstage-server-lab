from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Experiment:
    name: str
    hypothesis: str
    dataset: str
    variants: list[dict[str, Any]]
    metrics: list[str]
    results_dir: Path


def load_experiment(path: Path) -> Experiment:
    raw = yaml.safe_load(path.read_text())
    return Experiment(
        name=str(raw.get("name", path.stem)),
        hypothesis=str(raw.get("hypothesis", "")),
        dataset=str(raw.get("dataset", "unknown")),
        variants=list(raw.get("variants", [])),
        metrics=list(raw.get("metrics", ["score"])),
        results_dir=Path(raw.get("results_dir", f"results/{path.stem}")),
    )
