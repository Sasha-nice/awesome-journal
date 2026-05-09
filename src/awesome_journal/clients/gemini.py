"""Gemini async client implementing the LLMClient Protocol."""
from __future__ import annotations

import logging
import time

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel, ValidationError

from awesome_journal.models.result import Result

log = logging.getLogger(__name__)


class GeminiClient:
    """Async Gemini wrapper.

    Single public method: `generate_structured(prompt, schema)`.
    Catches all exceptions; never raises.
    """

    def __init__(self, *, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def generate_structured[T: BaseModel](
        self,
        prompt: str,
        schema: type[T],
        *,
        temperature: float = 0.0,
        system_instruction: str | None = None,
    ) -> Result[T]:
        config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
            system_instruction=system_instruction,
        )

        start = time.perf_counter()
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
        except Exception as e:
            log.warning("Gemini API call failed: %s", e)
            return Result.failure(f"api error: {e}")

        latency_ms = int((time.perf_counter() - start) * 1000)

        usage = response.usage_metadata
        if usage is not None:
            log.info(
                "Gemini call: model=%s in_tokens=%s out_tokens=%s latency_ms=%d",
                self._model,
                usage.prompt_token_count,
                usage.candidates_token_count,
                latency_ms,
            )

        parsed = response.parsed
        if parsed is None:
            raw = (response.text or "").strip()
            if not raw:
                log.warning("Gemini returned empty response")
                return Result.failure("empty response")
            log.warning(
                "SDK didn't parse; falling back to manual validation. Raw: %r",
                raw[:300],
            )
            try:
                return Result.success(schema.model_validate_json(raw))
            except ValidationError as e:
                return Result.failure(f"validation error: {e}")

        if not isinstance(parsed, schema):
            return Result.failure(
                f"unexpected parsed type: {type(parsed).__name__}"
            )

        return Result.success(parsed)
