from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
REGISTRY_PATH = Path("artifacts/notebook_submission_registry.jsonl")
PARALLEL_PLAN_PATH = Path("artifacts/kaggle_parallel/plan.json")
PARALLEL_PLAN_YAML_PATH = Path("artifacts/kaggle_parallel/plan.yaml")
PARALLEL_LEDGER_PATH = Path("artifacts/kaggle_parallel/ledger.jsonl")
LIVE_ENDPOINTS_PATH = Path("docs/LIVE_ENDPOINTS.md")
LOG_DIR = Path("logs")
EVENTS_PATH = Path("artifacts/operator_events.jsonl")


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


def load_registry() -> pd.DataFrame:
    if not REGISTRY_PATH.exists():
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for line in REGISTRY_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "profile" in df.columns:
        df["format"] = df["profile"].apply(
            lambda p: p.get("format", "") if isinstance(p, dict) else ""
        )
    return df


def load_parallel_plan() -> dict[str, Any]:
    if PARALLEL_PLAN_PATH.exists():
        try:
            return json.loads(PARALLEL_PLAN_PATH.read_text())
        except Exception:
            return {}
    if PARALLEL_PLAN_YAML_PATH.exists():
        try:
            import yaml

            raw = yaml.safe_load(PARALLEL_PLAN_YAML_PATH.read_text())
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}
    return {}


def load_parallel_ledger() -> pd.DataFrame:
    if not PARALLEL_LEDGER_PATH.exists():
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for line in PARALLEL_LEDGER_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def read_live_endpoints_md() -> str:
    if not LIVE_ENDPOINTS_PATH.exists():
        return "No `docs/LIVE_ENDPOINTS.md` yet. Run `make obs-probe`."
    return LIVE_ENDPOINTS_PATH.read_text()


def recent_logs(max_lines: int = 250) -> str:
    parts: list[str] = []
    for path in sorted(LOG_DIR.glob("*.log")):
        try:
            tail = path.read_text().splitlines()[-max_lines:]
        except Exception:
            tail = []
        parts.append(f"## {path.name}\n" + ("\n".join(tail) if tail else "(empty)"))
    return "\n\n".join(parts) if parts else "No log files found in `logs/`."


def _fmt_utc(dt: datetime | None = None) -> str:
    now = dt or datetime.now(timezone.utc)
    return now.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_events() -> pd.DataFrame:
    if not EVENTS_PATH.exists():
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for line in EVENTS_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return pd.DataFrame(rows)


def emit_event(kind: str, source: str, message: str, severity: str = "info", run_id: str = "") -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _fmt_utc(),
        "kind": kind,
        "source": source,
        "message": message,
        "severity": severity,
        "run_id": run_id,
    }
    with EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


def context_rail() -> None:
    st.sidebar.markdown("### Context Rail")
    registry = load_registry()
    ledger = load_parallel_ledger()
    latest_run = ""
    if not ledger.empty and "run_id" in ledger.columns:
        latest = ledger.dropna(subset=["run_id"]).tail(1)
        if not latest.empty:
            latest_run = str(latest.iloc[0]["run_id"])
    st.sidebar.code(
        "\n".join(
            [
                f"active_run: {latest_run or '(none)'}",
                f"submission_rows: {len(registry)}",
                f"parallel_events: {len(ledger)}",
                f"events_file: {EVENTS_PATH}",
                f"registry_file: {REGISTRY_PATH}",
                f"plan_file: {PARALLEL_PLAN_PATH}",
            ]
        ),
        language="text",
    )


def render_pipeline_tab() -> None:
    st.subheader("Pipeline Observatory")
    st.caption("State -> execution -> interpretation -> prioritization.")
    stages = [
        "1. Ingest notebook output",
        "2. Detect submission format",
        "3. Normalize to canonical records",
        "4. Register artifact + breadcrumb",
        "5. Build structure representations",
        "6. Launch viewer overlays",
        "7. Compare against prior runs",
        "8. Score VOI + propose next tests",
        "9. Execute batch reruns",
        "10. Persist ledger + graph",
    ]
    st.code("\n".join(stages), language="text")
    st.markdown("### Live ingress")
    st.markdown(read_live_endpoints_md())
    st.markdown("### State artifact contract")
    st.code(
        """{
  "run_id": "run_2026_03_14_001",
  "experiment_id": "exp_recycling_6_layers_8",
  "input_artifacts": ["submission.csv"],
  "normalized_artifacts": ["structure_record.parquet", "manifest.json"],
  "metrics": {"tm_score": 0.71, "lddt": 0.63},
  "mark": "candidate",
  "validation_spec": "family_dropout_v1",
  "status": "completed"
}""",
        language="json",
    )


def render_registry_tab() -> None:
    st.subheader("Submission Ledger")
    df = load_registry()
    if df.empty:
        st.info("No submission registry rows yet. Use `make submission-register`.")
        return

    display_cols = [
        c
        for c in [
            "created_at",
            "notebook_ref",
            "run_id",
            "mark",
            "tm_score",
            "lddt",
            "format",
            "viewer_url",
            "breadcrumb",
        ]
        if c in df.columns
    ]
    st.dataframe(df[display_cols], use_container_width=True, height=380)

    choices = df.index.tolist()
    selected = st.multiselect("compare 2", choices, default=choices[:2] if len(choices) >= 2 else choices)
    if len(selected) == 2:
        left = df.loc[selected[0]].to_dict()
        right = df.loc[selected[1]].to_dict()
        ltm = float(left.get("tm_score", 0) or 0)
        rtm = float(right.get("tm_score", 0) or 0)
        lld = float(left.get("lddt", 0) or 0)
        rld = float(right.get("lddt", 0) or 0)
        st.markdown("### Diff card")
        st.write(
            {
                "left_run": left.get("run_id", ""),
                "right_run": right.get("run_id", ""),
                "tm_score_delta": round(rtm - ltm, 6),
                "lddt_delta": round(rld - lld, 6),
                "left_notebook": left.get("notebook_ref", ""),
                "right_notebook": right.get("notebook_ref", ""),
            }
        )


def render_parallel_tab() -> None:
    st.subheader("Run Fabric")
    plan = load_parallel_plan()
    ledger = load_parallel_ledger()

    col1, col2, col3 = st.columns(3)
    col1.metric("Plan jobs", int(_safe_len(plan.get("jobs", []))))
    col2.metric("Ledger rows", int(len(ledger)))
    if not ledger.empty and "status" in ledger.columns:
        col3.metric("Failures", int((ledger["status"] != "ok").sum()))
    else:
        col3.metric("Failures", 0)

    if plan:
        st.markdown("### Plan")
        st.json(plan)
    else:
        st.info("No parallel plan found yet. Use `labops kaggle-parallel-init`.")

    if ledger.empty:
        st.info("No ledger yet. Use `labops kaggle-parallel-dispatch`.")
        return
    st.markdown("### Ledger")
    st.dataframe(ledger, use_container_width=True, height=360)

    st.markdown("### Control snippets")
    st.code(
        "\n".join(
            [
                "labops kaggle-parallel-dispatch --workers 3",
                "labops kaggle-parallel-dispatch --workers 10",
                "labops kaggle-parallel-dispatch --workers 12",
                "labops kaggle-parallel-reruns --status failed",
            ]
        ),
        language="bash",
    )


def render_voi_tab() -> None:
    st.subheader("VOI Compass")
    voi = pd.DataFrame(
        [
            {"param": "recycling_depth", "voi": 0.91},
            {"param": "n_layers", "voi": 0.84},
            {"param": "n_heads", "voi": 0.72},
            {"param": "dropout", "voi": 0.58},
            {"param": "lr", "voi": 0.66},
        ]
    )
    st.bar_chart(voi.set_index("param"))
    st.caption("Highest-information next moves: recycling depth 3->6 and n_layers 4->8.")
    st.markdown("### Decomposition")
    st.code(
        "VOI = ((uncertainty * upside * relevance * novelty) / cost) * coverage_bonus",
        language="text",
    )

    st.markdown("### Hypothesis shelf")
    st.code(
        "\n".join(
            [
                "H1: recycling depth >3 improves long-range helix recovery",
                "EVIDENCE: exp17 +0.03 F1, exp21 +0.02 F1, exp25 -0.01 F1",
                "STATUS: active",
            ]
        ),
        language="text",
    )


def render_log_tab() -> None:
    st.subheader("Operator Trace")
    st.caption("Typed event stream + service traces.")
    events = load_events()
    if events.empty:
        emit_event("infra.info", "observatory", "operator trace initialized")
        events = load_events()
    if not events.empty:
        st.dataframe(events.tail(200), use_container_width=True, height=260)
    st.text_area("Recent raw logs", value=recent_logs(), height=260)


def render_garden_tab() -> None:
    st.subheader("RNA Helix Garden")
    st.caption("Morphology map: stem height=prominence, color=entity type, pulse=active competition.")
    st.markdown(
        """
<style>
.garden-wrap { background: radial-gradient(circle at 20% 20%, #1b2018, #0e110c 62%); border: 1px solid #2a3125; border-radius: 10px; padding: 10px; }
.garden-title { color: #e8b74d; font-family: "IBM Plex Mono", monospace; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 8px; }
.garden-svg { width: 100%; height: 260px; display:block; }
.helix-line { stroke: #7fbf7f; stroke-width: 1; opacity: .35; }
.helix-dot { animation: pulse 2.6s ease-in-out infinite; }
@keyframes pulse { 0% { opacity:.35; } 50% { opacity:1; } 100% { opacity:.35; } }
</style>
<div class="garden-wrap">
  <div class="garden-title">Generative Helix Field</div>
  <svg class="garden-svg" viewBox="0 0 1200 260" xmlns="http://www.w3.org/2000/svg">
    <rect x="0" y="0" width="1200" height="260" fill="transparent"/>
    <g>
      <line class="helix-line" x1="70" y1="220" x2="70" y2="40"/>
      <line class="helix-line" x1="250" y1="220" x2="250" y2="20"/>
      <line class="helix-line" x1="430" y1="220" x2="430" y2="55"/>
      <line class="helix-line" x1="610" y1="220" x2="610" y2="35"/>
      <line class="helix-line" x1="790" y1="220" x2="790" y2="28"/>
      <line class="helix-line" x1="970" y1="220" x2="970" y2="45"/>
      <line class="helix-line" x1="1130" y1="220" x2="1130" y2="60"/>
    </g>
    <g>
      <circle class="helix-dot" cx="70" cy="38" r="8" fill="#d59a2a"/>
      <circle class="helix-dot" cx="250" cy="20" r="7" fill="#d59a2a" style="animation-delay:.2s"/>
      <circle class="helix-dot" cx="430" cy="56" r="6" fill="#70c070" style="animation-delay:.4s"/>
      <circle class="helix-dot" cx="610" cy="35" r="6" fill="#70c070" style="animation-delay:.6s"/>
      <circle class="helix-dot" cx="790" cy="28" r="6" fill="#9a7be0" style="animation-delay:.8s"/>
      <circle class="helix-dot" cx="970" cy="45" r="6" fill="#5fa4d6" style="animation-delay:1s"/>
      <circle class="helix-dot" cx="1130" cy="60" r="6" fill="#9a7be0" style="animation-delay:1.2s"/>
    </g>
  </svg>
</div>
        """,
        unsafe_allow_html=True,
    )
    plants = pd.DataFrame(
        [
            {"entity": "RNA 3D Part 2", "kind": "competition", "prominence": 1938, "pulse": 1},
            {"entity": "Ribonanza", "kind": "competition", "prominence": 890, "pulse": 0},
            {"entity": "RibonanzaNet2", "kind": "model", "prominence": 760, "pulse": 0},
            {"entity": "RNA-FM", "kind": "model", "prominence": 540, "pulse": 0},
            {"entity": "Top Notebook A", "kind": "notebook", "prominence": 420, "pulse": 0},
            {"entity": "Stanford RNA 3D data", "kind": "dataset", "prominence": 610, "pulse": 0},
        ]
    )
    st.dataframe(plants, use_container_width=True, height=280)
    st.markdown("### Data Contract")
    st.code(
        "\n".join(
            [
                "data shape: seq -> MSA -> pairwise tensor -> 3D coords",
                "representation: contact map + atom coordinates",
                "target: base-pair geometry and residue coordinates",
                "validation: temporal + family/motif dropout",
            ]
        ),
        language="text",
    )


def main() -> None:
    st.set_page_config(page_title="RNA Folding Research Observatory", layout="wide")
    st.title("RNA Folding Research Observatory")
    st.caption("One operator surface for ingest, registry, parallel execution, VOI, logs, and the helix garden.")

    with st.sidebar:
        limit = st.slider("Items per source", min_value=10, max_value=200, value=60, step=10)
        search = st.text_input("Search", value="")
        force_live = st.checkbox("Refresh live from Kaggle API", value=False)
        refresh_catalogue = st.checkbox("Refresh structured catalogue", value=False)
        sort_by = st.selectbox("Sort by", ["kind", "score", "updated", "title"], index=1)
        ascending = st.checkbox("Ascending", value=False)
    context_rail()

    try:
        df = load_or_fetch(limit=limit, search=search, force_live=force_live)
    except Exception:
        df = pd.DataFrame()

    if refresh_catalogue:
        from labops.datasets.kaggle_catalogue import build_catalogue

        try:
            build_catalogue(out=CATALOGUE_PATH, search=search or "rna", limit=limit)
            st.success(f"Catalogue refreshed: {CATALOGUE_PATH}")
        except Exception as e:
            st.warning(f"Catalogue refresh failed: {e}")

    tabs = st.tabs(
        [
            "Pipeline Observatory",
            "Submission Ledger",
            "Run Fabric",
            "VOI Compass",
            "Operator Trace",
            "Garden",
            "Live Search",
            "Structured Catalogue",
            "Starter Notebook Library",
        ]
    )

    with tabs[0]:
        render_pipeline_tab()

    with tabs[1]:
        render_registry_tab()

    with tabs[2]:
        render_parallel_tab()

    with tabs[3]:
        render_voi_tab()

    with tabs[4]:
        render_log_tab()

    with tabs[5]:
        render_garden_tab()

    with tabs[6]:
        if df.empty:
            st.warning("No live rows returned. Set Kaggle credentials to populate.")
            return
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

    with tabs[7]:
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

    with tabs[8]:
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

    st.caption(f"Last refresh: {_fmt_utc()}")


if __name__ == "__main__":
    main()
