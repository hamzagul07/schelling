"""The ``schelling`` command-line interface (BUILD_PLAN §8).

Two workflows:

    schelling solve <fixture.json> --draws N --seed S [config flags]
    schelling knowledge search "<query>" [-k N]
    schelling knowledge build [--transcripts DIR] [--embedder bge-m3|hashing]
"""

from __future__ import annotations

import json
import os
import webbrowser
from pathlib import Path

import typer
from dotenv import find_dotenv, load_dotenv
from pydantic import ValidationError

from schelling.advise.search import advise as run_advise
from schelling.formalizer.client import AnthropicClient
from schelling.formalizer.firewall import IndexLeakageError
from schelling.formalizer.formalize import formalize as run_formalize
from schelling.formalizer.schemas import DraftGameSpec
from schelling.knowledge.embed import make_embedder
from schelling.knowledge.index import DEFAULT_DB_PATH, DEFAULT_TRANSCRIPTS, KnowledgeIndex
from schelling.mc.monte_carlo import forecast, write_record
from schelling.mc.sensitivity import format_tornado
from schelling.report.render import render as render_report
from schelling.schemas.forecast import ADVISE_CAVEAT, Assumption, DraftMetadata
from schelling.schemas.question import GameSpec
from schelling.schemas.stakeholders import TriangularEstimate
from schelling.solver.config import RangeMode, SolverConfig

app = typer.Typer(
    help="Schelling — deterministic strategic-forecasting engine.", no_args_is_help=True
)
knowledge_app = typer.Typer(help="Transcript concept index (BUILD_PLAN §7).", no_args_is_help=True)
app.add_typer(knowledge_app, name="knowledge")

# Shown when the bge-m3 knowledge extra is needed but not installed (D7.0c).
_KNOWLEDGE_HINT = (
    "This needs the 'knowledge' extra (bge-m3 embeddings): run `uv sync --all-extras`."
)


@app.callback()
def _startup() -> None:
    """Load a project ``.env`` at startup so ANTHROPIC_API_KEY is found automatically.

    Searches upward from the working directory (where the user runs ``schelling``), not from the
    package, so the developer's project ``.env`` is picked up.
    """
    load_dotenv(find_dotenv(usecwd=True))


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err.get("loc", ())) or "(root)"
    return f"{loc}: {err.get('msg', 'invalid')}"


def _load_solve_input(path: Path) -> tuple[GameSpec, list[Assumption], DraftMetadata | None]:
    """Load a GameSpec or a DraftGameSpec; raises ValueError with a one-sentence friendly reason."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON ({exc}).") from exc
    is_draft = isinstance(data, dict) and {"game", "assumptions", "template_classification"} <= set(
        data
    )
    if is_draft:
        try:
            draft = DraftGameSpec.model_validate(data)
        except ValidationError as exc:
            raise ValueError(
                f"{path} looks like a DraftGameSpec (formalizer output) but does not match the "
                f"schema ({_first_error(exc)}); re-run `schelling formalize` to regenerate it."
            ) from exc
        return draft.game, list(draft.assumptions), draft.metadata
    try:
        return GameSpec.model_validate(data), [], None
    except ValidationError as exc:
        shape = "a DraftGameSpec" if isinstance(data, dict) and "game" in data else "a GameSpec"
        raise ValueError(
            f"{path} is not a solvable game — `solve` expects a GameSpec or a DraftGameSpec "
            f"(from `schelling formalize`); this looks {shape}-shaped but invalid "
            f"({_first_error(exc)})."
        ) from exc


@app.command()
def solve(
    fixture: Path = typer.Argument(..., help="A GameSpec or DraftGameSpec JSON."),
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
    """Solve a game (bare GameSpec or a formalizer DraftGameSpec) and write the ForecastRecord."""
    if not fixture.exists():
        typer.echo(f"input not found: {fixture}", err=True)
        raise typer.Exit(code=2)
    try:
        game, assumptions, formalizer_metadata = _load_solve_input(fixture)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    config = SolverConfig(
        range_mode=range_mode,
        q=q,
        security_mode=security_mode,
        conflict_resolves=conflict_resolves,
        apply_risk=apply_risk,
        max_rounds=max_rounds,
        seed=seed,
    )
    record = forecast(
        game,
        config,
        n_draws=draws,
        seed=seed,
        out_dir=out_dir,
        assumptions=assumptions,
        formalizer_metadata=formalizer_metadata,
    )
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


def _rng(est: TriangularEstimate) -> str:
    return f"{est.low:g}-{est.mode:g}-{est.high:g}"


def _render_draft(draft: DraftGameSpec) -> str:
    """Human-readable stakeholder table + open assumptions for review."""
    g = draft.game
    lines = [
        f"Question:   {g.question_id}   (frozen {g.frozen_at})",
        f"Continuum:  {g.continuum.label}",
        f"            0 = {g.continuum.anchor_0}   100 = {g.continuum.anchor_100}",
        f"Template:   {draft.template_classification.template}   horizon: {g.horizon}",
        "",
        "Stakeholders (position / salience / capability as low-mode-high, 0-100):",
    ]
    for a in g.actors:
        lines.append(
            f"  {a.name} [{a.id}]  pos {_rng(a.position)}  sal {_rng(a.salience)}  "
            f"cap {_rng(a.capability)}"
        )
        for ev in a.evidence:
            lines.append(f"      evidence: {ev.note}  ({ev.source}, {ev.date})")
        if not a.evidence:
            lines.append("      evidence: (none supplied)")
    lines.append("")
    lines.append("Open assumptions (asserted WITHOUT supplied evidence — review before solving):")
    if draft.assumptions:
        for i, asm in enumerate(draft.assumptions, 1):
            lines.append(f"  {i}. {asm.statement}")
            lines.append(f"     why: {asm.why}")
    else:
        lines.append("  (none)")
    lines.append("")
    m = draft.metadata
    lines.append(
        f"Provenance: {m.model}  in={m.input_tokens} out={m.output_tokens} "
        f"tok  ${m.cost_usd:.4f}  retries={m.retries}"
    )
    return "\n".join(lines)


@app.command()
def formalize(
    situation: Path = typer.Argument(..., help="Path to a situation .txt file."),
    sources: Path | None = typer.Option(None, "--sources", help="Directory of source files."),
    output: Path | None = typer.Option(None, "-o", "--output", help="Where to write the draft."),
    model: str = typer.Option("claude-opus-4-8", "--model"),
    max_retries: int = typer.Option(2, "--max-retries", min=0),
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="Concept index (for grounding)."),
    no_knowledge: bool = typer.Option(False, "--no-knowledge", help="Skip concept grounding."),
) -> None:
    """Formalize a situation into a DraftGameSpec. NEVER auto-solves — review, then `solve`."""
    if not situation.exists():
        typer.echo(f"situation file not found: {situation}", err=True)
        raise typer.Exit(code=2)
    situation_text = situation.read_text()

    source_texts: dict[str, str] = {}
    if sources is not None:
        if not sources.is_dir():
            typer.echo(f"--sources is not a directory: {sources}", err=True)
            raise typer.Exit(code=2)
        for path in sorted(sources.iterdir()):
            if path.is_file():
                source_texts[path.name] = path.read_text(errors="replace")

    index = None if no_knowledge else (KnowledgeIndex.open(db_path) if db_path.exists() else None)
    if index is None and not no_knowledge:
        typer.echo(f"(no concept index at {db_path}; formalizing without grounding)", err=True)

    client = AnthropicClient(model=model)
    # Only the live client needs a key; a test-injected replay client does not.
    if type(client).__name__ == "AnthropicClient" and not os.environ.get("ANTHROPIC_API_KEY"):
        typer.echo(
            "No ANTHROPIC_API_KEY found. Set it in your shell or a .env file at the project "
            "root (a line like ANTHROPIC_API_KEY=sk-...), then re-run `schelling formalize`.",
            err=True,
        )
        raise typer.Exit(code=2)

    out_path = output or situation.with_suffix(".draft.json")
    try:
        draft = run_formalize(
            situation_text,
            source_texts,
            client=client,
            index=index,
            model=model,
            max_retries=max_retries,
        )
    except IndexLeakageError as exc:
        quarantine = out_path.with_suffix(".quarantine.json")
        if exc.draft is not None:
            quarantine.write_text(exc.draft.model_dump_json(indent=2) + "\n")
        locs = "; ".join(f"{leak.phrase!r} in {leak.location}" for leak in exc.leaks[:6])
        typer.echo(
            f"Blocked: concept-library phrases leaked into factual fields — {locs}", err=True
        )
        typer.echo(f"Rejected draft quarantined at {quarantine} for inspection.", err=True)
        raise typer.Exit(code=2) from exc
    except ImportError as exc:
        typer.echo(f"{_KNOWLEDGE_HINT} Or pass --no-knowledge to formalize ungrounded.", err=True)
        raise typer.Exit(code=2) from exc

    out_path.write_text(draft.model_dump_json(indent=2) + "\n")
    typer.echo(_render_draft(draft))
    typer.echo("")
    typer.echo(f"Draft written: {out_path}")
    typer.echo("This is a DRAFT — edit the JSON, then run `schelling solve` to forecast.")


@app.command()
def report(
    artifact: Path = typer.Argument(..., help="A DraftGameSpec or ForecastRecord JSON."),
    output: Path | None = typer.Option(None, "-o", "--output", help="Where to write the HTML."),
    open_browser: bool = typer.Option(False, "--open", help="Open the report in a browser."),
) -> None:
    """Render an artifact to a single self-contained HTML report (offline, deterministic)."""
    if not artifact.exists():
        typer.echo(f"artifact not found: {artifact}", err=True)
        raise typer.Exit(code=2)
    try:
        data = json.loads(artifact.read_text())
        html = render_report(data)
    except (json.JSONDecodeError, ValueError) as exc:
        typer.echo(f"could not render {artifact}: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    out_path = output or artifact.with_suffix(".report.html")
    out_path.write_text(html)
    typer.echo(f"Report written: {out_path}")
    if open_browser:
        webbrowser.open(out_path.resolve().as_uri())


@app.command()
def advise(
    fixture: Path = typer.Argument(..., help="A GameSpec or DraftGameSpec JSON."),
    actor: str = typer.Option(..., "--actor", help="The advising actor's id."),
    draws_per_candidate: int = typer.Option(2000, "--draws-per-candidate", min=1),
    seed: int = typer.Option(42, "--seed"),
    target_draws: int = typer.Option(10000, "--target-draws", min=1),
    grid_step: float = typer.Option(5.0, "--grid-step", min=0.1),
    salience_floor: float = typer.Option(20.0, "--salience-floor", min=0.0, max=100.0),
    out_dir: Path = typer.Option(Path("runs"), "--out-dir"),
) -> None:
    """Find levers for one actor: own moves + who to persuade. Writes an AdviseRecord to runs/."""
    if not fixture.exists():
        typer.echo(f"input not found: {fixture}", err=True)
        raise typer.Exit(code=2)
    try:
        game, _assumptions, _fm = _load_solve_input(fixture)
        record, baseline = run_advise(
            game,
            actor,
            draws_per_candidate=draws_per_candidate,
            target_draws=target_draws,
            seed=seed,
            grid_step=grid_step,
            salience_floor=salience_floor,
        )
    except ValueError as exc:  # bad JSON/schema, or unknown actor id
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    write_record(baseline, out_dir)  # the baseline ForecastRecord reference
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{record.run_id}.json"
    out.write_text(record.model_dump_json(indent=2) + "\n")

    typer.echo(
        f"Advising:  {record.advising_actor}  (ideal {record.ideal:g}, "
        f"baseline settlement {record.baseline_median:.3f})"
    )
    typer.echo("")
    typer.echo("Top own moves (benefit toward ideal / cost conceded):")
    for mv in record.top_moves:
        flag = "  [beyond stated range]" if mv.beyond_stated_range else ""
        typer.echo(
            f"  {mv.dimension} -> {mv.value:g}: settle {mv.settlement_median:.3f}  "
            f"benefit {mv.benefit:+.3f}  cost {mv.cost:g}{flag}"
        )
    typer.echo("")
    typer.echo("Top persuasion targets (who to work on):")
    for t in record.persuasion_targets[:5]:
        typer.echo(
            f"  {t.actor_id}.{t.dimension} {t.from_value:g}->{t.to_value:g}: "
            f"settle {t.settlement_median:.3f}  benefit {t.benefit:+.3f}"
        )
    typer.echo("")
    typer.echo(f"AdviseRecord written: {out}")
    typer.echo(ADVISE_CAVEAT)


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
    try:
        index = KnowledgeIndex.open(db_path)
        results = index.search(query, k=k)
    except ImportError as exc:
        typer.echo(_KNOWLEDGE_HINT, err=True)
        raise typer.Exit(code=2) from exc
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
    try:
        index = KnowledgeIndex.build_from_transcripts(
            transcripts, embedder=make_embedder(embedder), db_path=db_path
        )
    except ImportError as exc:
        typer.echo(_KNOWLEDGE_HINT, err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"indexed {index.count()} chunks -> {db_path}")


if __name__ == "__main__":  # pragma: no cover
    app()
