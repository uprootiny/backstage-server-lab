from __future__ import annotations

import uuid
from datetime import datetime, timezone
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .bench import export_thesis_graph, run_bench
from .datasets.kaggle_catalogue import build_catalogue
from .datasets.kaggle import sync_kaggle
from .kaggle_mass_study import build_notebook_minimap
from .kaggle_parallel import dispatch as kaggle_parallel_dispatch
from .kaggle_parallel import init_plan as kaggle_parallel_init_plan
from .kaggle_parallel import suggest_reruns as kaggle_parallel_suggest_reruns
from .kaggle_parallel import summarize_ledger as kaggle_parallel_summarize_ledger
from .notebook_ops import list_registry, profile_submission, register_submission
from .notebook_pipeline import materialize_pipeline
from .runner import run_experiment_file
from .rna_ingest import ingest_result
from .store import connect, insert_hypothesis
from .techniques import compose_techniques, load_techniques
from .validation import validate_results
from .voi import value_of_information

app = typer.Typer(no_args_is_help=True, help="Validation bench + experiment orchestration")
console = Console()

DB_DEFAULT = Path("artifacts/validation_bench.db")
RNA_INDEX_DEFAULT = Path("artifacts/rna_predictions/index.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.command("new-exp")
def new_exp(name: str, out: Path = Path("experiments")) -> None:
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.yaml"
    if p.exists():
        raise typer.BadParameter(f"experiment exists: {p}")
    p.write_text(
        "\n".join(
            [
                f"name: {name}",
                "hypothesis: |",
                "  Replace with a crisp testable statement",
                "dataset: kaggle/<dataset-ref>",
                "variants:",
                "  - lr: 0.0001",
                "    batch_size: 16",
                "  - lr: 0.0003",
                "    batch_size: 32",
                "  - lr: 0.001",
                "    batch_size: 64",
                "metrics:",
                "  - score",
            ]
        )
        + "\n"
    )
    console.print(f"[green]created[/green] {p}")


@app.command("run")
def run(experiment: Path, workers: int = 3) -> None:
    out = run_experiment_file(experiment, workers=workers)
    table = Table(title=f"Experiment Run: {out['experiment']}")
    table.add_column("variant_idx")
    table.add_column("score")
    for r in out["results"]:
        table.add_row(str(r["variant_idx"]), f"{r['score']:.4f}")
    console.print(table)


@app.command("suggest-next")
def suggest_next(uncertainty: float = 0.6, expected_improvement: float = 0.2, importance: float = 0.9) -> None:
    voi = value_of_information(uncertainty, expected_improvement, importance)
    console.print({"voi": round(voi, 4), "uncertainty": uncertainty, "expected_improvement": expected_improvement, "importance": importance})


@app.command("kaggle-sync")
def kaggle_sync(search: str = "", limit: int = 50, out: Path = Path("artifacts/kaggle_sync.json")) -> None:
    path = sync_kaggle(out=out, search=search, limit=limit)
    console.print(f"[green]kaggle sync written[/green] {path}")


@app.command("kaggle-catalogue")
def kaggle_catalogue(search: str = "rna", limit: int = 80, out: Path = Path("artifacts/kaggle_catalogue.json")) -> None:
    path = build_catalogue(out=out, search=search, limit=limit)
    console.print(f"[green]kaggle catalogue written[/green] {path}")


@app.command("kaggle-init")
def kaggle_init(ref: str, out: Path = Path("experiments")) -> None:
    out.mkdir(parents=True, exist_ok=True)
    name = ref.replace("/", "-")
    p = out / f"{name}.yaml"
    p.write_text(
        "\n".join(
            [
                f"name: {name}",
                "hypothesis: |",
                f"  Baseline on kaggle challenge {ref} can be improved by variant search",
                f"dataset: kaggle/{ref}",
                "variants:",
                "  - lr: 0.0001",
                "    batch_size: 16",
                "  - lr: 0.0003",
                "    batch_size: 32",
                "  - lr: 0.001",
                "    batch_size: 64",
                "metrics:",
                "  - score",
            ]
        )
        + "\n"
    )
    console.print(f"[green]experiment initialized[/green] {p}")


@app.command("kaggle-notebook-minimap")
def kaggle_notebook_minimap(
    search: str = "rna",
    limit: int = 300,
    out_json: Path = Path("artifacts/kaggle_rna_notebooks_minimap.json"),
    out_md: Path = Path("docs/KAGGLE_RNA_NOTEBOOK_MINIMAP.md"),
) -> None:
    j, m = build_notebook_minimap(search=search, limit=limit, out_json=out_json, out_md=out_md)
    console.print({"json": str(j), "markdown": str(m)})


@app.command("kaggle-parallel-init")
def kaggle_parallel_init(
    profile: str = "three",
    out: Path = Path("artifacts/kaggle_parallel/plan.yaml"),
    notebooks_dir: Path = Path("notebooks/kaggle"),
) -> None:
    p = kaggle_parallel_init_plan(profile=profile, out=out, notebooks_dir=notebooks_dir)
    console.print({"plan": str(p), "profile": profile})


@app.command("kaggle-parallel-dispatch")
def kaggle_parallel_dispatch_cmd(
    plan: Path = Path("artifacts/kaggle_parallel/plan.yaml"),
    workers: int = 3,
    ledger: Path = Path("artifacts/kaggle_parallel/ledger.jsonl"),
    logs_dir: Path = Path("logs/kaggle_parallel"),
    executed_dir: Path = Path("artifacts/kaggle_parallel/executed"),
) -> None:
    out = kaggle_parallel_dispatch(
        plan_path=plan,
        concurrency=workers,
        ledger_path=ledger,
        logs_dir=logs_dir,
        executed_dir=executed_dir,
    )
    console.print(out)


@app.command("kaggle-parallel-status")
def kaggle_parallel_status(
    ledger: Path = Path("artifacts/kaggle_parallel/ledger.jsonl"),
) -> None:
    out = kaggle_parallel_summarize_ledger(ledger_path=ledger)
    console.print(out)


@app.command("kaggle-parallel-reruns")
def kaggle_parallel_reruns(
    ledger: Path = Path("artifacts/kaggle_parallel/ledger.jsonl"),
    min_voi: float = 0.12,
    limit: int = 12,
) -> None:
    out = kaggle_parallel_suggest_reruns(ledger_path=ledger, min_voi=min_voi, limit=limit)
    console.print(out)


@app.command("technique-list")
def technique_list(path: Path = Path("catalogue/techniques/rna_notebook_techniques.yaml")) -> None:
    rows = load_techniques(path=path)
    table = Table(title="Technique Library")
    table.add_column("id")
    table.add_column("name")
    table.add_column("stage")
    table.add_column("source")
    for r in rows:
        table.add_row(str(r.get("id", "")), str(r.get("name", "")), str(r.get("stage", "")), str(r.get("source", "")))
    console.print(table)


@app.command("technique-compose")
def technique_compose(
    ids: str,
    hypothesis: str = "Composed strategy improves structural fidelity",
    dataset: str = "kaggle/stanford-rna-3d-folding-part-2",
    path: Path = Path("catalogue/techniques/rna_notebook_techniques.yaml"),
    out: Path = Path("artifacts/technique_compositions/latest.yaml"),
) -> None:
    selected = [x.strip() for x in ids.split(",") if x.strip()]
    t = load_techniques(path=path)
    outp = compose_techniques(selected_ids=selected, all_techniques=t, hypothesis=hypothesis, dataset=dataset, out=out)
    console.print({"composition": str(outp), "suggested_experiment": str(out.parent / "composed_experiment.yaml")})


@app.command("ingest-result")
def ingest_result_cmd(
    input_path: Path,
    run_id: str = "",
    sequence: str = "",
    model: str = "unknown",
    out_root: Path = Path("artifacts/rna_predictions"),
    public_base: str = "http://127.0.0.1:19999",
) -> None:
    rid = run_id or f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_pdb = out_root / rid / "prediction.pdb"
    out = ingest_result(input_path=input_path, out_pdb=out_pdb, default_seq=sequence)

    out_root.mkdir(parents=True, exist_ok=True)
    idx_path = out_root / "index.json"
    if idx_path.exists():
        idx = json.loads(idx_path.read_text())
    else:
        idx = {"predictions": []}
    preds = idx.get("predictions", [])
    if not isinstance(preds, list):
        preds = []
    preds.append(
        {
            "run_id": rid,
            "sequence": sequence or "unknown",
            "model": model,
            "pdb_url": f"{public_base.rstrip('/')}/{rid}/prediction.pdb",
            "created_at": now_iso(),
            "source": str(input_path),
        }
    )
    idx["predictions"] = preds
    idx_path.write_text(json.dumps(idx, indent=2))
    console.print(
        {
            "ingested": str(out),
            "index": str(idx_path),
            "pdb_url": f"{public_base.rstrip('/')}/{rid}/prediction.pdb",
        }
    )


@app.command("submission-profile")
def submission_profile(
    input_path: Path,
    sample_rows: int = 200,
) -> None:
    info = profile_submission(path=input_path, sample_rows=sample_rows)
    console.print(info)


@app.command("notebook-extract-pipeline")
def notebook_extract_pipeline(
    notebook: Path,
    out_dir: Path = Path("artifacts/notebook_pipelines"),
) -> None:
    out = materialize_pipeline(path=notebook, out_root=out_dir)
    console.print({k: str(v) for k, v in out.items()})


@app.command("submission-register")
def submission_register(
    notebook_ref: str,
    submission_path: Path,
    mark: str = "candidate",
    breadcrumb: str = "",
    sequence: str = "",
    model: str = "unknown",
    run_id: str = "",
    sample_idx: int = 1,
    target_id: str = "",
    bridge_base: str = "http://127.0.0.1:19999",
) -> None:
    row = register_submission(
        notebook_ref=notebook_ref,
        submission_path=submission_path,
        mark=mark,
        breadcrumb=breadcrumb,
        sequence=sequence,
        model=model,
        run_id=run_id,
        sample_idx=sample_idx,
        target_id=target_id,
        bridge_base=bridge_base,
    )
    console.print(row)


@app.command("submission-list")
def submission_list(limit: int = 50) -> None:
    rows = list_registry()
    table = Table(title="Notebook Submission Registry")
    table.add_column("created")
    table.add_column("notebook")
    table.add_column("format")
    table.add_column("mark")
    table.add_column("viewer_url")
    for r in rows[-limit:]:
        profile = r.get("profile", {}) if isinstance(r, dict) else {}
        table.add_row(
            str(r.get("created_at", "")),
            str(r.get("notebook_ref", "")),
            str(profile.get("format", "")),
            str(r.get("mark", "")),
            str(r.get("viewer_url", "")),
        )
    console.print(table)


@app.command("formulate")
def formulate(
    statement: str,
    question: str,
    hypothesis_id: str | None = None,
    voi_prior: float = 0.5,
    kaggle_ref: str = "",
    paper_ref: str = "",
    db: Path = DB_DEFAULT,
) -> None:
    hid = hypothesis_id or str(uuid.uuid4())
    conn = connect(db)
    insert_hypothesis(
        conn,
        {
            "hypothesis_id": hid,
            "statement": statement,
            "question": question,
            "voi_prior": voi_prior,
            "kaggle_ref": kaggle_ref,
            "paper_ref": paper_ref,
            "created_at": now_iso(),
        },
    )
    conn.close()
    console.print(f"[green]hypothesis saved[/green] id={hid}")


@app.command("run-bench")
def run_bench_cmd(
    hypothesis_id: str,
    config: Path = Path("configs/validation_bench.yaml"),
    workers: int = 3,
    db: Path = DB_DEFAULT,
) -> None:
    results = run_bench(db_path=db, config_path=config, hypothesis_id=hypothesis_id, workers=workers)
    table = Table(title=f"Validation Bench: {hypothesis_id}")
    table.add_column("variant")
    table.add_column("metric")
    table.add_column("score")
    for r in results:
        table.add_row(r["variant"], f"{r['metric']:.4f}", f"{r['score']:.4f}")
    console.print(table)


@app.command("validate")
def validate(
    min_metric: float = 0.7,
    db: Path = DB_DEFAULT,
) -> None:
    conn = connect(db)
    cur = conn.cursor()
    cur.execute("SELECT variant, metric FROM runs ORDER BY ended_at DESC LIMIT 20")
    rows = cur.fetchall()
    conn.close()

    recent = [{"variant": str(v), "score": float(m)} for v, m in rows]
    summary = validate_results(recent, min_score=min_metric)

    table = Table(title="Recent Validations")
    table.add_column("variant")
    table.add_column("metric")
    table.add_column("status")
    for variant, metric in rows:
        status = "PASS" if float(metric) >= min_metric else "FAIL"
        table.add_row(str(variant), f"{float(metric):.4f}", status)
    console.print(table)
    console.print(summary)


@app.command("graph")
def graph(out: Path = Path("artifacts/thesis_graph.json"), db: Path = DB_DEFAULT) -> None:
    export_thesis_graph(db_path=db, out_path=out)
    console.print(f"[green]graph exported[/green] {out}")


@app.command("list")
def list_hypotheses(db: Path = DB_DEFAULT) -> None:
    conn = connect(db)
    cur = conn.cursor()
    cur.execute("SELECT hypothesis_id, statement, question, voi_prior, created_at FROM hypotheses ORDER BY created_at DESC LIMIT 50")
    rows = cur.fetchall()
    conn.close()

    table = Table(title="Hypotheses")
    table.add_column("id")
    table.add_column("statement")
    table.add_column("question")
    table.add_column("voi")
    table.add_column("created")
    for row in rows:
        table.add_row(str(row[0]), str(row[1]), str(row[2]), f"{float(row[3]):.2f}", str(row[4]))
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
