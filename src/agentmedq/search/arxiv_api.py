"""arXiv API search provider."""

from __future__ import annotations

import logging
from xml.etree import ElementTree as ET

import httpx

from ..models import SearchResult, Source

logger = logging.getLogger(__name__)

_BASE_URL = "https://export.arxiv.org/api/query"

# arXiv Atom namespace
_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivSearch:
    """Search arXiv via the native Atom API."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search(
        self,
        query: str,
        limit: int = 20,
        **kwargs,
    ) -> list[SearchResult]:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(limit, 100),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        resp = await self.client.get(_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        results: list[SearchResult] = []

        for entry in root.findall("atom:entry", _NS):
            arxiv_id = _extract_arxiv_id(entry)
            title = _text(entry, "atom:title").replace("\n", " ").strip()
            abstract = _text(entry, "atom:summary").strip()
            published = _text(entry, "atom:published")[:10]  # YYYY-MM-DD

            authors = []
            for author in entry.findall("atom:author", _NS):
                name = _text(author, "atom:name")
                if name:
                    authors.append(name)

            doi_el = entry.find("arxiv:doi", _NS)
            doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None

            results.append(
                SearchResult(
                    paper_id=arxiv_id,
                    source=Source.ARXIV,
                    title=title,
                    authors=authors,
                    doi=doi,
                    date=published,
                    abstract=abstract,
                    journal="arXiv",
                    url=f"https://arxiv.org/abs/{arxiv_id}",
                )
            )

        return results[:limit]


def _text(el: ET.Element, path: str) -> str:
    child = el.find(path, _NS)
    return child.text.strip() if child is not None and child.text else ""


def _extract_arxiv_id(entry: ET.Element) -> str:
    id_text = _text(entry, "atom:id")
    # Format: http://arxiv.org/abs/XXXX.XXXXX[vN]
    if "/abs/" in id_text:
        return id_text.split("/abs/")[-1]
    return id_text
