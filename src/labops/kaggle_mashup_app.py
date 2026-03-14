from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from kaggle.api.kaggle_api_extended import KaggleApi

CACHE_PATH = Path("artifacts/kaggle_mashup_cache.parquet")
CATALOGUE_PATH = Path("artifacts/kaggle_catalogue.json")
STARTER_INDEX_PATH = Path("notebooks/starters/index.json")
SEED_ROWS_PATH = Path("data/seeds/kaggle_rna_seed_rows.json")
SEED_CATALOGUE_PATH = Path("data/seeds/kaggle_rna_seed_catalogue.json")


@dataclass
class Row:
    kind: str
    ref: str
    title: str
    subtitle: str
    score: float
    updated: str
    url: str


def _safe_len(v: Any) -> int:
    try:
        return len(v)
    except Exception:
        return 0


def fetch_live(limit: int = 50, search: str = "") -> pd.DataFrame:
    api = KaggleApi()
    api.authenticate()

    rows: list[Row] = []

    competitions = api.competitions_list(search=search)
    for c in competitions[:limit]:
        rows.append(
            Row(
                kind="competition",
                ref=getattr(c, "ref", ""),
                title=getattr(c, "title", ""),
                subtitle=getattr(c, "category", ""),
                score=float(getattr(c, "reward", 0) or 0),
                updated=str(getattr(c, "deadline", "")),
                url=f"https://www.kaggle.com/competitions/{getattr(c, 'ref', '')}",
            )
        )

    datasets = api.dataset_list(search=search)
    for d in datasets[:limit]:
        rows.append(
            Row(
                kind="dataset",
                ref=getattr(d, "ref", ""),
                title=getattr(d, "title", ""),
                subtitle=getattr(d, "licenseName", ""),
                score=float(getattr(d, "totalBytes", 0) or 0),
                updated=str(getattr(d, "lastUpdated", "")),
                url=f"https://www.kaggle.com/datasets/{getattr(d, 'ref', '')}",
            )
        )

    df = pd.DataFrame([asdict(r) for r in rows])
    return df


def load_or_fetch(limit: int, search: str, force_live: bool) -> pd.DataFrame:
    if force_live:
        df = fetch_live(limit=limit, search=search)
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(CACHE_PATH, index=False)
        return df

    if CACHE_PATH.exists():
        return pd.read_parquet(CACHE_PATH)

    try:
        df = fetch_live(limit=limit, search=search)
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(CACHE_PATH, index=False)
        return df
    except Exception:
        if SEED_ROWS_PATH.exists():
            raw = json.loads(SEED_ROWS_PATH.read_text())
            rows = raw.get("rows", [])
            return pd.DataFrame(rows)
        raise


def load_catalogue() -> pd.DataFrame:
    if CATALOGUE_PATH.exists():
        raw = json.loads(CATALOGUE_PATH.read_text())
    elif SEED_CATALOGUE_PATH.exists():
        raw = json.loads(SEED_CATALOGUE_PATH.read_text())
    else:
        return pd.DataFrame()
    items = raw.get("items", [])
    if not isinstance(items, list):
        return pd.DataFrame()
    return pd.DataFrame(items)


def load_starter_index() -> list[dict[str, Any]]:
    if not STARTER_INDEX_PATH.exists():
        return []
    raw = json.loads(STARTER_INDEX_PATH.read_text())
    items = raw.get("starters", [])
    if not isinstance(items, list):
        return []
    return items


def main() -> None:
    st.set_page_config(page_title="Kaggle Mashup", layout="wide")
    st.title("Kaggle Mashup UI")
    st.caption("Sort through competitions/challenges/models/notebooks/datasets and keep a reproducible starter library.")

    with st.sidebar:
        limit = st.slider("Items per source", min_value=10, max_value=200, value=60, step=10)
        search = st.text_input("Search", value="")
        force_live = st.checkbox("Refresh live from Kaggle API", value=False)
        refresh_catalogue = st.checkbox("Refresh structured catalogue", value=False)
        sort_by = st.selectbox("Sort by", ["kind", "score", "updated", "title"], index=1)
        ascending = st.checkbox("Ascending", value=False)

    try:
        df = load_or_fetch(limit=limit, search=search, force_live=force_live)
    except Exception as e:
        st.error(f"Kaggle API unavailable: {e}")
        st.info("Set KAGGLE_USERNAME and KAGGLE_KEY, or place ~/.kaggle/kaggle.json")
        return

    if df.empty:
        st.warning("No rows returned.")
        return

    if refresh_catalogue:
        from labops.datasets.kaggle_catalogue import build_catalogue

        try:
            build_catalogue(out=CATALOGUE_PATH, search=search or "rna", limit=limit)
            st.success(f"Catalogue refreshed: {CATALOGUE_PATH}")
        except Exception as e:
            st.warning(f"Catalogue refresh failed: {e}")

    tab_live, tab_catalogue, tab_starters = st.tabs(["Live Search", "Structured Catalogue", "Starter Notebook Library"])

    with tab_live:
        kinds = st.multiselect("Kinds", options=sorted(df["kind"].unique().tolist()), default=sorted(df["kind"].unique().tolist()))
        f = df[df["kind"].isin(kinds)].copy()
        if sort_by in f.columns:
            f = f.sort_values(sort_by, ascending=ascending, kind="mergesort")

        col1, col2, col3 = st.columns(3)
        col1.metric("Rows", len(f))
        col2.metric("Competitions", int((f["kind"] == "competition").sum()))
        col3.metric("Datasets", int((f["kind"] == "dataset").sum()))

        st.dataframe(f[["kind", "title", "subtitle", "score", "updated", "url"]], use_container_width=True, height=480)

        st.subheader("Quick links")
        top_links = f.head(10)[["title", "url"]].to_dict(orient="records")
        for row in top_links:
            st.markdown(f"- [{row['title']}]({row['url']})")

    with tab_catalogue:
        cdf = load_catalogue()
        if cdf.empty:
            st.info("No structured catalogue found yet. Enable 'Refresh structured catalogue' then reload.")
        else:
            domains = sorted([d for d in cdf.get("domain", pd.Series(dtype=str)).dropna().unique().tolist() if d])
            kinds = sorted([k for k in cdf.get("kind", pd.Series(dtype=str)).dropna().unique().tolist() if k])
            selected_domains = st.multiselect("Domains", options=domains, default=domains)
            selected_kinds = st.multiselect("Item types", options=kinds, default=kinds)
            f = cdf[cdf["domain"].isin(selected_domains) & cdf["kind"].isin(selected_kinds)].copy()
            st.dataframe(
                f[
                    [
                        "kind",
                        "title",
                        "domain",
                        "data_shape",
                        "representation",
                        "target",
                        "validation_dropout",
                        "url",
                    ]
                ],
                use_container_width=True,
                height=520,
            )

    with tab_starters:
        starters = load_starter_index()
        if not starters:
            st.info("No local starter index found at notebooks/starters/index.json")
        else:
            st.caption("Clone-ready starter notebooks maintained in this repo.")
            for s in starters:
                title = s.get("title", "Untitled")
                nb_path = s.get("path", "")
                desc = s.get("description", "")
                focus = s.get("focus", "")
                st.markdown(f"### {title}")
                st.markdown(f"- Path: `{nb_path}`")
                st.markdown(f"- Focus: `{focus}`")
                st.markdown(f"- {desc}")

    st.caption(f"Last refresh: {datetime.utcnow().isoformat()}Z")


if __name__ == "__main__":
    main()
