from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx
import orjson


def export_graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], out: Path) -> None:
    g = nx.DiGraph()
    for n in nodes:
        nid = n["id"]
        attrs = {k: v for k, v in n.items() if k != "id"}
        g.add_node(nid, **attrs)
    for e in edges:
        src = e["source"]
        dst = e["target"]
        attrs = {k: v for k, v in e.items() if k not in {"source", "target"}}
        g.add_edge(src, dst, **attrs)

    payload = {
        "nodes": [{"id": n, **attrs} for n, attrs in g.nodes(data=True)],
        "edges": [{"source": u, "target": v, **attrs} for u, v, attrs in g.edges(data=True)],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))
