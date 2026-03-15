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
READ_DATA_RE = re.compile(
    r"""(?:read_csv|read_parquet|read_json|read_feather|np\.load|loadtxt)\s*\(\s*["']([^"']+)["']""",
    re.I,
)
WRITE_DATA_RE = re.compile(
    r"""(?:to_csv|to_parquet|to_json|savez|savez_compressed|to_feather)\s*\(\s*["']([^"']+)["']""",
    re.I,
)


@dataclass
class NotebookDigest:
    ref: str
    title: str
    code_url: str
    pulled: bool
    local_path: str
    code_cells: int
    markdown_cells: int
    imports: list[str]
    techniques: list[str]
    datasets_read: list[str]
    artifacts_written: list[str]
    stage_hints: list[str]
    key_params: dict[str, Any]
    summary: str
    what_it_does: str
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


def _stage_hints(text: str, imports: list[str], techniques: list[str]) -> list[str]:
    hints: list[str] = []
    if "pandas" in imports or "polars" in imports:
        hints.append("data-loading")
    if any(t in techniques for t in ("msa", "pairwise", "confidence")):
        hints.append("feature-and-prior-construction")
    if any(t in techniques for t in ("protenix", "tbm", "diffusion")):
        hints.append("3d-structure-generation")
    if re.search(r"\b(train|fit|optimizer|loss)\b", text, flags=re.I):
        hints.append("model-training-or-finetuning")
    if re.search(r"\b(infer|predict|submission|lb|leaderboard)\b", text, flags=re.I):
        hints.append("inference-and-submission")
    if not hints:
        hints.append("manual-review-required")
    return hints


def _what_it_does(techniques: list[str], datasets_read: list[str], artifacts_written: list[str], stage_hints: list[str]) -> str:
    t = ", ".join(techniques[:5]) if techniques else "general notebook operations"
    dr = ", ".join(datasets_read[:3]) if datasets_read else "unknown inputs"
    aw = ", ".join(artifacts_written[:3]) if artifacts_written else "no explicit exports detected"
    st = " -> ".join(stage_hints[:4]) if stage_hints else "unspecified stages"
    return (
        f"Pipeline: {st}. "
        f"Likely techniques: {t}. "
        f"Reads: {dr}. "
        f"Writes: {aw}."
    )


def analyze_notebook(nb_path: Path) -> tuple[int, int, list[str], list[str], list[str], list[str], list[str], dict[str, Any], str, str]:
    raw = json.loads(nb_path.read_text(encoding="utf-8"))
    cells = raw.get("cells", []) if isinstance(raw, dict) else []
    src_parts: list[str] = []
    code_cells = 0
    markdown_cells = 0
    for c in cells:
        if not isinstance(c, dict):
            continue
        src = c.get("source", [])
        text_src = "".join(src) if isinstance(src, list) else str(src)
        if c.get("cell_type") == "code":
            code_cells += 1
            src_parts.append(text_src)
        elif c.get("cell_type") == "markdown":
            markdown_cells += 1
    text = "\n\n".join(src_parts)

    imports: list[str] = []
    for m in IMPORT_RE.finditer(text):
        mod = m.group(1) or m.group(2)
        if mod:
            imports.append(mod.split(".")[0])
    imports = sorted(set(imports))[:50]

    techniques = [k for k, pat in KEYWORDS.items() if re.search(pat, text, flags=re.I)]
    datasets_read = sorted(set(READ_DATA_RE.findall(text)))[:20]
    artifacts_written = sorted(set(WRITE_DATA_RE.findall(text)))[:20]
    stage_hints = _stage_hints(text=text, imports=imports, techniques=techniques)

    key_params: dict[str, Any] = {}
    for name in ["n_cycle", "recycle", "batch_size", "lr", "dropout", "model_name", "use_msa", "use_template"]:
        m = re.search(rf"{name}\s*=\s*([^\n#]+)", text)
        if m:
            key_params[name] = m.group(1).strip()[:120]

    summary = (
        f"Parsed {len(cells)} cells (code={code_cells}, markdown={markdown_cells}); "
        f"imports={len(imports)}; techniques={','.join(techniques) if techniques else 'none_detected'}; "
        f"datasets={len(datasets_read)}; outputs={len(artifacts_written)}"
    )
    what = _what_it_does(
        techniques=techniques,
        datasets_read=datasets_read,
        artifacts_written=artifacts_written,
        stage_hints=stage_hints,
    )
    return (
        code_cells,
        markdown_cells,
        imports,
        techniques,
        datasets_read,
        artifacts_written,
        stage_hints,
        key_params,
        summary,
        what,
    )


def fallback_summary(ref: str, title: str) -> NotebookDigest:
    return NotebookDigest(
        ref=ref,
        title=title,
        code_url=f"https://www.kaggle.com/code/{ref}",
        pulled=False,
        local_path="",
        code_cells=0,
        markdown_cells=0,
        imports=[],
        techniques=["manual_review_required"],
        datasets_read=[],
        artifacts_written=[],
        stage_hints=["manual-review-required"],
        key_params={},
        summary="Notebook pull failed (auth/network/availability). Kept reproducible stub.",
        what_it_does="Notebook source unavailable in this run; use reproduce command to pull code and rerun analysis.",
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
        (
            code_cells,
            markdown_cells,
            imports,
            techniques,
            datasets_read,
            artifacts_written,
            stage_hints,
            key_params,
            summary,
            what_it_does,
        ) = analyze_notebook(nb_path)
        digests.append(
            NotebookDigest(
                ref=ref,
                title=title,
                code_url=f"https://www.kaggle.com/code/{ref}",
                pulled=True,
                local_path=str(nb_path.relative_to(ROOT)),
                code_cells=code_cells,
                markdown_cells=markdown_cells,
                imports=imports,
                techniques=techniques,
                datasets_read=datasets_read,
                artifacts_written=artifacts_written,
                stage_hints=stage_hints,
                key_params=key_params,
                summary=summary,
                what_it_does=what_it_does,
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
                "stage_hints": d.stage_hints,
                "datasets_read": d.datasets_read,
                "artifacts_written": d.artifacts_written,
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
                f"- code_url: `{d.code_url}`",
                f"- cells: code={d.code_cells}, markdown={d.markdown_cells}",
                f"- techniques: `{', '.join(d.techniques)}`",
                f"- datasets_read: `{', '.join(d.datasets_read[:8])}`",
                f"- artifacts_written: `{', '.join(d.artifacts_written[:8])}`",
                f"- stage_hints: `{', '.join(d.stage_hints)}`",
                f"- key_params: `{json.dumps(d.key_params)}`",
                f"- summary: {d.summary}",
                f"- what_it_does: {d.what_it_does}",
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
