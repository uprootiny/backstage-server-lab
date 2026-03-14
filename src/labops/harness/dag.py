from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class Node:
    name: str
    transform: Callable[..., Any]
    inputs: list[str]
    outputs: list[str]


@dataclass
class PipelineDAG:
    nodes: list[Node]

    def list_nodes(self) -> list[str]:
        return [n.name for n in self.nodes]
