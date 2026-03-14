from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

PAPER_CARDS = Path("docs/PAPER_PROJECT_CARDS.md")
RNA_SUMMARIES = Path("docs/RNA_RESEARCH_SUMMARIES.md")
TECHNIQUES = Path("catalogue/techniques/rna_notebook_techniques.yaml")
CATALOGUE = Path("data/seeds/kaggle_rna_seed_catalogue.json")


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

    with tab_catalogue:
        st.subheader("Curated Research Library")
        items = _load_catalogue()
        if not items:
            st.info("No seeded catalogue items found.")
        else:
            st.write(f"Items: {len(items)}")
            st.dataframe(items, use_container_width=True, height=480)

    st.caption(f"Updated: {_now()}")


if __name__ == "__main__":
    main()
