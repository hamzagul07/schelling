"""One interface for structured evidence providers (Session 52, item 5, D52).

DBnomics, UCDP, ACLED, and the institutional archives all register HERE, behind a single registry,
rather than each becoming a separate agent tool. Every provider (a) declares what it is for, (b)
reports whether it is ``available`` given the environment (a keyless source is always available; a
key/token source is available only when its variables are set), and (c) returns
:class:`~schelling.evidence.claim.EvidenceClaim` values — never a coordinate.

The availability contract is the item-2/item-4 discipline in code: a source whose key is absent
reports ``available = False`` with the registration step to follow, so the caller can print
"unavailable" rather than degrade silently or crash.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import NamedTuple


class Availability(NamedTuple):
    """Whether a provider can be used now, and — when it cannot — the exact step to enable it."""

    available: bool
    reason: str  # empty when available; otherwise the missing keys + how to register


@dataclass(frozen=True)
class ProviderInfo:
    """A registered evidence provider: what it is, what it is for, and how to enable it."""

    name: str
    kind: str  # "indicator" | "reference-class" | "archive"
    purpose: str
    env_keys: tuple[str, ...] = ()  # required environment variables (empty = keyless)
    registration: str = ""  # where a human obtains the key/token

    def availability(self, env: Mapping[str, str]) -> Availability:
        missing = [k for k in self.env_keys if not env.get(k, "").strip()]
        if missing:
            step = f" — register at {self.registration}" if self.registration else ""
            return Availability(False, f"set {', '.join(missing)}{step}")
        return Availability(True, "")


# The registry. Adding a source is one entry here + its client module; no new top-level command.
REGISTRY: dict[str, ProviderInfo] = {
    "dbnomics": ProviderInfo(
        name="dbnomics",
        kind="indicator",
        purpose="capability & salience series (fiscal breakevens, production weights, budget "
        "dependence, GDP) from aggregated official providers",
        env_keys=(),  # keyless, free
    ),
    "ucdp": ProviderInfo(
        name="ucdp",
        kind="reference-class",
        purpose="conflict reference classes (events, dyads, one-sided violence) for outside-view "
        "base rates",
        env_keys=("UCDP_ACCESS_TOKEN",),  # portal token now required (checked 2026-08-14; HTTP 401)
        registration="https://ucdp.uu.se/apidocs/ (request a portal access token)",
    ),
    "acled": ProviderInfo(
        name="acled",
        kind="reference-class",
        purpose="disaggregated political-violence & protest events for reference classes",
        env_keys=("ACLED_API_KEY", "ACLED_EMAIL"),  # key + registered email
        registration="https://developer.acleddata.com/ (register for an API key + use your email)",
    ),
    "archive": ProviderInfo(
        name="archive",
        kind="archive",
        purpose="published session/statement records of a body (IAEA, OPEC, EU) — the precedent "
        "layer's sessions-at-risk denominator (D30.2); candidates only, a human ratifies",
        env_keys=(),  # keyless (but a body's live listing may block bots; reported per fetch)
    ),
}


def availability_report(env: Mapping[str, str]) -> list[tuple[ProviderInfo, Availability]]:
    """Every registered provider paired with whether it is usable in this environment."""
    return [(p, p.availability(env)) for p in REGISTRY.values()]
