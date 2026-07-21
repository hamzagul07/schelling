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
from datetime import date
from pathlib import Path

import typer
from dotenv import find_dotenv, load_dotenv
from pydantic import ValidationError

from schelling.advise.search import advise as run_advise
from schelling.analog.icb import ICBAnalogIndex, to_panel
from schelling.backtest.coercive import DEFAULT_LIBRARY
from schelling.backtest.deu import load_deu_issues
from schelling.backtest.harness import run_backtest
from schelling.backtest.ledger import (
    empty_seal_ledger,
    insert_seal_row,
    record_sha256,
    seal_row,
    stamp_ledger,
)
from schelling.backtest.oracle import oracle_summary
from schelling.backtest.successor import forecast_candidate as run_forecast_candidate
from schelling.backtest.successor import leaderboard_markdown, run_successor_search
from schelling.backtest.writeup import backtest_markdown
from schelling.formalizer.client import AnthropicClient, WebSearchUnavailableError
from schelling.formalizer.firewall import IndexLeakageError
from schelling.formalizer.formalize import formalize as run_formalize
from schelling.formalizer.schemas import DraftGameSpec
from schelling.knowledge.embed import make_embedder
from schelling.knowledge.index import DEFAULT_DB_PATH, DEFAULT_TRANSCRIPTS, KnowledgeIndex
from schelling.mc.monte_carlo import forecast, write_record
from schelling.mc.sensitivity import format_tornado, zero_swing_warning
from schelling.report.render import render as render_report
from schelling.schemas.forecast import ADVISE_CAVEAT, AnalogPanel, Assumption, DraftMetadata
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


def _load_solve_input(
    path: Path,
) -> tuple[GameSpec, list[Assumption], DraftMetadata | None, bool]:
    """Load a GameSpec or a DraftGameSpec; raises ValueError with a one-sentence friendly reason.

    Returns ``(game, assumptions, formalizer_metadata, live_searched)``; the last three are empty
    for a bare GameSpec.
    """
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
        return draft.game, list(draft.assumptions), draft.metadata, draft.live_searched
    try:
        return GameSpec.model_validate(data), [], None, False
    except ValidationError as exc:
        shape = "a DraftGameSpec" if isinstance(data, dict) and "game" in data else "a GameSpec"
        raise ValueError(
            f"{path} is not a solvable game — `solve` expects a GameSpec or a DraftGameSpec "
            f"(from `schelling formalize`); this looks {shape}-shaped but invalid "
            f"({_first_error(exc)})."
        ) from exc


def _analog_panel(spec: str) -> AnalogPanel:
    """Parse ``gravity=..,violence=..,actors=..`` tags and build an ICB base-rate panel."""
    tags: dict[str, float] = {}
    for part in spec.split(","):
        key, _, val = part.partition("=")
        key = key.strip().lower()
        try:
            tags[key] = float(val)
        except ValueError as exc:
            raise ValueError(
                f"bad --analog tag {part!r}; use e.g. gravity=6,violence=3,actors=8"
            ) from exc
    missing = {"gravity", "violence", "actors"} - set(tags)
    if missing:
        raise ValueError(f"--analog needs gravity, violence and actors tags (missing {missing}).")
    result = ICBAnalogIndex.load().search(
        gravity=tags["gravity"], violence=tags["violence"], n_actors=tags["actors"]
    )
    panel = to_panel(result)
    assert isinstance(panel, AnalogPanel)
    return panel


def _formalize_or_exit(
    situation_text: str,
    source_texts: dict[str, str],
    *,
    model: str,
    max_retries: int,
    search: bool,
    max_searches: int,
    db_path: Path,
    no_knowledge: bool,
    quarantine_path: Path,
) -> DraftGameSpec:
    """Shared formalize path (client + key + index + leak/search handling); exits 2 on failure."""
    index = None if no_knowledge else (KnowledgeIndex.open(db_path) if db_path.exists() else None)
    if index is None and not no_knowledge:
        typer.echo(f"(no concept index at {db_path}; formalizing without grounding)", err=True)
    client = AnthropicClient(model=model)
    if type(client).__name__ == "AnthropicClient" and not os.environ.get("ANTHROPIC_API_KEY"):
        typer.echo(
            "No ANTHROPIC_API_KEY found. Set it in your shell or a .env file at the project "
            "root (a line like ANTHROPIC_API_KEY=sk-...), then re-run.",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        return run_formalize(
            situation_text,
            source_texts,
            client=client,
            index=index,
            model=model,
            max_retries=max_retries,
            search=search,
            max_searches=max_searches,
            today=date.today().isoformat() if search else None,
        )
    except WebSearchUnavailableError as exc:
        typer.echo(f"Web search unavailable: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except IndexLeakageError as exc:
        if exc.draft is not None:
            quarantine_path.write_text(exc.draft.model_dump_json(indent=2) + "\n")
        locs = "; ".join(f"{leak.phrase!r} in {leak.location}" for leak in exc.leaks[:6])
        typer.echo(
            f"Blocked: concept-library phrases leaked into factual fields — {locs}", err=True
        )
        typer.echo(f"Rejected draft quarantined at {quarantine_path}.", err=True)
        raise typer.Exit(code=2) from exc
    except ImportError as exc:
        typer.echo(f"{_KNOWLEDGE_HINT} Or pass --no-knowledge to formalize ungrounded.", err=True)
        raise typer.Exit(code=2) from exc


@app.command()
def analyze(
    question: str = typer.Argument(..., help="The question / situation text to formalize."),
    sources: Path | None = typer.Option(None, "--sources", help="Directory of source files."),
    search: bool = typer.Option(
        False, "--search/--no-search", help="Let the model search the web."
    ),
    solver: str = typer.Option("both", "--solver", help="challenge|compromise|both."),
    seed: int = typer.Option(42, "--seed"),
    review: bool = typer.Option(
        True, "--review/--no-review", help="Pause for human review between draft and solve."
    ),
    draws: int = typer.Option(10_000, "--draws"),
    llm_model: str = typer.Option("claude-opus-4-8", "--model"),
    max_retries: int = typer.Option(2, "--max-retries", min=0),
    max_searches: int = typer.Option(5, "--max-searches", min=1),
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db"),
    no_knowledge: bool = typer.Option(False, "--no-knowledge"),
    out_dir: Path = typer.Option(Path("runs"), "--out-dir"),
    draft_out: Path = typer.Option(Path("draft.json"), "-o", "--draft-out"),
    report_out: Path | None = typer.Option(
        None, "--report", help="Where to write the HTML report."
    ),
) -> None:
    """One command: formalize -> draft -> (human review) -> solve -> report -> summary."""
    if solver not in ("challenge", "compromise", "both"):
        typer.echo("--solver must be 'challenge', 'compromise', or 'both'.", err=True)
        raise typer.Exit(code=2)
    source_texts: dict[str, str] = {}
    if sources is not None:
        if not sources.is_dir():
            typer.echo(f"--sources is not a directory: {sources}", err=True)
            raise typer.Exit(code=2)
        for p in sorted(sources.iterdir()):
            if p.is_file():
                source_texts[p.name] = p.read_text(errors="replace")

    # 1-2. Formalize the question into a reviewable draft and write it.
    draft = _formalize_or_exit(
        question,
        source_texts,
        model=llm_model,
        max_retries=max_retries,
        search=search,
        max_searches=max_searches,
        db_path=db_path,
        no_knowledge=no_knowledge,
        quarantine_path=draft_out.with_suffix(".quarantine.json"),
    )
    draft_out.write_text(draft.model_dump_json(indent=2) + "\n")
    typer.echo(_render_draft(draft))
    typer.echo("")
    typer.echo(f"Draft written: {draft_out}")

    # 3-4. The human gate (default on): pause between draft and solve.
    if review and not typer.confirm(
        "Review the draft above (edit the JSON if needed). Solve now?", default=False
    ):
        typer.echo("Stopped before solving. Edit the draft JSON, then run `schelling solve`.")
        return

    # 5. Solve the selected model(s), carrying the draft's provenance.
    models = ["challenge", "compromise"] if solver == "both" else [solver]
    records = [
        forecast(
            draft.game,
            SolverConfig(seed=seed),
            n_draws=draws,
            seed=seed,
            out_dir=out_dir,
            assumptions=draft.assumptions,
            formalizer_metadata=draft.metadata,
            live_searched=draft.live_searched,
            model=m,
        )
        for m in models
    ]

    # 6. Render the primary report.
    report_path = report_out or (draft_out.with_suffix(".report.html"))
    report_path.write_text(render_report(json.loads(records[0].model_dump_json())))

    # 7. Five-line summary.
    by_model = {r.model: r for r in records}
    ch = by_model.get("challenge")
    typer.echo("")
    typer.echo(f"Report: {report_path}")
    med = "  ".join(f"{r.model} median {r.ensemble.median:.3f}" for r in records)
    typer.echo(f"1. medians:   {med}")
    ci = "  ".join(f"{r.model} [{r.ensemble.p10:.2f}, {r.ensemble.p90:.2f}]" for r in records)
    typer.echo(f"2. CI80:      {ci}")
    if ch is not None and ch.median_trajectory:
        gap = ch.ensemble.median - ch.median_trajectory[-1]
        mm = ch.median_trajectory[-1]
        typer.echo(f"3. mode gap:  challenge mode-game {mm:.3f} (gap {gap:+.2f})")
    else:
        typer.echo("3. mode gap:  n/a (no challenge trajectory)")
    sens = ch.sensitivity if ch is not None else (records[0].sensitivity)
    if sens:
        typer.echo(f"4. top lever: {sens[0].parameter} (swing {sens[0].swing:+.2f})")
    else:
        typer.echo("4. top lever: none (point estimates — zero sensitivity)")
    typer.echo(f"5. assumptions flagged: {len(draft.assumptions)} — review before trusting")


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
    solver: str = typer.Option(
        "both",
        "--solver",
        help="challenge|compromise|both, or a successor: gravity|regime (R1).",
    ),
    reference_point: float | None = typer.Option(
        None,
        "--reference-point",
        help="Status-quo point (used by gravity/regime and rp challenge).",
    ),
    analog: str | None = typer.Option(
        None,
        "--analog",
        help="ICB base-rate panel tags, e.g. 'gravity=6,violence=3,actors=8' (off by default).",
    ),
    out_dir: Path = typer.Option(Path("runs"), "--out-dir", help="Where the record is written."),
) -> None:
    """Solve a game (bare GameSpec or DraftGameSpec) and write the ForecastRecord(s)."""
    if not fixture.exists():
        typer.echo(f"input not found: {fixture}", err=True)
        raise typer.Exit(code=2)
    valid = ("challenge", "compromise", "both", "gravity", "regime")
    if solver not in valid:
        typer.echo(f"--solver must be one of {', '.join(valid)}.", err=True)
        raise typer.Exit(code=2)
    try:
        game, assumptions, formalizer_metadata, live_searched = _load_solve_input(fixture)
        panel = _analog_panel(analog) if analog else None
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
        reference_point=reference_point,
        seed=seed,
    )
    models = ["challenge", "compromise"] if solver == "both" else [solver]
    typer.echo(f"Question:  {game.question_id}")
    records = []
    for model in models:
        if model in ("gravity", "regime"):
            record = run_forecast_candidate(
                game, model, n_draws=draws, seed=seed, rp=reference_point, write=False
            )
        else:
            record = forecast(
                game,
                config,
                n_draws=draws,
                seed=seed,
                write=False,
                assumptions=assumptions,
                formalizer_metadata=formalizer_metadata,
                live_searched=live_searched,
                model=model,
            )
        if panel is not None:
            record = record.model_copy(update={"analog_panel": panel})
        write_record(record, out_dir)
        records.append(record)
        e = record.ensemble
        mode = record.median_trajectory[-1] if record.median_trajectory else None
        if mode is None:  # the compromise model has no deterministic round trajectory
            mode_str = "mode-game —"
        else:
            mode_str = f"mode-game {mode:.3f} (gap {e.median - mode:+.2f})"
        typer.echo(
            f"{model:<11} MC-median {e.median:.3f}   {mode_str}   mean {e.mean:.3f}   "
            f"CI80 [{e.p10:.3f}, {e.p90:.3f}]   (n={e.n_draws}, seed {seed})"
        )
    typer.echo("")
    if records[0].sensitivity:
        typer.echo(format_tornado(records[0].sensitivity))
        warning = zero_swing_warning(records[0].sensitivity)
        if warning is not None:
            typer.echo(warning)
        typer.echo("")
    if panel is not None:
        dist = "  ".join(f"{k} {v * 100:.0f}%" for k, v in panel.outcome_distribution.items())
        typer.echo(f"ICB base rate (n={panel.n}, NOT blended): {dist}")
    for record in records:
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
    if draft.live_searched:
        lines.append(
            f"Live-searched (frozen {g.frozen_at}); {len(draft.sources_fetched)} source(s) fetched:"
        )
        for s in draft.sources_fetched:
            lines.append(f"  - {s.title or s.url}  ({s.url}, retrieved {s.retrieved_at})")
        lines.append("")
    m = draft.metadata
    search_note = f"  searches={m.searches_used}" if m.searches_used else ""
    lines.append(
        f"Provenance: {m.model}  in={m.input_tokens} out={m.output_tokens} "
        f"tok  ${m.cost_usd:.4f}  retries={m.retries}{search_note}"
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
    search: bool = typer.Option(
        False, "--search/--no-search", help="Let the model search the web for current sources."
    ),
    max_searches: int = typer.Option(
        5, "--max-searches", min=1, help="Search budget for --search."
    ),
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
            search=search,
            max_searches=max_searches,
            today=date.today().isoformat() if search else None,
        )
    except WebSearchUnavailableError as exc:
        typer.echo(f"Web search unavailable: {exc}", err=True)
        raise typer.Exit(code=2) from exc
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
    grid_step: float | None = typer.Option(
        None, "--grid-step", min=0.1, help="Position sweep step (default: adaptive, span/20)."
    ),
    salience_floor: float = typer.Option(20.0, "--salience-floor", min=0.0, max=100.0),
    solver: str = typer.Option(
        "challenge", "--solver", help="challenge (simulated), compromise (exact), or both."
    ),
    out_dir: Path = typer.Option(Path("runs"), "--out-dir"),
) -> None:
    """Find levers for one actor: own moves + who to persuade. Writes an AdviseRecord to runs/."""
    if not fixture.exists():
        typer.echo(f"input not found: {fixture}", err=True)
        raise typer.Exit(code=2)
    if solver not in ("challenge", "compromise", "both"):
        typer.echo("--solver must be 'challenge', 'compromise', or 'both'.", err=True)
        raise typer.Exit(code=2)
    try:
        game, _assumptions, _fm, _ls = _load_solve_input(fixture)
        record, baseline = run_advise(
            game,
            actor,
            model=solver,
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

    lens_label = "exact weighted-mean" if record.exact else "simulated challenge"
    typer.echo(
        f"Advising:  {record.advising_actor}  (ideal {record.ideal:g}, "
        f"baseline settlement {record.baseline_median:.3f})  [{lens_label} lens]"
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
            f"  [{t.kind}] {t.actor_id}.{t.dimension} {t.from_value:g}->{t.to_value:g}: "
            f"settle {t.settlement_median:.3f}  benefit {t.benefit:+.3f}"
        )
    if record.second_lens is not None:
        s = record.second_lens
        typer.echo("")
        typer.echo(f"Exact (compromise) lens — closed-form (baseline {s.baseline_median:.3f}):")
        for mv in s.top_moves:
            typer.echo(
                f"  {mv.dimension} -> {mv.value:g}: settle {mv.settlement_median:.3f}  "
                f"benefit {mv.benefit:+.3f}  (exact)"
            )
    typer.echo("")
    typer.echo(f"AdviseRecord written: {out}")
    typer.echo(ADVISE_CAVEAT)


_DEU_CSV_NAME = "Dataset_DEU_III.csv"
_DEU_LABEL = "DEU III (doi:10.34810/data53)"


@app.command()
def backtest(
    data_dir: Path = typer.Argument(..., help="Directory holding the DEU CSV (e.g. data/deu/)."),
    draws: int = typer.Option(2000, "--draws", help="Nominal MC draws (point estimates: no-op)."),
    seed: int = typer.Option(42, "--seed"),
    capability: float = typer.Option(
        100.0, "--capability", help="Fixed capability (equal mode only)."
    ),
    capability_mode: str = typer.Option(
        "sourced", "--capability-mode", help="'sourced' (treaty regime, D10.1) or 'equal' (D9.2)."
    ),
    reference_point: bool = typer.Option(
        True,
        "--reference-point/--no-reference-point",
        help="Add the rp-anchored challenge (D10.4).",
    ),
    min_actors: int = typer.Option(3, "--min-actors", min=1),
    out_dir: Path = typer.Option(Path("runs"), "--out-dir"),
    md_out: Path = typer.Option(Path("BACKTEST.md"), "--md", help="Where to write BACKTEST.md."),
    html_out: Path | None = typer.Option(None, "--html", help="Also render an HTML report here."),
) -> None:
    """Backtest the solver + naive baselines against DEU outcomes; write BACKTEST.md + record."""
    csv_path = data_dir / _DEU_CSV_NAME if data_dir.is_dir() else data_dir
    if not csv_path.exists():
        typer.echo(
            f"DEU CSV not found at {csv_path}. Download the open-access DEU III dataset "
            f"(doi:10.34810/data53) into data/deu/ — see BACKTEST.md / README.",
            err=True,
        )
        raise typer.Exit(code=2)
    if capability_mode not in ("sourced", "equal"):
        typer.echo("--capability-mode must be 'sourced' or 'equal'.", err=True)
        raise typer.Exit(code=2)

    sourced = capability_mode == "sourced"
    issues = load_deu_issues(
        csv_path, capability=capability, sourced_capability=sourced, min_actors=min_actors
    )
    if not issues:
        typer.echo(f"no scoreable issues parsed from {csv_path}.", err=True)
        raise typer.Exit(code=2)
    # Noise-floor diagnostic (D11.0); needs enough issues for cross-validation.
    oracle = oracle_summary(issues) if sourced and len(issues) >= 40 else None
    record = run_backtest(
        issues,
        csv_path=csv_path,
        dataset_label=_DEU_LABEL,
        seed=seed,
        draws=draws,
        capability=0.0 if sourced else capability,
        capability_mode=capability_mode,
        reference_point=reference_point,
        oracle=oracle,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    record_path = out_dir / f"backtest-{record.dataset_sha256[:12]}.json"
    record_path.write_text(record.model_dump_json(indent=2) + "\n")
    # Section ownership (D18.4): `backtest` owns the report body; the LEADERBOARD block belongs to
    # `successor`. Preserve any existing leaderboard so regenerating one section never strips the
    # other (before this fix, a bare `backtest` deleted the R1 leaderboard).
    body = backtest_markdown(record)
    md_out.write_text(_preserve_leaderboard(body, md_out.read_text()) if md_out.exists() else body)
    if html_out is not None:
        html_out.write_text(render_report(json.loads(record.model_dump_json())))

    typer.echo(f"Dataset:   {record.dataset}  ({record.n_issues} issues, seed {seed})")
    typer.echo("")
    typer.echo(f"{'method':<48}{'MAE':>8}{'RMSE':>8}{'MedAE':>8}")
    for m in record.methods:
        mark = " *" if m.key == record.primary_method else ""
        typer.echo(f"{m.label[:46]:<48}{m.mae:>8.2f}{m.rmse:>8.2f}{m.median_error:>8.2f}{mark}")
    typer.echo("")
    verdict = "PASSED" if record.gate_passed else "FAILED"
    typer.echo(f"Gate {verdict}: primary must beat both {record.baseline_methods}.")
    typer.echo(f"Record: {record_path}   BACKTEST.md: {md_out}")


_LEADERBOARD_START = "<!-- LEADERBOARD:START -->"
_LEADERBOARD_END = "<!-- LEADERBOARD:END -->"


def _preserve_leaderboard(body: str, existing: str) -> str:
    """Re-attach an existing LEADERBOARD block (owned by `successor`) to a fresh `backtest` body."""
    if _LEADERBOARD_START in existing and _LEADERBOARD_END in existing:
        _, _, rest = existing.partition(_LEADERBOARD_START)
        block, _, _ = rest.partition(_LEADERBOARD_END)
        return body.rstrip() + f"\n\n{_LEADERBOARD_START}{block}{_LEADERBOARD_END}\n"
    return body


@app.command()
def successor(
    data_dir: Path = typer.Argument(..., help="Directory holding the DEU CSV (e.g. data/deu/)."),
    md_out: Path = typer.Option(Path("BACKTEST.md"), "--md", help="Living leaderboard document."),
) -> None:
    """Run the successor search (fit train, tune dev, score TEST once); update the leaderboard."""
    csv_path = data_dir / _DEU_CSV_NAME if data_dir.is_dir() else data_dir
    if not csv_path.exists():
        typer.echo(f"DEU CSV not found at {csv_path}. See BACKTEST.md / README.", err=True)
        raise typer.Exit(code=2)

    report, _a, _b = run_successor_search(csv_path)
    board = f"{_LEADERBOARD_START}\n{leaderboard_markdown(report)}{_LEADERBOARD_END}\n"
    if md_out.exists():
        text = md_out.read_text()
        if _LEADERBOARD_START in text and _LEADERBOARD_END in text:
            head, _, rest = text.partition(_LEADERBOARD_START)
            _, _, tail = rest.partition(_LEADERBOARD_END)
            text = head.rstrip() + "\n\n" + board + tail.lstrip()
        else:
            text = text.rstrip() + "\n\n" + board
        md_out.write_text(text)
    else:
        md_out.write_text(board)

    typer.echo("Successor search — TEST scored once:")
    for c in report.candidates:
        verdict = "beats compromise" if c.beats_compromise else "does NOT beat compromise"
        typer.echo(
            f"  {c.name}: TEST MAE {c.test_mae:.2f} vs {c.test_compromise_mae:.2f}  "
            f"(Δ {c.delta:+.2f} CI [{c.ci_lo:+.2f}, {c.ci_hi:+.2f}]) — {verdict}"
        )
    typer.echo(
        "A survivor is sealed to the ledger."
        if report.any_survivor
        else "No survivor — nothing sealed. The compromise model stands."
    )
    typer.echo(f"Leaderboard written to {md_out}.")


@app.command()
def coercive(
    library: Path = typer.Argument(
        DEFAULT_LIBRARY,
        help="Coercive case library (a directory of *.json case files, or one file).",
    ),
) -> None:
    """Run the pre-registered coercive head-to-head (challenge vs compromise vs successors)."""
    from schelling.backtest.coercive import head_to_head, load_library

    report = head_to_head(load_library(library))
    if report.n_cases == 0:
        typer.echo(report.note)
        typer.echo(
            "Add expert-coded case files (see data/coercive-cases/README.md for the schema) to "
            f"{library} to run the head-to-head — the classics are still the quest (D11.1)."
        )
        return
    typer.echo(f"Coercive head-to-head ({report.n_cases} cases):")
    for m in report.methods:
        typer.echo(
            f"  {m.key:<11} MAE {m.mae:6.2f}   vs compromise {m.delta_vs_compromise:+.2f} "
            f"[{m.ci_lo:+.2f}, {m.ci_hi:+.2f}]"
        )
    typer.echo(report.note)


_SEAL_HEADER = """# FORECASTS.md — the sealed forecast ledger

**Commit-reveal.** Each forecast is sealed by the SHA-256 of its `runs/` record file — a commitment
that cannot be retrofitted once the outcome is known. The record files are never committed (`runs/`
is gitignored). To verify a line, run `sha256sum runs/<file>` locally and compare the digest."""


@app.command()
def seal(
    record: Path = typer.Argument(..., help="A ForecastRecord JSON in runs/ to seal."),
    vintage: str = typer.Option("—", "--vintage", help="A vintage label for the ledger line."),
    out: Path = typer.Option(Path("FORECASTS.md"), "-o", "--out", help="The ledger file."),
    proofs_dir: Path = typer.Option(
        Path("ledger-proofs"), "--proofs-dir", help="Where OpenTimestamps proofs are stored."
    ),
) -> None:
    """Seal a forecast record into FORECASTS.md by its SHA-256 (idempotent), then timestamp it.

    Refuses to seal a forecast whose question carries no ``resolution_rubric`` (D17.1): a prediction
    that cannot be graded by a pre-registered rule has no business being sealed. On success the
    ledger is anchored with OpenTimestamps (D17.2; a soft no-op if `ots` is absent).
    """
    if not record.exists():
        typer.echo(f"record not found: {record}", err=True)
        raise typer.Exit(code=2)
    try:
        data = json.loads(record.read_text())
        median = float(data["ensemble"]["median"])
        question_id = str(data["question_id"])
        model = str(data.get("model", "challenge"))
        game = data.get("game") or {}
        frozen_at = str(game.get("frozen_at", "unknown"))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        typer.echo(f"{record} is not a readable ForecastRecord ({exc}).", err=True)
        raise typer.Exit(code=2) from exc

    sha = record_sha256(record)
    existing = out.read_text() if out.exists() else empty_seal_ledger(_SEAL_HEADER)
    if sha in existing:
        typer.echo(f"Already sealed (sha256 {sha[:12]}… present in {out}); nothing changed.")
        return
    # A new seal requires a pre-registered grading rubric on the question (D17.1).
    if not game.get("resolution_rubric"):
        typer.echo(
            f"Refusing to seal: {record}'s question has no resolution_rubric. A sealed forecast "
            f"must be gradable by a rule fixed before resolution — add a ResolutionRubric to the "
            f"game (schemas/question.py) and write GRADING-{question_id}.md, then re-seal.",
            err=True,
        )
        raise typer.Exit(code=2)

    row = seal_row(
        model=model,
        vintage=vintage,
        question_id=question_id,
        frozen_at=frozen_at,
        median=median,
        sha=sha,
    )
    updated, _changed = insert_seal_row(existing, row, sha)
    out.write_text(updated if updated.endswith("\n") else updated + "\n")
    typer.echo(f"Sealed {question_id} [{model}, {vintage}] median {median:.3f} into {out}")
    typer.echo(f"  sha256 {sha}")
    _proof, message = stamp_ledger(out, proofs_dir)
    typer.echo(f"  {message}")


@app.command()
def stamp(
    ledger: Path = typer.Option(Path("FORECASTS.md"), "--ledger", help="Ledger file to anchor."),
    proofs_dir: Path = typer.Option(
        Path("ledger-proofs"), "--proofs-dir", help="Where OpenTimestamps proofs are stored."
    ),
) -> None:
    """Anchor the ledger with OpenTimestamps without sealing anything new (D18.0).

    Re-timestamps the current ledger file and stores the proof in ``ledger-proofs/`` (content-
    addressed by the ledger's SHA-256, so re-stamping the same bytes is idempotent). Use this to
    externally anchor a ledger that was sealed before the timestamping feature existed, or after any
    correction-on-top edit. A soft no-op with a warning if the `ots` client is unavailable.
    """
    if not ledger.exists():
        typer.echo(f"ledger not found: {ledger}", err=True)
        raise typer.Exit(code=2)
    proof, message = stamp_ledger(ledger, proofs_dir)
    typer.echo(message)
    if proof is None:  # the `ots` client was unavailable or failed — nothing was anchored
        raise typer.Exit(code=1)


@app.command()
def verify(
    record: Path = typer.Argument(..., help="A sealed ForecastRecord JSON to audit."),
    ledger: Path = typer.Option(Path("FORECASTS.md"), "--ledger", help="The sealed ledger file."),
) -> None:
    """Audit a sealed forecast: hash-in-ledger, inputs-hash, and re-solve determinism (D17.3).

    The one command an outsider runs to check a prediction: it recomputes the record's SHA-256 and
    matches it against the ledger, recomputes the inputs hash, and re-solves the embedded game to
    confirm the forecast reproduces byte-for-byte. Exits non-zero if any check fails.
    """
    from schelling.backtest.verify import verify_record

    if not record.exists():
        typer.echo(f"record not found: {record}", err=True)
        raise typer.Exit(code=2)
    try:
        report = verify_record(record, ledger)
    except (ValidationError, ValueError) as exc:
        typer.echo(f"{record} is not a readable ForecastRecord ({exc}).", err=True)
        raise typer.Exit(code=2) from exc

    for check in report.checks:
        mark = "PASS" if check.passed else "FAIL"
        typer.echo(f"  [{mark}] {check.name}: {check.detail}")
    if report.ok:
        typer.echo("VERIFIED — every check passed.")
    else:
        typer.echo("FAILED — one or more checks did not pass.", err=True)
        raise typer.Exit(code=1)


def _check_evidence_drift(repo_root: Path, out_dir: Path) -> int:
    """Compare committed EVIDENCE.md to a fresh regeneration (D18.3). Returns a process exit code.

    Fails (1) if any **science** number drifted; warns (0) on provenance-only or test-count drift.
    """
    from schelling.paper.assemble import parse_evidence
    from schelling.paper.evidence import build_evidence, evidence_markdown

    committed_path = out_dir / "EVIDENCE.md"
    if not committed_path.exists():
        typer.echo(f"no committed {committed_path} to check; run without --check.", err=True)
        return 2
    bundle = build_evidence(repo_root)
    data_absent = (
        bundle.record is None
    )  # DEU data not present -> its tags can't be regenerated here
    fresh = parse_evidence(evidence_markdown(bundle))
    committed = parse_evidence(committed_path.read_text())
    science: list[str] = []
    provenance: list[str] = []
    skipped = 0
    for tag in sorted(set(fresh) | set(committed)):
        f, c = fresh.get(tag), committed.get(tag)
        if c is None:
            provenance.append(f"{tag}: new ({f['value']})")  # type: ignore[index]
        elif f is None:
            # Absent from the fresh regen: a real drop only if the data was actually present.
            if data_absent:
                skipped += 1
            else:
                science.append(f"{tag}: DROPPED (was {c['value']})")
        elif f["value"] != c["value"]:
            (provenance if tag == "E-TESTS" else science).append(
                f"{tag}: {c['value']} -> {f['value']}"
            )
        elif f["prov"] != c["prov"]:
            provenance.append(f"{tag}: provenance {c['prov']} -> {f['prov']}")
    if skipped:
        typer.echo(
            f"({skipped} data-derived tags not regenerable here — DEU data absent — skipped)"
        )
    if science:
        typer.echo(f"SCIENCE DRIFT — build fails ({len(science)}):", err=True)
        for s in science:
            typer.echo(f"  ✗ {s}", err=True)
        typer.echo("Regenerate with `schelling paper-evidence` and re-commit.", err=True)
        return 1
    if provenance:
        typer.echo(f"provenance/repro drift only — warning, not a failure ({len(provenance)}):")
        for p in provenance:
            typer.echo(f"  ~ {p}")
    else:
        typer.echo("EVIDENCE.md is in sync with HEAD — no drift.")
    return 0


@app.command("paper-evidence")
def paper_evidence(
    repo_root: Path = typer.Option(Path("."), "--repo-root", help="Repository root."),
    out_dir: Path = typer.Option(Path("paper"), "--out-dir", help="Where paper/ artifacts go."),
    check: bool = typer.Option(
        False, "--check", help="Verify committed EVIDENCE.md vs HEAD; fail on science-number drift."
    ),
) -> None:
    """Regenerate paper/EVIDENCE.md + paper/figures/ deterministically from artifacts (D14.1/2).

    Every number is computed from the repo's own artifacts (fixtures, DEU data pinned by SHA-256,
    the sealed ledger) — never hand-typed — so the evidence table and figures can be regenerated and
    diffed forever. Numbers no artifact can source are listed as open questions, never guessed. With
    ``--check`` it writes nothing: it fails the build if any science number drifted from the
    committed EVIDENCE.md, and only warns on provenance-hash or test-count drift (D18.3).
    """
    if check:
        raise typer.Exit(code=_check_evidence_drift(repo_root, out_dir))

    from schelling.paper.evidence import build_evidence, evidence_markdown
    from schelling.paper.figures import write_figures

    bundle = build_evidence(repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "EVIDENCE.md").write_text(evidence_markdown(bundle))
    figs = write_figures(out_dir / "figures", bundle.record, bundle.report)

    typer.echo(f"EVIDENCE.md: {len(bundle.items)} sourced numbers → {out_dir / 'EVIDENCE.md'}")
    typer.echo(f"figures: {len(figs)} written → {out_dir / 'figures'}")
    if figs:
        for f in figs:
            typer.echo(f"  {f}")
    if bundle.open_questions:
        typer.echo(f"open questions (unsourced): {len(bundle.open_questions)}")
        for q in bundle.open_questions:
            typer.echo(f"  - {q}")
    else:
        typer.echo("open questions: none — every cited number resolved to an artifact.")


@app.command("paper-assemble")
def paper_assemble(
    repo_root: Path = typer.Option(Path("."), "--repo-root", help="Repository root."),
    out: Path = typer.Option(Path("paper/DRAFT.md"), "-o", "--out", help="Assembled draft path."),
) -> None:
    """Assemble paper/DRAFT.md from the draft sections + EVIDENCE.md (deterministic, idempotent).

    Concatenates paper/draft/00..10 in order, resolves every [E-tag] inline to its EVIDENCE.md value
    with a provenance footnote, places the four figures at their section anchors, and appends the
    bibliography skeleton. Any E-tag EVIDENCE.md cannot resolve is left as a visible TODO.
    """
    from schelling.paper.assemble import assemble

    draft, todos, missing = assemble(repo_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(draft)
    words = len(draft.split())
    typer.echo(f"DRAFT.md: {words} words → {out}")
    if missing:
        typer.echo(f"missing inputs: {len(missing)}")
        for msg in missing:
            typer.echo(f"  - {msg}")
    if todos:
        typer.echo(f"UNRESOLVED E-tag TODOs: {len(todos)}")
        for t in todos:
            typer.echo(f"  - {t}")
    else:
        typer.echo("unresolved E-tags: none — every citation resolved to an EVIDENCE.md value.")


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
