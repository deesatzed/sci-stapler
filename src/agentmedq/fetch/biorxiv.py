"""Fetch provider for bioRxiv and medRxiv full text."""

from __future__ import annotations

import logging
import re

import httpx

from ..models import Paper, Source

logger = logging.getLogger(__name__)

# Europe PMC full text endpoint
_EPMC_FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"


class BiorxivFetch:
    """Fetch full text for bioRxiv/medRxiv papers via Europe PMC."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def fetch(self, paper_id: str, source: Source = Source.BIORXIV) -> Paper | None:
        """Fetch paper by Europe PMC PPR ID or DOI.

        For preprints, Europe PMC provides full text via their fullTextXML endpoint.
        Falls back to metadata-only if full text is unavailable.
        """
        # Try to get metadata + abstract from Europe PMC search
        meta = await self._get_metadata(paper_id, source)
        if meta is None:
            return None

        # Try to get full text
        full_text = await self._get_full_text(paper_id)

        return Paper(
            paper_id=meta.get("id", paper_id),
            source=source,
            title=meta.get("title", ""),
            authors=_parse_authors(meta),
            doi=meta.get("doi"),
            date=meta.get("firstPublicationDate"),
            abstract=meta.get("abstractText"),
            journal=source.value,
            url=f"https://doi.org/{meta['doi']}" if meta.get("doi") else None,
            full_text=full_text,
        )

    async def _get_metadata(self, paper_id: str, source: Source) -> dict | None:
        """Get paper metadata from Europe PMC."""
        # If it looks like a DOI, search by DOI
        if "/" in paper_id:
            query = f'DOI:"{paper_id}"'
        else:
            query = f'EXT_ID:"{paper_id}" SRC:PPR'

        url = f"{_EPMC_FULLTEXT_URL}/search"
        params = {
            "query": query,
            "format": "json",
            "pageSize": 1,
            "resultType": "core",
        }

        try:
            resp = await self.client.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("resultList", {}).get("result", [])
            return results[0] if results else None
        except (httpx.HTTPError, IndexError, KeyError) as e:  # pragma: no cover
            logger.warning("Failed to get metadata for %s: %s", paper_id, e)
            return None

    async def _get_full_text(self, paper_id: str) -> str | None:
        """Try to get full text XML from Europe PMC."""
        # Europe PMC full text endpoint uses the PPR ID
        url = f"{_EPMC_FULLTEXT_URL}/{paper_id}/fullTextXML"

        try:
            resp = await self.client.get(url, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            # Strip XML tags to get plain text
            return _xml_to_text(resp.text)
        except httpx.HTTPError as e:  # pragma: no cover
            logger.debug("Full text not available for %s: %s", paper_id, e)
            return None


def _parse_authors(item: dict) -> list[str]:
    author_list = item.get("authorList", {}).get("author", [])
    if author_list:
        return [a.get("fullName", "") for a in author_list if a.get("fullName")]
    author_str = item.get("authorString", "")
    if author_str:
        return [a.strip().rstrip(".") for a in author_str.split(",") if a.strip()]
    return []


def _xml_to_text(xml_str: str) -> str:
    """Extract plain text from XML, preserving paragraph breaks."""
    # Remove XML tags but keep content
    text = re.sub(r"<[^>]+>", " ", xml_str)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else ""
