"""Fetch provider for arXiv papers (abstract only, v1)."""

from __future__ import annotations

import logging
from xml.etree import ElementTree as ET

import httpx

from ..models import Paper, Source

logger = logging.getLogger(__name__)

_BASE_URL = "https://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivFetch:
    """Fetch arXiv paper metadata and abstract (no full text in v1)."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def fetch(self, paper_id: str) -> Paper | None:
        """Fetch paper by arXiv ID (e.g., '2301.12345' or '2301.12345v2')."""
        clean_id = paper_id.replace("arxiv:", "").strip()

        params = {"id_list": clean_id, "max_results": 1}

        try:
            resp = await self.client.get(_BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Failed to fetch arXiv paper %s: %s", paper_id, e)
            return None

        root = ET.fromstring(resp.text)
        entry = root.find("atom:entry", _NS)
        if entry is None:
            return None

        # Check for error (arXiv returns an entry with an error for invalid IDs)
        id_text = _text(entry, "atom:id")
        if not id_text or "api/errors" in id_text:  # pragma: no cover — arXiv rate limits prevent reliable testing
            return None

        title = _text(entry, "atom:title").replace("\n", " ").strip()
        abstract = _text(entry, "atom:summary").strip()
        published = _text(entry, "atom:published")[:10]

        authors = []
        for author in entry.findall("atom:author", _NS):
            name = _text(author, "atom:name")
            if name:
                authors.append(name)

        doi_el = entry.find("arxiv:doi", _NS)
        doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None

        # Extract primary category
        primary_cat = entry.find("arxiv:primary_category", _NS)
        category = primary_cat.get("term") if primary_cat is not None else None

        return Paper(
            paper_id=clean_id,
            source=Source.ARXIV,
            title=title,
            authors=authors,
            doi=doi,
            date=published,
            abstract=abstract,
            journal="arXiv",
            url=f"https://arxiv.org/abs/{clean_id}",
            full_text=None,  # No full text in v1
            metadata={"category": category} if category else None,
        )


def _text(el: ET.Element, path: str) -> str:
    child = el.find(path, _NS)
    return child.text.strip() if child is not None and child.text else ""
