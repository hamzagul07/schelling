"""The ``schelling`` command-line interface (BUILD_PLAN §8).

Two workflows:

    schelling solve <fixture.json> --draws N --seed S [config flags]
    schelling knowledge search "<query>" [-k N]
    schelling knowledge build [--transcripts DIR] [--embedder bge-m3|hashing]
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from schelling.knowledge.embed import make_embedder
from schelling.knowledge.index import DEFAULT_DB_PATH, DEFAULT_TRANSCRIPTS, KnowledgeIndex
from schelling.mc.monte_carlo import forecast
from schelling.mc.sensitivity import format_tornado
from schelling.schemas.question import GameSpec
from schelling.solver.config import RangeMode, SolverConfig

app = typer.Typer(
    help="Schelling — deterministic strategic-forecasting engine.", no_args_is_help=True
)
knowledge_app = typer.Typer(help="Transcript concept index (BUILD_PLAN §7).", no_args_is_help=True)
app.add_typer(knowledge_app, name="knowledge")


@app.command()
def solve(
    fixture: Path = typer.Argument(..., help="Path to a GameSpec JSON fixture."),
    draws: int = typer.Option(10_000, "--draws", help="Number of Monte Carlo draws."),
    seed: int = typer.Option(42, "--seed", help="Monte Carlo master seed."),
    range_mode: RangeMode = typer.Option(RangeMode.DYNAMIC, "--range-mode"),
    q: float = typer.Option(1.0, "--q", min=0.0, max=1.0, help="Status-quo probability Q."),
    security_mode: str = typer.Option("adversary", "--security-mode"),
    conflict_resolves: bool = typer.Option(False, "--conflict-resolves/--no-conflict-resolves"),
    apply_risk: bool = typer.Option(True, "--apply-risk/--no-apply-risk"),
    max_rounds: int = typer.Option(20, "--max-rounds", min=1),
    out_dir: Path = typer.Option(Path("runs"), "--out-dir", help="Where the record is written."),
) -> None:
    """Solve a game with Monte Carlo, print the forecast + tornado, write the ForecastRecord."""
    if not fixture.exists():
        typer.echo(f"fixture not found: {fixture}", err=True)
        raise typer.Exit(code=2)
    game = GameSpec.model_validate(json.loads(fixture.read_text()))
    config = SolverConfig(
        range_mode=range_mode,
        q=q,
        security_mode=security_mode,
        conflict_resolves=conflict_resolves,
        apply_risk=apply_risk,
        max_rounds=max_rounds,
        seed=seed,
    )
    record = forecast(game, config, n_draws=draws, seed=seed, out_dir=out_dir)
    e = record.ensemble
    conv = record.convergence_stats
    typer.echo(f"Question:  {record.question_id}")
    typer.echo(
        f"Forecast:  median {e.median:.3f}   mean {e.mean:.3f}   (n={e.n_draws} draws, seed {seed})"
    )
    typer.echo(f"CI80:      [{e.p10:.3f}, {e.p90:.3f}]")
    typer.echo(
        f"Converge:  {conv.get('converged_fraction', 0.0) * 100:.1f}% converged, "
        f"mean {conv.get('rounds_mean', 0.0):.1f} rounds (max {conv.get('rounds_max', 0.0):.0f})"
    )
    typer.echo("")
    typer.echo(format_tornado(record.sensitivity))
    typer.echo("")
    typer.echo(f"Record written: {out_dir / (record.run_id + '.json')}")


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(..., help="Free-text query."),
    k: int = typer.Option(5, "-k", "--k", min=1, help="Number of results."),
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="Index database path."),
) -> None:
    """Search the transcript index; prints top chunks with lecture citation refs."""
    if not db_path.exists():
        typer.echo(f"no index at {db_path}. Build one with: schelling knowledge build", err=True)
        raise typer.Exit(code=2)
    index = KnowledgeIndex.open(db_path)
    results = index.search(query, k=k)
    if not results:
        typer.echo("no results.")
        return
    for rank, result in enumerate(results, start=1):
        snippet = " ".join(result.chunk.text.split())[:220]
        typer.echo(f"{rank}. [{result.score:.3f}] {result.ref}")
        typer.echo(f"   {snippet}...")
        typer.echo("")


@knowledge_app.command("build")
def knowledge_build(
    transcripts: Path = typer.Option(DEFAULT_TRANSCRIPTS, "--transcripts"),
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db"),
    embedder: str = typer.Option("bge-m3", "--embedder", help="'bge-m3' or 'hashing'."),
) -> None:
    """Chunk the transcripts and build the sqlite-vec index."""
    if not transcripts.exists() or not any(transcripts.glob("*.txt")):
        typer.echo(f"no transcripts in {transcripts}", err=True)
        raise typer.Exit(code=2)
    typer.echo(f"building index ({embedder}) from {transcripts} ...")
    index = KnowledgeIndex.build_from_transcripts(
        transcripts, embedder=make_embedder(embedder), db_path=db_path
    )
    typer.echo(f"indexed {index.count()} chunks -> {db_path}")


if __name__ == "__main__":  # pragma: no cover
    app()
