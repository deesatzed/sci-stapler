"""Base protocol for fetch providers."""

from __future__ import annotations

from typing import Protocol

from ..models import Paper


class FetchProvider(Protocol):  # pragma: no cover
    """Protocol for source-specific full-text fetch implementations."""

    async def fetch(self, paper_id: str) -> Paper | None:
        """Fetch full paper details by ID."""
        ...
