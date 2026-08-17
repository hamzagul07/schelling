"""Regime decomposition of the DEU benchmark (Session 62, D62). POST-HOC, exploratory.

Reproduces every number in the D62 REVISION-NOTES entry from the committed DEU dataset
and the harness. Deterministic (seeded bootstraps). Nothing here is pre-registered and
no sealed value, E-tag, or paper figure is touched — it is hypothesis-generation only.

    python docs/review/regime-decomposition.py

Sections:
  CLASSIFY   binary (2 named alternatives) vs graded (>=3), ex ante from the issue spec
  2x2        {mean,median} operator x {initial,converged} positions
  DECOMP     pole/middle decomposition (+binary/graded control), oracle bound, pole-call precision
  ROBUST     iid vs dossier-clustered bootstrap; paired-diff and per-model tail trims
  ATTACKS    convex / shrink-to-mean / shrink-to-50 / linear recalibration + OLS slope
  PROPER     CRPS, Brier=reliability-RESOLUTION+uncertainty, log score on P(>=85)/P(<=15)
  PAYOFF     expected MAE vs regime-classifier accuracy; break-even and MDE-beating accuracy
"""

from __future__ import annotations

import csv
import re
import zipfile
from pathlib import Path

import numpy as np

from schelling.backtest.harness import _rp_challenge, weighted_mean_forecast
from schelling.backtest.review import load_scored_issues
from schelling.schemas.backtest import DEUIssue
from schelling.solver.config import SolverConfig
from schelling.solver.model import run

DEU = Path("data/deu")
POLE = (0.0, 100.0)
Z = 1.959964 + 0.841621  # z(.975) + z(.80): matches review.py MDE constant
MDE_ALL = 3.04
SEED = 62


def parse_poles() -> dict[int, int]:
    """DEU global case number -> count of distinct policy alternatives in Policy Scales."""
    doc = zipfile.ZipFile(DEU / "Policy_Scales_DEU_III.docx").read("word/document.xml")
    xml = doc.decode("utf-8", "replace")
    paras = [
        re.sub(r"<[^>]+>", "", "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))).strip()
        for p in re.split(r"</w:p>", xml)
    ]
    poles: dict[int, int] = {}
    cur: int | None = None
    issue_re = re.compile(r"^(\d+)\.\s+.*?\((\d+)\)\s*$")
    pole_re = re.compile(r"^(-?\d+):\s*.+")
    for line in [p for p in paras if p]:
        m = issue_re.match(line)
        if m:
            cur = int(m.group(2))
            poles[cur] = 0
        elif pole_re.match(line) and cur is not None:
            poles[cur] += 1
        else:
            cur = None
    return poles


def isnr_case() -> dict[str, int]:
    with (DEU / "Dataset_DEU_III.csv").open(newline="") as fh:
        return {r["isnr"]: int(r["isnrnmc"]) for r in csv.DictReader(fh, delimiter=";")}


def classify(iss: DEUIssue, poles: dict[int, int], case_of: dict[str, int]) -> str:
    """binary (2 named alternatives) vs graded (>=3); fallback = an interior elicited position."""
    interior = any(0.0 < a.position.mode < 100.0 for a in iss.game.actors) or (
        iss.reference_point is not None and 0.0 < iss.reference_point < 100.0
    )
    n_alt = poles.get(case_of.get(iss.issue_id, -1), 0)
    if n_alt >= 2:
        return "binary" if n_alt == 2 else "graded"
    return "graded" if interior else "binary"


def dist(iss: DEUIssue, q: float, *, converged: bool) -> tuple[np.ndarray, np.ndarray]:
    """Predictive distribution: (positions, normalized cap x salience weights)."""
    g = iss.game
    w = np.array([a.capability.mode * a.salience.mode for a in g.actors], dtype=np.float64)
    w = w / w.sum() if w.sum() > 0 else np.ones(len(g.actors)) / len(g.actors)
    if converged:
        res = run(g, SolverConfig(q=q, reference_point=iss.reference_point))
        pos = np.array(list(res.rounds[-1].positions.values()), dtype=np.float64)
    else:
        pos = np.array([a.position.mode for a in g.actors], dtype=np.float64)
    return pos, w


def crps(pos: np.ndarray, w: np.ndarray, y: float) -> float:
    e_ax = float((w * np.abs(pos - y)).sum())
    e_xx = float(0.5 * (w[:, None] * w[None, :] * np.abs(pos[:, None] - pos[None, :])).sum())
    return e_ax - e_xx


def wmedian(pos: np.ndarray, w: np.ndarray) -> float:
    order = np.argsort(pos)
    cw = np.cumsum(w[order]) / w.sum()
    return float(pos[order][min(int(np.searchsorted(cw, 0.5)), len(pos) - 1)])


def mae(a: np.ndarray) -> float:
    return float(np.mean(a)) if len(a) else float("nan")


def hit(a: np.ndarray, t: float) -> float:
    return float(np.mean(a <= t)) if len(a) else float("nan")


def iid_ci(d: np.ndarray, b: int = 10000) -> tuple[float, float, float]:
    rng = np.random.default_rng(SEED)
    m = d[rng.integers(0, len(d), size=(b, len(d)))].mean(axis=1)
    return float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def cluster_ci(d: np.ndarray, groups: np.ndarray, b: int = 10000) -> tuple[float, float, float]:
    uniq = np.unique(groups)
    by = {g: d[groups == g] for g in uniq}
    rng = np.random.default_rng(SEED)
    means = np.array(
        [
            np.concatenate([by[g] for g in uniq[rng.integers(0, len(uniq), len(uniq))]]).mean()
            for _ in range(b)
        ]
    )
    return float(d.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def murphy(f: np.ndarray, y: np.ndarray, nbins: int = 10) -> tuple[float, float, float, float]:
    ybar = float(y.mean())
    edges = np.linspace(0.0, 1.0, nbins + 1)
    b = np.clip(np.digitize(f, edges[1:-1]), 0, nbins - 1)
    rel = res = 0.0
    for k in np.unique(b):
        mk = b == k
        rel += int(mk.sum()) * (float(f[mk].mean()) - float(y[mk].mean())) ** 2
        res += int(mk.sum()) * (float(y[mk].mean()) - ybar) ** 2
    return float(((f - y) ** 2).mean()), rel / len(f), res / len(f), ybar * (1 - ybar)


def main() -> None:
    issues, q = load_scored_issues()
    chal = _rp_challenge(q)
    poles, case_of = parse_poles(), isnr_case()

    rows = []
    for iss in issues:
        y = iss.outcome
        p0, w = dist(iss, q, converged=False)
        p1, _ = dist(iss, q, converged=True)
        rows.append(
            {
                "pid": iss.proposal_id,
                "y": y,
                "cls": classify(iss, poles, case_of),
                "pole": y in POLE,
                "cf": chal(iss),
                "mf": weighted_mean_forecast(iss.game),
                "mean_conv": float((w * p1).sum()),
                "med_init": wmedian(p0, w),
                "crps0": crps(p0, w, y),
                "crps1": crps(p1, w, y),
                "phi1": float(w[p1 >= 85].sum()),
                "plo1": float(w[p1 <= 15].sum()),
                "phi0": float(w[p0 >= 85].sum()),
                "plo0": float(w[p0 <= 15].sum()),
            }
        )
    n = len(rows)
    y = np.array([r["y"] for r in rows])
    mf = np.array([r["mf"] for r in rows])
    cae = np.abs(np.array([r["cf"] for r in rows]) - y)
    mae_ = np.abs(mf - y)
    pole = np.array([r["pole"] for r in rows])
    binary = np.array([r["cls"] == "binary" for r in rows])
    pid = np.array([r["pid"] for r in rows])

    print(
        f"n={n}  Q={q:.3f}  binary={int(binary.sum())} graded={int((~binary).sum())}  "
        f"mean MAE={mae(mae_):.2f}  challenge MAE={mae(cae):.2f}"
    )

    print("\n== 2x2  operator x position vintage (cap x sal weighted) ==")
    mean_conv = np.abs(np.array([r["mean_conv"] for r in rows]) - y)
    med_init = np.abs(np.array([r["med_init"] for r in rows]) - y)
    print(
        f"  mean-init={mae(mae_):.2f}  mean-conv={mae(mean_conv):.2f}  "
        f"med-init={mae(med_init):.2f}  med-conv(challenge)={mae(cae):.2f}"
    )
    dyn, lo, hi = iid_ci(mean_conv - mae_)
    print(
        f"  dynamics on mean Δ(conv-init)={dyn:+.2f} CI[{lo:+.2f},{hi:+.2f}] (inert); "
        f"operator Δ(med-mean|conv)={mae(cae) - mae(mean_conv):+.2f}"
    )

    print("\n== DECOMP  pole/middle (+control), oracle, pole-call precision ==")
    for lbl, sel in (("pole", pole), ("middle", ~pole)):
        print(
            f"  {lbl:<6} n={int(sel.sum()):>3} chal={mae(cae[sel]):.2f} mean={mae(mae_[sel]):.2f} "
            f"hit@10 {hit(cae[sel], 10):.2f}/{hit(mae_[sel], 10):.2f}"
        )
    print(
        f"  mean's error on poles={mae_[pole].sum() / mae_.sum():.1%}; "
        f"oracle bound={mae(np.minimum(cae, mae_)):.2f}"
    )
    called = (np.array([r["cf"] for r in rows]) <= 15) | (np.array([r["cf"] for r in rows]) >= 85)
    print(
        f"  challenge pole-call precision={(pole & called).sum() / called.sum():.2f} "
        f"vs base {pole.mean():.2f}"
    )
    for c, cm in (("binary", binary), ("graded", ~binary)):
        for lbl, sel in (("pole", pole & cm), ("middle", ~pole & cm)):
            print(
                f"  {c:<6} {lbl:<6} n={int(sel.sum()):>3} chal={mae(cae[sel]):.2f} "
                f"mean={mae(mae_[sel]):.2f}"
            )

    print("\n== ROBUST  clustered bootstrap + trims ==")
    d = cae - mae_
    for label, fn in (("iid", iid_ci(d)), ("clustered", cluster_ci(d, pid))):
        print(f"  {label:<10} Δ={fn[0]:+.2f} CI[{fn[1]:+.2f},{fn[2]:+.2f}]")
    for tr in (0.05, 0.10):
        k = int(len(cae) * (1 - tr))
        print(
            f"  trim top {tr:.0%} per model: chal={np.sort(cae)[:k].mean():.2f} "
            f"mean={np.sort(mae_)[:k].mean():.2f} "
            f"gap={np.sort(cae)[:k].mean() - np.sort(mae_)[:k].mean():+.2f} (MDE {MDE_ALL})"
        )

    print("\n== ATTACKS  post-hoc in-sample transforms of the mean ==")
    grid = np.linspace(0, 1, 101)
    cf = np.array([r["cf"] for r in rows])
    for name, fam in (
        ("convex mean/challenge", [s * mf + (1 - s) * cf for s in grid]),
        ("shrink to grand mean", [mf + s * (y.mean() - mf) for s in grid]),
        ("shrink to 50", [mf + s * (50 - mf) for s in grid]),
    ):
        best = min(mae(np.abs(f - y)) for f in fam)
        print(f"  {name:<22} best MAE={best:.2f}")
    coef, *_ = np.linalg.lstsq(np.vstack([np.ones(n), mf]).T, y, rcond=None)
    fit = coef[0] + coef[1] * mf
    resid = y - fit
    se_b = float(np.sqrt((resid @ resid) / (n - 2) / ((mf - mf.mean()) ** 2).sum()))
    print(
        f"  linear recal a+b*mean MAE={mae(np.abs(fit - y)):.2f}; "
        f"OLS slope b={coef[1]:.3f} CI[{coef[1] - 1.96 * se_b:.3f},{coef[1] + 1.96 * se_b:.3f}]"
    )

    print("\n== PROPER  scores from each model's own ensemble (graded-pole cell) ==")
    for cell, sel in (
        ("graded-pole", ~binary & pole),
        ("graded-middle", ~binary & ~pole),
        ("binary-pole", binary & pole),
    ):
        idx = np.where(sel)[0]
        c0 = float(np.mean([rows[i]["crps0"] for i in idx]))
        c1 = float(np.mean([rows[i]["crps1"] for i in idx]))
        yhi = np.array([1.0 if rows[i]["y"] >= 85 else 0.0 for i in idx])
        f_ch = np.array([rows[i]["phi1"] for i in idx])
        f_co = np.array([rows[i]["phi0"] for i in idx])
        _, _, res_ch, _ = murphy(f_ch, yhi)
        _, _, res_co, _ = murphy(f_co, yhi)
        print(
            f"  {cell:<13} CRPS init(mean)={c0:.2f} settled(chal)={c1:.2f}; "
            f"RESOLUTION(>=85) chal={res_ch:.3f} mean={res_co:.3f}"
        )

    print("\n== PAYOFF  E[MAE] vs regime-classifier accuracy ==")
    for name, cm in (("pole/middle", pole), ("structural(binary)", binary)):
        good = np.where(cm, cae, mae_)
        bad = np.where(cm, mae_, cae)
        e1, e0, mm = mae(good), mae(bad), mae(mae_)
        a_be = (e0 - mm) / (e0 - e1)
        a_mde = (e0 - (mm - MDE_ALL)) / (e0 - e1)
        print(
            f"  {name:<18} E(1)={e1:.2f} E(0)={e0:.2f} break-even alpha={a_be:.2f} "
            f"MDE-beating alpha={a_mde:.2f} ({'unreachable' if a_mde > 1 else 'reachable'})"
        )


if __name__ == "__main__":
    main()
