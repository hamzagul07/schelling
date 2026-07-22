"""The LLM judgment baseline (Session 27): ask a model directly, no solver, no game math (D27.1).

The model is given the SAME situation text, sources, and continuum the solver received, and asked
for a settlement point, an 80% interval, and — when the rubric is banded — a probability per band.
It is sampled ``n`` times; the headline is the median of the sampled points and the spread is the
self-consistency. Non-deterministic by nature, so the record's file SHA-256 is the commitment.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from pathlib import Path

from schelling.formalizer.client import LLMClient, Message, cost_usd
from schelling.schemas.forecast import Ensemble, LLMForecastRecord, LLMSample
from schelling.schemas.question import GameSpec

_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)
_MAX_TOKENS = 1500
DEFAULT_SAMPLES = 5
DEFAULT_TEMPERATURE = 1.0


class LLMForecastError(RuntimeError):
    """A sample could not be parsed into a point/interval, or no usable sample was produced."""


def game_context(game: GameSpec) -> str:
    """The situation text a judge is shown — derived from the game, matching the solver's inputs."""
    c = game.continuum
    lines = [
        f"QUESTION {game.question_id}",
        f"CONTINUUM (the 0-100 scale): {c.label}.",
        f"  0 = {c.anchor_0}.",
        f"  100 = {c.anchor_100}.",
        f"HORIZON: {game.horizon}.",
    ]
    if game.notes:
        lines.append(f"NOTES: {game.notes}")
    lines.append("ACTORS (as the solver received them):")
    for a in game.actors:
        lines.append(
            f"- {a.name}: position {a.position.mode:g}, salience {a.salience.mode:g}, "
            f"capability {a.capability.mode:g}"
        )
        for ev in a.evidence:
            lines.append(f"    * {ev.note} — {ev.source}, {ev.date}")
    return "\n".join(lines)


def _band_labels(game: GameSpec) -> list[str]:
    r = game.resolution_rubric
    return [b.label for b in r.bands] if r is not None else []


def build_prompt(game: GameSpec, sources_text: str) -> tuple[str, str]:
    """The (system, user) prompt: a direct settlement point, 80% interval, and band probs."""
    bands = _band_labels(game)
    system = (
        "You are a forecasting analyst. You are given a situation and a 0-100 outcome scale. Judge "
        "directly where the outcome will land — do NOT run any model or arithmetic; use your own "
        "reasoning. Reply with ONLY a JSON object and nothing else:\n"
        '{"point": <0-100 settlement point>, "p10": <80% interval low>, "p90": <80% interval high>'
    )
    if bands:
        system += ', "bands": {' + ", ".join(f'"{b}": <probability 0-1>' for b in bands) + "}"
    system += "}\nProbabilities across the bands must sum to about 1."
    user = game_context(game)
    if sources_text.strip():
        user += "\n\nFETCHED SOURCES:\n" + sources_text.strip()
    user += "\n\nReturn only the JSON object."
    return system, user


def parse_sample(text: str, band_labels: list[str]) -> LLMSample:
    """Parse a model response into an :class:`LLMSample`; raise on a missing point/interval."""
    m = _JSON_OBJ.search(text)
    if m is None:
        raise LLMForecastError("no JSON object in the model response")
    try:
        obj = json.loads(m.group(0))
        point = float(obj["point"])
        p10 = float(obj["p10"])
        p90 = float(obj["p90"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise LLMForecastError(f"unparseable judgment: {exc}") from exc
    raw_bands = obj.get("bands") or {}
    bands = {b: float(raw_bands[b]) for b in band_labels if b in raw_bands}
    return LLMSample(
        point=point, p10=min(p10, p90), p90=max(p10, p90), band_probabilities=bands, raw_text=text
    )


def _aggregate(
    samples: list[LLMSample], band_labels: list[str]
) -> tuple[Ensemble, dict[str, float]]:
    points = [s.point for s in samples]
    ens = Ensemble(
        median=float(statistics.median(points)),
        mean=float(statistics.fmean(points)),
        p10=float(statistics.median([s.p10 for s in samples])),
        p90=float(statistics.median([s.p90 for s in samples])),
        n_draws=len(samples),
    )
    bands: dict[str, float] = {}
    for label in band_labels:
        vals = [s.band_probabilities[label] for s in samples if label in s.band_probabilities]
        if vals:
            bands[label] = float(statistics.fmean(vals))
    total = sum(bands.values())
    if total > 0:  # normalise so the aggregate distribution sums to 1
        bands = {k: v / total for k, v in bands.items()}
    return ens, bands


def detect_contamination(source_path: Path, game: GameSpec) -> tuple[bool, str]:
    """Flag a run whose outcomes the model may already know (DEU / the coercive library, D27.5)."""
    hay = f"{source_path}".lower() + " " + game.question_id.lower() + " " + game.template.lower()
    for marker, what in (("deu", "the DEU dataset"), ("coercive", "the coercive case library")):
        if marker in hay:
            return True, (
                f"Input resembles {what}; the model may know the historical outcome. This is a "
                "CONTAMINATION-RISK run — report it separately from live sealed forecasts."
            )
    return False, ""


def _inputs_hash(game: GameSpec, judge_model: str, temperature: float, n: int) -> str:
    payload = {
        "game": game.model_dump(mode="json", exclude={"resolution_rubric", "non_voting_actor_ids"}),
        "judge": {"model": judge_model, "temperature": temperature, "n": n},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def llm_forecast(
    client: LLMClient,
    game: GameSpec,
    *,
    sources_text: str = "",
    source_path: Path | None = None,
    n_samples: int = DEFAULT_SAMPLES,
    temperature: float = DEFAULT_TEMPERATURE,
    contamination_override: bool | None = None,
    engine_version: str = "",
    created_at: str | None = None,
) -> LLMForecastRecord:
    """Sample ``n`` independent judgments and assemble the record (D27.1-D27.2)."""
    system, user = build_prompt(game, sources_text)
    prompt_hash = hashlib.sha256((system + "\x1f" + user).encode("utf-8")).hexdigest()
    labels = _band_labels(game)
    samples: list[LLMSample] = []
    cost = 0.0
    for _ in range(n_samples):
        result = client.complete(
            system, [Message("user", user)], _MAX_TOKENS, temperature=temperature
        )
        samples.append(parse_sample(result.text, labels))
        cost += cost_usd(client.model, result.input_tokens, result.output_tokens)
    if not samples:
        raise LLMForecastError("no samples produced")
    ens, band_probs = _aggregate(samples, labels)
    pts = [s.point for s in samples]
    contam, note = detect_contamination(source_path or Path(game.question_id), game)
    if contamination_override is not None:
        contam = contamination_override
        note = note or ("Marked CONTAMINATION-RISK by the caller." if contam else "")
    ihash = _inputs_hash(game, client.model, temperature, n_samples)
    run_id = f"{game.question_id}-llm-n{n_samples}-{ihash[:12]}"
    return LLMForecastRecord(
        question_id=game.question_id,
        run_id=run_id,
        engine_version=engine_version,
        inputs_hash=ihash,
        created_at=created_at,
        judge_model=client.model,
        temperature=temperature,
        n_samples=n_samples,
        prompt_hash=prompt_hash,
        cost_usd=cost,
        ensemble=ens,
        band_probabilities=band_probs,
        self_consistency=float(max(pts) - min(pts)),
        samples=samples,
        contamination_risk=contam,
        contamination_note=note,
        game=game,
    )
