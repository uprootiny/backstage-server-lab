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
from .runner import run_experiment_file
from .rna_ingest import ingest_result
from .store import connect, insert_hypothesis
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
