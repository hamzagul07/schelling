"""Run an elicitation ensemble: N independent formalizer drafts (Session 45, D45.1).

Each draft is a separate ``formalize`` call on the same situation — independent by nature, since the
model is not deterministic — optionally with a different judge model per draft, which is recorded in
the draft's metadata. The drafts are returned in order, each tagged with its ``draft_index`` so the
provenance of every draft in the ensemble is explicit. Reconciliation and the variance decomposition
consume these drafts; the ensemble's reproducible commitment is the set of draft hashes (D45.5).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from schelling.formalizer.client import DEFAULT_MODEL, AnthropicClient, LLMClient
from schelling.formalizer.formalize import formalize
from schelling.formalizer.schemas import DraftGameSpec
from schelling.knowledge.index import KnowledgeIndex


def _live_client(_index: int, model: str) -> LLMClient:
    return AnthropicClient(model=model)


def run_ensemble(
    situation_text: str,
    sources: dict[str, str] | None = None,
    *,
    n: int = 5,
    models: Sequence[str] | None = None,
    index: KnowledgeIndex | None = None,
    client_for: Callable[[int, str], LLMClient] = _live_client,
    max_retries: int = 2,
    search: bool = False,
    max_searches: int = 5,
    today: str | None = None,
    created_at: str | None = None,
) -> list[DraftGameSpec]:
    """Formalize ``situation_text`` ``n`` times into independent drafts (D45.1).

    ``models`` cycles a judge model per draft (default: all drafts use :data:`DEFAULT_MODEL`);
    ``client_for(index, model)`` supplies the LLM client for each draft (default: a live client;
    tests inject stubs). Each returned draft carries its ``draft_index`` in the metadata.
    """
    if n < 1:
        raise ValueError("ensemble size n must be at least 1")
    model_cycle = list(models) if models else [DEFAULT_MODEL]
    drafts: list[DraftGameSpec] = []
    for i in range(n):
        model_i = model_cycle[i % len(model_cycle)]
        draft = formalize(
            situation_text,
            sources,
            client=client_for(i, model_i),
            index=index,
            model=model_i,
            max_retries=max_retries,
            search=search,
            max_searches=max_searches,
            today=today,
            created_at=created_at,
        )
        tagged = draft.metadata.model_copy(update={"draft_index": i})
        drafts.append(draft.model_copy(update={"metadata": tagged}))
    return drafts
