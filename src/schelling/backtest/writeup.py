"""Render a :class:`BacktestRecord` to the ``BACKTEST.md`` write-up (deterministic).

A negative finding is a finding (CLAUDE.md-adjacent honesty): the gate is stated first, then the
verdict, then the full per-method table, the worst issues, and the published context we could find.
"""

from __future__ import annotations

from schelling.backtest.context import CITATIONS, CONTEXT_PROSE, PUBLISHED_RESULTS
from schelling.schemas.backtest import BacktestRecord, MethodResult


def _method_by_key(record: BacktestRecord, key: str) -> MethodResult:
    return next(m for m in record.methods if m.key == key)


def _mae_table(record: BacktestRecord) -> list[str]:
    lines = ["| Method | Kind | MAE | RMSE | Median AE | Max AE |", "|---|---|---:|---:|---:|---:|"]
    for m in record.methods:
        star = " ★" if m.key == record.primary_method else ""
        lines.append(
            f"| {m.label}{star} | {m.kind} | {m.mae:.2f} | {m.rmse:.2f} | "
            f"{m.median_error:.2f} | {m.max_error:.2f} |"
        )
    return lines


def backtest_markdown(record: BacktestRecord) -> str:
    primary = _method_by_key(record, record.primary_method)
    baselines = [_method_by_key(record, k) for k in record.baseline_methods]
    verdict = "PASSED ✅" if record.gate_passed else "FAILED ❌"

    out: list[str] = []
    out.append("# BACKTEST.md — DEU benchmark")
    out.append("")
    out.append(
        f"Deterministic backtest of the solver against **{record.n_issues}** resolved issues from "
        f"the {record.dataset}. Every issue is a point-estimate game solved deterministically; "
        f"live search is off (a frozen historical benchmark, CLAUDE.md rule 7)."
    )
    out.append("")
    out.append("## The gate (fixed in advance)")
    out.append("")
    out.append(
        "> The solver (paper-faithful config) must beat **both** naive baselines — the "
        "capability x salience weighted mean and the median actor position — on MAE across the "
        "full issue set. If it does not, the result is written up honestly here."
    )
    out.append("")
    out.append(f"**Verdict: {verdict}.**")
    out.append("")
    b_txt = ", ".join(f"{b.label.split('—')[-1].strip()} = {b.mae:.2f}" for b in baselines)
    beat = [b for b in baselines if primary.mae < b.mae]
    lost = [b for b in baselines if primary.mae >= b.mae]
    out.append(
        f"The solver's MAE is **{primary.mae:.2f}**. Baselines: {b_txt}. "
        + (
            f"It beats {len(beat)} of {len(baselines)} baselines"
            + (
                f" (loses to {', '.join(b.label.split('—')[-1].strip() for b in lost)})."
                if lost
                else "."
            )
        )
    )
    out.append("")
    out.append("## Per-method error (full issue set)")
    out.append("")
    out += _mae_table(record)
    out.append("")
    out.append("★ = the primary config the gate is judged on. Lower is better; scale is 0-100.")
    out.append("")
    out.append("## Worst issues (by the primary solver's absolute error)")
    out.append("")
    out.append("| Issue | Proposal | Forecast | Actual | Error |")
    out.append("|---|---|---:|---:|---:|")
    for w in record.worst_issues:
        name = w.proposal_name[:48]
        out.append(f"| {w.issue_id} | {name} | {w.forecast:.1f} | {w.actual:.1f} | {w.error:.1f} |")
    out.append("")
    out.append("## Published DEU model error rates, for context")
    out.append("")
    out.append(CONTEXT_PROSE)
    out.append("")
    out.append("| Published model | Mean abs. error | Subset | Source |")
    out.append("|---|---:|---|---|")
    for p in PUBLISHED_RESULTS:
        out.append(f"| {p.model} | {p.mean_abs_error:.1f} | {p.subset} | {p.source} |")
    out.append("")
    out.append(
        "These are **not** directly comparable to our numbers (different DEU version, issue "
        "subset, and capability/resolve handling); they are cited to show the regime and the "
        "known ordering, not as a like-for-like benchmark."
    )
    out.append("")
    out.append("### Citations")
    out.append("")
    for c in CITATIONS:
        out.append(f"- {c}")
    out.append("")
    out.append("## Method notes")
    out.append("")
    out.append(
        f"- **Capability.** DEU records position and salience but no capability, so every actor is "
        f"assigned a fixed capability of {record.capability:g} (D9.2). With equal capability the "
        f"weighted-mean baseline is the salience-weighted mean — a classic DEU 'compromise' model."
    )
    out.append(
        "- **Point estimates.** Each issue is point estimates, so Monte Carlo is degenerate (zero "
        f"variance, D3.1); the harness solves each issue once deterministically. `--draws` "
        f"({record.draws}) is recorded for interface parity but does not affect the result (D9.3)."
    )
    out.append(
        f"- **Determinism.** Dataset pinned by SHA-256 `{record.dataset_sha256[:16]}…`; "
        f"engine `{record.engine_version[:12]}`; seed {record.seed}. Same inputs → byte-identical "
        f"record."
    )
    out.append("")
    return "\n".join(out) + "\n"
