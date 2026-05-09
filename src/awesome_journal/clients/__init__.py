"""External service clients (LLM, future cache, etc.)."""

from awesome_journal.clients.base import LLMClient
from awesome_journal.clients.gemini import GeminiClient

__all__ = ["GeminiClient", "LLMClient"]
