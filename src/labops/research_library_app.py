from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

PAPER_CARDS = Path("docs/PAPER_PROJECT_CARDS.md")
RNA_SUMMARIES = Path("docs/RNA_RESEARCH_SUMMARIES.md")
TECHNIQUES = Path("catalogue/techniques/rna_notebook_techniques.yaml")
CATALOGUE = Path("data/seeds/kaggle_rna_seed_catalogue.json")
README_ACTUAL = Path("README.ACTUAL.md")
RUNBOOK = Path("docs/MEANINGFUL_RESULTS_RUNBOOK.md")
WALKTHROUGH = Path("docs/FOOLPROOF_WALKTHROUGH.md")
COHERENCE = Path("docs/INTEGRATION_COHERENCE_CHECKS.md")
PARALLEL_LEDGER = Path("artifacts/kaggle_parallel/ledger.jsonl")
EXECUTED_DIR = Path("artifacts/kaggle_parallel/executed")


def _read(path: Path) -> str:
    if not path.exists():
        return f"Missing: {path}"
    return path.read_text(encoding="utf-8")


def _load_catalogue() -> list[dict[str, Any]]:
    if not CATALOGUE.exists():
        return []
    raw = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    items = raw.get("items", [])
    return items if isinstance(items, list) else []


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_run_health() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if PARALLEL_LEDGER.exists():
        for line in PARALLEL_LEDGER.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
                if isinstance(row, dict):
                    rows.append(row)
            except Exception:
                continue

    run_end = [r for r in rows if r.get("event") == "run_end"]
    job_end = [r for r in rows if r.get("event") == "job_end"]
    ok = sum(1 for r in job_end if r.get("status") == "ok")
    failed = len(job_end) - ok

    by_notebook: dict[str, dict[str, int]] = {}
    for r in job_end:
        nb = str(r.get("notebook") or r.get("job_id") or "unknown")
        bucket = by_notebook.setdefault(nb, {"ok": 0, "failed": 0})
        if r.get("status") == "ok":
            bucket["ok"] += 1
        else:
            bucket["failed"] += 1

    notebooks = [
        {"notebook": k, "ok": v["ok"], "failed": v["failed"], "total": v["ok"] + v["failed"]}
        for k, v in by_notebook.items()
    ]
    notebooks.sort(key=lambda x: (-x["total"], x["notebook"]))

    executed = sorted(str(p) for p in EXECUTED_DIR.glob("*.ipynb")) if EXECUTED_DIR.exists() else []
    latest = run_end[-1] if run_end else None
    return {
        "ledger_rows": len(rows),
        "run_end_count": len(run_end),
        "job_end_count": len(job_end),
        "ok": ok,
        "failed": failed,
        "latest_run_end": latest,
        "notebooks": notebooks,
        "executed_notebooks": executed,
    }


def _notebook_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    jobs = [r for r in rows if r.get("event") == "job_end"]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in jobs:
        nb = str(r.get("notebook") or r.get("job_id") or "unknown")
        grouped.setdefault(nb, []).append(r)
    out: list[dict[str, Any]] = []
    for nb, rs in grouped.items():
        total = len(rs)
        ok = sum(1 for r in rs if r.get("status") == "ok")
        failed = total - ok
        sr = (ok / total) if total else 0.0
        secs = [float(r.get("seconds", 0) or 0) for r in rs if isinstance(r.get("seconds", 0), (int, float))]
        mean_sec = (sum(secs) / len(secs)) if secs else 0.0
        score = 100.0 * sr - 0.12 * mean_sec - 6.0 * failed
        priority = (1.0 - sr) * 0.65 + min(1.0, mean_sec / 300.0) * 0.2 + (1 if failed > ok else 0) * 0.15
        out.append(
            {
                "notebook": nb,
                "total": total,
                "ok": ok,
                "failed": failed,
                "success_rate": round(sr, 3),
                "mean_seconds": round(mean_sec, 2),
                "score": round(score, 2),
                "rerun_priority": round(priority, 3),
            }
        )
    out.sort(key=lambda r: (-r["rerun_priority"], r["score"]))
    return out


def _extract_shell_commands(markdown_text: str) -> list[str]:
    """
    Extract shell-like commands from markdown code blocks and standalone lines.

    Supports fenced blocks (```bash/sh) and plain lines that start with common
    command prefixes.
    """
    commands: list[str] = []
    seen: set[str] = set()

    fenced = re.findall(r"```(?:bash|sh)?\n(.*?)```", markdown_text, flags=re.DOTALL | re.IGNORECASE)
    prefixes = (
        "bash ",
        "make ",
        "python ",
        "python3 ",
        "labops ",
        "AUTO_HEAL=",
        "WORKERS=",
        "TOP_N=",
        "cd ",
    )

    def _push(cmd: str) -> None:
        c = cmd.strip()
        if not c or c.startswith("#"):
            return
        if c not in seen:
            seen.add(c)
            commands.append(c)

    for block in fenced:
        for line in block.splitlines():
            line = line.strip()
            if line.startswith(prefixes):
                _push(line)

    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefixes):
            _push(stripped)

    return commands


def _run_shell(cmd: str, cwd: Path = Path("."), timeout_sec: int = 180) -> dict[str, Any]:
    """
    Execute one shell command via `bash -lc` and capture output.
    """
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _make_hypothesis_brief(question: str, focus: str, constraints: str) -> str:
    return (
        f"Question: {question}\n"
        f"Focus: {focus}\n"
        f"Constraints: {constraints or 'none specified'}\n\n"
        "Hypothesis Draft:\n"
        "- If we increase representation fidelity at the pairwise/geometry stage,\n"
        "  then tertiary-contact consistency should improve on held-out motifs.\n\n"
        "Test Plan:\n"
        "1. Run baseline stack on family-dropout split.\n"
        "2. Add one recombined trick bundle.\n"
        "3. Compare TM/lDDT + motif error tags.\n"
        "4. Rank next actions by VOI/cost.\n"
    )


def _make_method_recombo(goal: str, budget: str) -> str:
    return (
        f"Goal: {goal}\n"
        f"Budget: {budget}\n\n"
        "Suggested Recombination:\n"
        "- 2D prior: UFold-style contact prior\n"
        "- 3D head: geometry + recycling refinement\n"
        "- Fallback: TBM + de-novo fill\n"
        "- Selection: confidence-weighted ensemble\n"
        "- Eval: family + motif dropout\n"
    )


def main() -> None:
    st.set_page_config(page_title="RNA Research Library", layout="wide")
    st.title("RNA Research Library")
    st.caption("Digests + project cards + AI-assisted method tooling.")

    tab_digest, tab_cards, tab_tools, tab_catalogue = st.tabs(
        ["Research Digests", "Project Cards", "AI Tools", "Library Catalogue"]
    )

    with tab_digest:
        st.subheader("RNA Research Summaries")
        st.markdown(_read(RNA_SUMMARIES))

    with tab_cards:
        st.subheader("Paper Project Cards")
        st.markdown(_read(PAPER_CARDS))

    with tab_tools:
        st.subheader("AI-Assisted Research Tools")
        st.caption("Template-based helpers for rapid planning and method recombination.")

        with st.expander("Run Health (ledger truth)", expanded=True):
            health = _load_run_health()
            rows = []
            if PARALLEL_LEDGER.exists():
                for line in PARALLEL_LEDGER.read_text(encoding="utf-8").splitlines():
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        j = json.loads(s)
                        if isinstance(j, dict):
                            rows.append(j)
                    except Exception:
                        pass
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("run_end", health["run_end_count"])
            c2.metric("job_end", health["job_end_count"])
            c3.metric("ok", health["ok"])
            c4.metric("failed", health["failed"])
            if health["latest_run_end"]:
                st.caption(f"latest run_end: `{health['latest_run_end'].get('run_id','')}`")
                st.json(health["latest_run_end"])
            else:
                st.info("No run_end events in ledger yet.")

            if health["notebooks"]:
                st.markdown("**Notebook status summary**")
                st.dataframe(health["notebooks"][:30], use_container_width=True, height=220)
            scores = _notebook_scores(rows)
            if scores:
                st.markdown("**Notebook score context (ledger-linked)**")
                st.dataframe(scores[:30], use_container_width=True, height=220)

            if health["executed_notebooks"]:
                st.markdown("**Executed notebooks present**")
                ex_rows = []
                for p in health["executed_notebooks"][:30]:
                    path = str(p).strip().lstrip("./")
                    ex_rows.append(
                        {
                            "path": path,
                            "open_in_jupyter": f"https://175.155.64.231:19808/lab/tree/{path}",
                            "open_run_fabric": "http://175.155.64.231:19448",
                        }
                    )
                st.dataframe(
                    ex_rows,
                    use_container_width=True,
                    height=220,
                    column_config={
                        "open_in_jupyter": st.column_config.LinkColumn("Open notebook"),
                        "open_run_fabric": st.column_config.LinkColumn("Run Fabric"),
                    },
                )
            else:
                st.warning("No executed notebooks found in artifacts/kaggle_parallel/executed.")

        with st.expander("Hypothesis Brief Composer", expanded=True):
            q = st.text_input("Research question", value="How can we improve tertiary motif generalization?")
            f = st.text_input("Primary focus", value="pairwise geometry and refinement")
            c = st.text_input("Constraints", value="single 32GB GPU, 6h budget")
            if st.button("Generate Hypothesis Brief"):
                st.code(_make_hypothesis_brief(q, f, c), language="text")

        with st.expander("Method Recombination Assistant", expanded=False):
            g = st.text_input("Goal", value="Increase stability on long RNA targets")
            b = st.text_input("Compute budget", value="moderate")
            if st.button("Suggest Recombination"):
                st.code(_make_method_recombo(g, b), language="text")

        with st.expander("Experiment Card Writer", expanded=False):
            name = st.text_input("Experiment name", value="exp_recycle_6_layers_8")
            metric = st.text_input("Primary metric", value="tm_score")
            split = st.text_input("Validation split", value="family_dropout_v1")
            if st.button("Create Experiment Card"):
                card = {
                    "experiment": name,
                    "metric": metric,
                    "validation_spec": split,
                    "created_at": _now(),
                    "checklist": [
                        "manifest recorded",
                        "artifacts indexed",
                        "compare-2 generated",
                        "voi decision logged",
                    ],
                }
                st.json(card)

        with st.expander("Executable Command Console", expanded=True):
            st.caption("Click to run commands extracted from operational docs. Runs on the current host.")
            src_map = {
                "README actual": README_ACTUAL,
                "Runbook": RUNBOOK,
                "Walkthrough": WALKTHROUGH,
                "Coherence report": COHERENCE,
            }
            source_name = st.selectbox("Command source", list(src_map.keys()), index=0)
            source_path = src_map[source_name]
            source_text = _read(source_path)
            cmds = _extract_shell_commands(source_text)

            if not cmds:
                st.info(f"No shell commands found in {source_path}")
            else:
                st.write(f"Commands discovered: {len(cmds)}")
                max_show = st.slider("Show first N commands", min_value=3, max_value=min(40, len(cmds)), value=min(12, len(cmds)))
                for i, cmd in enumerate(cmds[:max_show]):
                    c1, c2 = st.columns([8, 1])
                    c1.code(cmd, language="bash")
                    if c2.button("Run", key=f"run_cmd_{source_name}_{i}"):
                        with st.spinner(f"Running: {cmd}"):
                            try:
                                result = _run_shell(cmd, cwd=Path("."), timeout_sec=240)
                            except subprocess.TimeoutExpired:
                                result = {"cmd": cmd, "returncode": 124, "stdout": "", "stderr": "timeout expired"}
                        st.session_state["last_cmd_result"] = result

                if "last_cmd_result" in st.session_state:
                    r = st.session_state["last_cmd_result"]
                    st.markdown(f"**Last command:** `{r['cmd']}`")
                    st.markdown(f"**Exit code:** `{r['returncode']}`")
                    if r["stdout"]:
                        st.text_area("stdout", r["stdout"], height=180)
                    if r["stderr"]:
                        st.text_area("stderr", r["stderr"], height=140)

    with tab_catalogue:
        st.subheader("Curated Research Library")
        items = _load_catalogue()
        if not items:
            st.info("No seeded catalogue items found.")
        else:
            st.write(f"Items: {len(items)}")
            for row in items:
                if isinstance(row, dict):
                    u = str(row.get("url", "")).strip()
                    if u:
                        row["open"] = u
            st.dataframe(
                items,
                use_container_width=True,
                height=480,
                column_config={
                    "open": st.column_config.LinkColumn("Open link"),
                    "url": st.column_config.LinkColumn("URL"),
                },
            )

            if items:
                titles = [str(r.get("title", r.get("ref", "item"))) for r in items if isinstance(r, dict)]
                selected = st.selectbox("Inspect item", options=titles, index=0)
                picked = next((r for r in items if str(r.get("title", r.get("ref", "item"))) == selected), None)
                if isinstance(picked, dict):
                    st.json(picked)
                    url = str(picked.get("url", "")).strip()
                    if url:
                        st.link_button("Open selected source", url, use_container_width=False)

    st.caption(f"Updated: {_now()}")


if __name__ == "__main__":
    main()
