"""Models for health-check operations."""
from __future__ import annotations

from pydantic import BaseModel


class HealthStatus(BaseModel):
    """Result of a health check.

    Could expand later: db latency, version, queue depth, etc.
    """

    db_alive: bool
