"""Unit tests for GeminiClient. Mocks google.genai.Client."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from awesome_journal.clients.gemini import GeminiClient


class _DummySchema(BaseModel):
    value: int
    label: str


@pytest.fixture
def mock_generate(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patch `genai.Client` so no network is touched.

    Returns the underlying `generate_content` AsyncMock so each test
    sets `return_value` / `side_effect` on it directly (avoiding
    method-assignment problems mypy doesn't like).
    """
    fake_genai_client = MagicMock(name="genai.Client")
    fake_genai_client.aio.models.generate_content = AsyncMock(name="generate_content")
    monkeypatch.setattr(
        "awesome_journal.clients.gemini.genai.Client",
        lambda **_: fake_genai_client,
    )
    generate: AsyncMock = fake_genai_client.aio.models.generate_content
    return generate


@pytest.fixture
def gemini_client(mock_generate: AsyncMock) -> GeminiClient:
    return GeminiClient(api_key="dummy-key", model="gemini-2.5-flash")


def _mock_response(*, parsed: object | None = None, text: str = "") -> MagicMock:
    """Mock the response shape from google-genai."""
    response = MagicMock()
    response.parsed = parsed
    response.text = text
    response.usage_metadata = MagicMock(
        prompt_token_count=10,
        candidates_token_count=20,
    )
    return response


async def test_returns_success_when_sdk_parses(
    gemini_client: GeminiClient,
    mock_generate: AsyncMock,
) -> None:
    expected = _DummySchema(value=42, label="hello")
    mock_generate.return_value = _mock_response(parsed=expected)

    result = await gemini_client.generate_structured("anything", _DummySchema)

    assert result.ok is True
    assert result.value == expected


async def test_returns_failure_when_api_raises(
    gemini_client: GeminiClient,
    mock_generate: AsyncMock,
) -> None:
    mock_generate.side_effect = RuntimeError("network down")

    result = await gemini_client.generate_structured("anything", _DummySchema)

    assert result.ok is False
    assert "network down" in (result.error or "")


async def test_falls_back_to_text_validation_when_parsed_is_none(
    gemini_client: GeminiClient,
    mock_generate: AsyncMock,
) -> None:
    raw_json = '{"value": 7, "label": "fallback"}'
    mock_generate.return_value = _mock_response(parsed=None, text=raw_json)

    result = await gemini_client.generate_structured("anything", _DummySchema)

    assert result.ok is True
    assert result.value == _DummySchema(value=7, label="fallback")


async def test_returns_failure_on_invalid_json(
    gemini_client: GeminiClient,
    mock_generate: AsyncMock,
) -> None:
    mock_generate.return_value = _mock_response(parsed=None, text="not json at all")

    result = await gemini_client.generate_structured("anything", _DummySchema)

    assert result.ok is False
    assert "validation" in (result.error or "").lower()


async def test_returns_failure_on_empty_response(
    gemini_client: GeminiClient,
    mock_generate: AsyncMock,
) -> None:
    mock_generate.return_value = _mock_response(parsed=None, text="")

    result = await gemini_client.generate_structured("anything", _DummySchema)

    assert result.ok is False
    assert "empty" in (result.error or "").lower()
