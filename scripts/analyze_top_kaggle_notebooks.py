#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIST = ROOT / "catalogue/top_kaggle_notebooks.yaml"
OUT_JSON = ROOT / "artifacts/top_notebook_analysis.json"
OUT_MD = ROOT / "docs/TOP_NOTEBOOK_DIGEST.md"
OUT_RECIPES = ROOT / "artifacts/top_notebook_recipes.yaml"
WORK_DIR = ROOT / "tmp/kaggle_top_notebooks"


KEYWORDS = {
    "tbm": r"\btbm\b|template",
    "protenix": r"protenix",
    "recycling": r"recycl|n_cycle|cycle",
    "ensemble": r"ensemble|blend|average",
    "confidence": r"confidence|lddt|pae|calibr",
    "pairwise": r"pairwise|distogram|contact",
    "diffusion": r"diffusion|denois",
    "msa": r"\bmsa\b|hmm|hmmer|kalign",
    "fallback": r"fallback|denovo|de-novo",
}

IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))", re.M)


@dataclass
class NotebookDigest:
    ref: str
    title: str
    pulled: bool
    local_path: str
    imports: list[str]
    techniques: list[str]
    key_params: dict[str, Any]
    summary: str
    repro_cmd: str


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def try_pull(ref: str, out_dir: Path) -> tuple[bool, Path | None, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    # prefer kaggle CLI if available/authenticated
    if shutil.which("kaggle"):
      rc, out = run(["kaggle", "kernels", "pull", ref, "-p", str(out_dir), "--metadata"])
      if rc == 0:
          nb = out_dir / f"{ref.split('/')[-1]}.ipynb"
          if nb.exists():
              return True, nb, out
      return False, None, out
    return False, None, "kaggle_cli_missing"


def analyze_notebook(nb_path: Path) -> tuple[list[str], list[str], dict[str, Any], str]:
    raw = json.loads(nb_path.read_text(encoding="utf-8"))
    cells = raw.get("cells", []) if isinstance(raw, dict) else []
    src_parts: list[str] = []
    for c in cells:
        if not isinstance(c, dict):
            continue
        if c.get("cell_type") != "code":
            continue
        src = c.get("source", [])
        if isinstance(src, list):
            src_parts.append("".join(src))
        elif isinstance(src, str):
            src_parts.append(src)
    text = "\n\n".join(src_parts)

    imports: list[str] = []
    for m in IMPORT_RE.finditer(text):
        mod = m.group(1) or m.group(2)
        if mod:
            imports.append(mod.split(".")[0])
    imports = sorted(set(imports))[:50]

    techniques = [k for k, pat in KEYWORDS.items() if re.search(pat, text, flags=re.I)]

    key_params: dict[str, Any] = {}
    for name in ["n_cycle", "recycle", "batch_size", "lr", "dropout", "model_name", "use_msa", "use_template"]:
        m = re.search(rf"{name}\s*=\s*([^\n#]+)", text)
        if m:
            key_params[name] = m.group(1).strip()[:120]

    summary = (
        f"Parsed {len(cells)} cells; detected imports={len(imports)}, "
        f"techniques={','.join(techniques) if techniques else 'none_detected'}"
    )
    return imports, techniques, key_params, summary


def fallback_summary(ref: str, title: str) -> NotebookDigest:
    return NotebookDigest(
        ref=ref,
        title=title,
        pulled=False,
        local_path="",
        imports=[],
        techniques=["manual_review_required"],
        key_params={},
        summary="Notebook pull failed (auth/network/availability). Kept reproducible stub.",
        repro_cmd=f"kaggle kernels pull {ref} -p tmp/kaggle_top_notebooks --metadata",
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze top Kaggle notebooks end-to-end")
    ap.add_argument("--list", default=str(DEFAULT_LIST))
    args = ap.parse_args()

    listed = yaml.safe_load(Path(args.list).read_text())
    rows = listed.get("notebooks", []) if isinstance(listed, dict) else []

    digests: list[NotebookDigest] = []
    for row in rows:
        ref = str(row.get("ref", "")).strip()
        title = str(row.get("title", ref))
        if not ref:
            continue
        safe_dir = WORK_DIR / ref.replace("/", "__")
        ok, nb_path, _log = try_pull(ref, safe_dir)
        if not ok or nb_path is None:
            digests.append(fallback_summary(ref, title))
            continue
        imports, techniques, key_params, summary = analyze_notebook(nb_path)
        digests.append(
            NotebookDigest(
                ref=ref,
                title=title,
                pulled=True,
                local_path=str(nb_path.relative_to(ROOT)),
                imports=imports,
                techniques=techniques,
                key_params=key_params,
                summary=summary,
                repro_cmd=f"kaggle kernels pull {ref} -p tmp/kaggle_top_notebooks --metadata",
            )
        )

    payload = {
        "generated_at": now(),
        "count": len(digests),
        "digests": [d.__dict__ for d in digests],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    recipes = {
        "generated_at": now(),
        "recipes": [
            {
                "id": d.ref.replace("/", "_"),
                "notebook_ref": d.ref,
                "repro_steps": [
                    d.repro_cmd,
                    f"PYTHONPATH=src .venv/bin/python -m labops.cli kaggle-parallel-dispatch --plan artifacts/kaggle_parallel/plan.json --workers 3",
                ],
                "detected_techniques": d.techniques,
                "detected_params": d.key_params,
            }
            for d in digests
        ],
    }
    OUT_RECIPES.write_text(yaml.safe_dump(recipes, sort_keys=False), encoding="utf-8")

    lines = [
        "# Top Kaggle Notebook Digest",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- notebooks: {payload['count']}",
        "",
        "## Through-and-through recap",
        "",
    ]
    for d in digests:
        lines.extend(
            [
                f"### {d.title}",
                f"- ref: `{d.ref}`",
                f"- pulled: `{d.pulled}`",
                f"- local_path: `{d.local_path}`" if d.local_path else "- local_path: `(not available)`",
                f"- techniques: `{', '.join(d.techniques)}`",
                f"- key_params: `{json.dumps(d.key_params)}`",
                f"- summary: {d.summary}",
                f"- reproduce: `{d.repro_cmd}`",
                "",
            ]
        )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_RECIPES}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
