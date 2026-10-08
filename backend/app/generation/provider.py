"""Provider interface for local text generation (IR-07).

Only local providers are allowed (ADR-0001). There is no fallback: a failing provider raises one of
the errors below, which the API maps to an explicit HTTP error.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class GenerationRequest:
    system: str
    prompt: str
    json_schema: dict[str, Any]
    """JSON Schema the output must follow (passed to the model's constrained decoding)."""


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    """Model tag that actually produced the text."""
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ms: float
    truncated: bool
    """True when generation stopped at the token limit, so the output may be incomplete."""


class GenerationProvider(Protocol):
    model_name: str
    options: dict[str, Any]
    """Generation settings (context size, token limit, temperature, seed), recorded per answer."""

    def generate(self, request: GenerationRequest) -> GenerationResult: ...
