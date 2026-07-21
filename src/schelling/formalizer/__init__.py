"""The formalizer (Phase 1): described situation -> reviewable DraftGameSpec.

The LLM structures; the math (the solver) predicts. Formalize never auto-solves and never
produces a probability. Every real-world claim must trace to supplied text/sources
(CLAUDE.md rule 6); a firewall enforces it.
"""

from schelling.formalizer.client import (
    AnthropicClient,
    LLMClient,
    LLMResult,
    Message,
    ReplayClient,
    cost_usd,
    replay_from_text,
)
from schelling.formalizer.firewall import (
    IndexLeakageError,
    Leak,
    assert_no_leakage,
    find_leaks,
)
from schelling.formalizer.formalize import FormalizeError, formalize
from schelling.formalizer.prompt import RULE_F, build_system_prompt, build_user_prompt
from schelling.formalizer.schemas import (
    Assumption,
    DraftExtraction,
    DraftGameSpec,
    DraftMetadata,
    TemplateClassification,
)

__all__ = [
    "RULE_F",
    "AnthropicClient",
    "Assumption",
    "DraftExtraction",
    "DraftGameSpec",
    "DraftMetadata",
    "FormalizeError",
    "IndexLeakageError",
    "LLMClient",
    "LLMResult",
    "Leak",
    "Message",
    "ReplayClient",
    "TemplateClassification",
    "assert_no_leakage",
    "build_system_prompt",
    "build_user_prompt",
    "cost_usd",
    "find_leaks",
    "formalize",
    "replay_from_text",
]
