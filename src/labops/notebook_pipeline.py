from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


@dataclass
class NotebookPipeline:
    notebook: str
    title: str
    code_cells: int
    markdown_cells: int
    stages: list[str]
    imports: list[str]
    functions: list[str]
    artifacts: list[str]
    inferred_steps: list[dict[str, Any]]


IMPORT_RE = re.compile(r"^\s*(?:from\s+([a-zA-Z0-9_\.]+)\s+import|import\s+([a-zA-Z0-9_\.]+))")
FUNC_RE = re.compile(r"^\s*def\s+([a-zA-Z0-9_]+)\s*\(")
ARTIFACT_RE = re.compile(r"([A-Za-z0-9_\-./]+?\.(?:csv|json|npz|npy|pdb|parquet|md|png|html|ipynb))")
H2_RE = re.compile(r"^\s*##+\s+(.+?)\s*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_nb(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _cell_source(cell: dict[str, Any]) -> str:
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return str(src)


def analyze_notebook(path: Path) -> NotebookPipeline:
    nb = _read_nb(path)
    cells = nb.get("cells", [])
    code_cells = 0
    markdown_cells = 0
    stages: list[str] = []
    imports: set[str] = set()
    funcs: set[str] = set()
    artifacts: set[str] = set()
    title = path.stem

    for c in cells:
        ctype = c.get("cell_type", "")
        text = _cell_source(c)
        if ctype == "markdown":
            markdown_cells += 1
            lines = text.splitlines()
            if lines and lines[0].startswith("# "):
                title = lines[0].lstrip("# ").strip()
            for line in lines:
                m = H2_RE.match(line)
                if m:
                    stages.append(m.group(1).strip())
        elif ctype == "code":
            code_cells += 1
            for line in text.splitlines():
                im = IMPORT_RE.match(line)
                if im:
                    imports.add((im.group(1) or im.group(2) or "").split(".")[0])
                fm = FUNC_RE.match(line)
                if fm:
                    funcs.add(fm.group(1))
            for m in ARTIFACT_RE.findall(text):
                artifacts.add(m)

    inferred_steps: list[dict[str, Any]] = []
    if stages:
        for i, s in enumerate(stages, start=1):
            inferred_steps.append({"id": f"step-{i:02d}", "name": s, "kind": "notebook_stage"})
    else:
        inferred_steps = [
            {"id": "step-01", "name": "execute_notebook", "kind": "notebook_stage"},
            {"id": "step-02", "name": "collect_artifacts", "kind": "artifact_stage"},
        ]

    return NotebookPipeline(
        notebook=str(path),
        title=title,
        code_cells=code_cells,
        markdown_cells=markdown_cells,
        stages=stages,
        imports=sorted(x for x in imports if x),
        functions=sorted(funcs),
        artifacts=sorted(artifacts),
        inferred_steps=inferred_steps,
    )


def materialize_pipeline(path: Path, out_root: Path) -> dict[str, Path]:
    info = analyze_notebook(path)
    slug = path.stem
    out_dir = out_root / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at": _now(),
        "kind": "notebook_pipeline_manifest",
        "pipeline": info.__dict__,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    pipeline_yaml = {
        "name": f"pipeline-{slug}",
        "source_notebook": str(path),
        "stages": info.inferred_steps,
        "artifacts": info.artifacts,
        "execution": {
            "engine": "nbconvert",
            "cmd": f"python -m nbconvert --to notebook --execute {path} --output {slug}.executed.ipynb --output-dir {out_dir}",
        },
    }
    pipeline_path = out_dir / "pipeline.yaml"
    pipeline_path.write_text(yaml.safe_dump(pipeline_yaml, sort_keys=False), encoding="utf-8")

    run_sh = out_dir / "run.sh"
    run_sh.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "ROOT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")/../..\" && pwd)\"",
                "cd \"$ROOT_DIR\"",
                f"PYTHONPATH=src python -m nbconvert --to notebook --execute {path} --output {slug}.executed.ipynb --output-dir {out_dir}",
                f"echo \"pipeline_executed {slug}\"",
                f"echo \"manifest={manifest_path}\"",
                f"echo \"pipeline={pipeline_path}\"",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_sh.chmod(0o755)

    return {"manifest": manifest_path, "pipeline": pipeline_path, "run_sh": run_sh}

