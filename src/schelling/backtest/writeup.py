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

    cap_txt = (
        "sourced treaty-regime Council power (Session 10, D10.1)"
        if record.capability_mode == "sourced"
        else f"equal capability {record.capability:g} (Session 9, D9.2)"
    )

    out: list[str] = []
    out.append("# BACKTEST.md — DEU benchmark (living document)")
    out.append("")
    out.append(
        f"Deterministic backtest of the solver against **{record.n_issues}** resolved issues from "
        f"the {record.dataset}. Every issue is a point-estimate game solved deterministically; "
        f"live search is off (a frozen historical benchmark, CLAUDE.md rule 7). Capabilities: "
        f"{cap_txt}."
    )
    out.append("")
    out.append("## The gate (fixed in advance)")
    out.append("")
    if record.reference_point_used:
        out.append(
            "> **Gate v2 (Session 10, immovable):** with real capabilities and the reference "
            "point, the challenge solver must beat the equally-equipped weighted mean on DEU MAE. "
            "Any model change beyond restoring inputs is validated split-sample."
        )
    else:
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
        f"The primary challenge model ({primary.label.split('—')[-1].strip()}) has MAE "
        f"**{primary.mae:.2f}**. Baselines: {b_txt}. "
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
    if record.split_sample is not None:
        s = record.split_sample
        verb = "beats" if s.passed else "does NOT beat"
        out.append("## Split-sample validation (item 4)")
        out.append("")
        out.append(
            f"The rp-anchored challenge's **{s.tuned_param}** was tuned on {s.train_n} training "
            f"issues (candidates {', '.join(f'{c:g}' for c in s.candidates)}) → selected "
            f"**{s.selected:g}** (train MAE {s.train_mae:.2f}), then scored on {s.test_n} held-out "
            f"issues: test MAE **{s.test_mae:.2f}** vs the equally-equipped weighted mean "
            f"**{s.test_baseline_mae:.2f}**. On the held-out half the tuned model {verb} the "
            f"weighted mean — the reference point is a real, non-overfit improvement, but "
            f"{'' if s.passed else 'still '}insufficient."
        )
        out.append("")
    if record.oracle is not None:
        o = record.oracle
        near = "at/near the ceiling" if o.gap <= 1.0 else f"below the ceiling by {o.gap:.2f}"
        out.append("## Noise-floor oracle (DIAGNOSTIC, D11.0)")
        out.append("")
        out.append(
            f"A deliberately flexible cross-validated model ({o.best_model}, {o.folds}-fold, rich "
            f"features incl. positions) scores MAE **{o.oracle_mae:.2f}** — an estimate of the "
            f"extractable-signal ceiling. The compromise mean scores **{o.compromise_mae:.2f}**, "
            f"so the gap is **{o.gap:+.2f}**: the mean is **{near}**. "
            + (
                "Even an optimistic flexible model does not beat the mean — there is essentially "
                "no signal beyond the influence-weighted average, which is why every model we "
                "have tried fails to beat it."
                if o.gap <= 1.0
                else "There is some headroom a better model might exploit."
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
    if record.capability_mode == "sourced":
        out.append(
            "- **Capability (sourced, D10.1).** DEU records no capability, so each member state "
            "takes its Council power in the treaty regime in force at the issue's decision date "
            "(pre-Nice / Nice weighted votes; Lisbon-era population), rescaled so the strongest "
            "actor = 100; Commission/EP each take the largest member-state power (D10.3). The same "
            "table feeds the challenge solver AND the weighted-mean baseline — a fair fight."
        )
    else:
        out.append(
            f"- **Capability (equal, D9.2).** DEU records no capability, so every actor gets a "
            f"fixed capability of {record.capability:g}. The weighted-mean baseline is then the "
            f"salience-weighted mean — a classic DEU 'compromise' model."
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
    out.append("## Domain verdicts, side by side")
    out.append("")
    out.append("| Domain | Benchmark | Verdict |")
    out.append("|---|---|---|")
    out.append(
        f"| Cooperative (EU legislative) | DEU III, {record.n_issues} issues | **Compromise mean "
        f"wins.** The challenge solver loses even fully equipped; the noise-floor oracle shows the "
        f"mean is at the extractable-signal ceiling. |"
    )
    out.append(
        "| Coercive (interstate crises) | Coercive library | **PENDING.** The expert-coded "
        "coercive tables (Hong Kong 1985, Iran 1984, ...) are in paywalled books; the harness is "
        "built and waits on the printed inputs (D11.1). |"
    )
    out.append("")
    out.append("## Coercive contenders")
    out.append("")
    out.append("| Model | Status | Result |")
    out.append("|---|---|---|")
    out.append(
        "| Challenge (BDM), compromise mean, gravity, regime | scored when cases arrive | awaiting "
        "the coercive library |"
    )
    out.append(
        "| **Model Three — Asabiyyah (MT-1.0)** | **PRE-REGISTERED — awaiting the reading** | "
        "Specification sealed ([`specs/MT-1.0.md`](specs/MT-1.0.md), D20.0) while the "
        "library holds "
        "two verified cases, none coercive. Scored **once**, at the 8-verified-case "
        "reading. **Gate "
        '(§6, verbatim):** *"Primary: at the pre-registered 8-verified-case coercive '
        "reading, MT-1.0 "
        "must beat the unadjusted compromise mean on MAE, reported with paired bootstrap "
        "intervals. "
        "… Negative results are published with the same prominence as positive ones. If MT-1.0 "
        "fails, it is retired exactly as R1's candidates were; its committed specification "
        "remains as "
        'the record that the theory stated its claim before the evidence existed."* |'
    )
    out.append("")
    out.append("## Scheduled next: the ICB coercive benchmark")
    out.append("")
    out.append(
        "EU legislative bargaining is a highly cooperative, consensual setting — the one BdM "
        "(2011) notes his model handles *worst*. The challenge model is built for competitive, "
        "coercive politics. So regardless of this verdict, the next benchmark is the International "
        "Crisis Behavior (ICB) dataset — coercive interstate crises — where the mechanism should "
        "have its best shot. Whether it clears there decides far more than this cooperative case."
    )
    out.append("")
    return "\n".join(out) + "\n"
