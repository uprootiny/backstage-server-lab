from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .bench import export_thesis_graph, run_bench
from .store import connect, insert_hypothesis

app = typer.Typer(no_args_is_help=True, help="Validation bench + hypothesis/VOI orchestration")
console = Console()

DB_DEFAULT = Path("artifacts/validation_bench.db")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    table = Table(title="Recent Validations")
    table.add_column("variant")
    table.add_column("metric")
    table.add_column("status")
    for variant, metric in rows:
        status = "PASS" if float(metric) >= min_metric else "FAIL"
        table.add_row(str(variant), f"{float(metric):.4f}", status)
    console.print(table)


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
