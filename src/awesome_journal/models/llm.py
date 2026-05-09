"""LLM-related Pydantic models."""
from __future__ import annotations

from pydantic import BaseModel


class LLMUsage(BaseModel):
    """Token counts and timing from a single LLM call.

    Not yet returned from generate_structured (logged only). Will be
    used when usage_log persistence is wired up.
    """

    input_tokens: int
    output_tokens: int
    latency_ms: int
