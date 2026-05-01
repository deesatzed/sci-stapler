"""OpenAlex API search provider."""

from __future__ import annotations

import logging

import httpx

from ..models import SearchResult, Source

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.openalex.org/works"


class OpenAlexSearch:
    """Search OpenAlex for abstracts across ~50M works."""

    def __init__(self, client: httpx.AsyncClient, email: str | None = None):
        self.client = client
        self.email = email

    async def search(
        self,
        query: str,
        limit: int = 20,
        **kwargs,
    ) -> list[SearchResult]:
        params: dict = {
            "search": query,
            "per_page": min(limit, 50),
            "select": "id,doi,title,authorships,publication_date,primary_location,abstract_inverted_index",
        }
        if self.email:
            params["mailto"] = self.email

        resp = await self.client.get(_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        results: list[SearchResult] = []
        for item in data.get("results", []):
            doi = item.get("doi")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi[len("https://doi.org/"):]

            authors = []
            for authorship in item.get("authorships", []):
                author = authorship.get("author", {})
                name = author.get("display_name", "")
                if name:
                    authors.append(name)

            abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))

            journal = None
            primary = item.get("primary_location")
            if primary and primary.get("source"):
                journal = primary["source"].get("display_name")

            openalex_id = item.get("id", "")
            if openalex_id.startswith("https://openalex.org/"):
                openalex_id = openalex_id.split("/")[-1]

            results.append(
                SearchResult(
                    paper_id=openalex_id,
                    source=Source.OPENALEX,
                    title=item.get("title", ""),
                    authors=authors,
                    doi=doi,
                    date=item.get("publication_date"),
                    abstract=abstract,
                    journal=journal,
                    url=f"https://doi.org/{doi}" if doi else None,
                )
            )

        return results[:limit]


def _reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return None

    words: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))

    words.sort(key=lambda x: x[0])
    return " ".join(w for _, w in words)
