"""Base protocol for search providers."""

from __future__ import annotations

from typing import Protocol

from ..models import SearchResult


class SearchProvider(Protocol):  # pragma: no cover
    """Protocol for source-specific search implementations."""

    async def search(
        self,
        query: str,
        limit: int = 20,
        **kwargs,
    ) -> list[SearchResult]:
        """Search for papers matching the query."""
        ...
