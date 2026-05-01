"""Fetch provider for PubMed Central full text."""

from __future__ import annotations

import logging
import re
from xml.etree import ElementTree as ET

import httpx

from ..models import Paper, Source

logger = logging.getLogger(__name__)

_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class PMCFetch:
    """Fetch full text for PMC papers via NCBI efetch."""

    def __init__(self, client: httpx.AsyncClient, api_key: str | None = None):
        self.client = client
        self.api_key = api_key

    async def fetch(self, paper_id: str) -> Paper | None:
        """Fetch full paper by PMC ID (e.g., 'PMC1234567')."""
        pmc_num = paper_id.replace("PMC", "")

        params: dict = {
            "db": "pmc",
            "id": pmc_num,
            "rettype": "xml",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            resp = await self.client.get(_EFETCH_URL, params=params, timeout=30)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Failed to fetch PMC paper %s: %s", paper_id, e)
            return None

        return _parse_pmc_xml(resp.text, paper_id)


def _parse_pmc_xml(xml_str: str, paper_id: str) -> Paper | None:
    """Parse PMC full-text XML into a Paper object."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        logger.warning("Failed to parse XML for %s: %s", paper_id, e)
        return None

    article = root.find(".//article")
    if article is None:
        article = root  # Sometimes the root is the article

    # Title
    title_el = article.find(".//article-title")
    title = _element_text(title_el) if title_el is not None else ""

    # Authors
    authors: list[str] = []
    for contrib in article.findall(".//contrib[@contrib-type='author']"):
        surname = contrib.findtext("name/surname", "")
        given = contrib.findtext("name/given-names", "")
        if surname:
            authors.append(f"{given} {surname}".strip())

    # DOI
    doi = None
    for aid in article.findall(".//article-id"):
        if aid.get("pub-id-type") == "doi" and aid.text:
            doi = aid.text.strip()
            break

    # Date
    pub_date = article.find(".//pub-date[@pub-type='epub']")
    if pub_date is None:
        pub_date = article.find(".//pub-date")
    date_str = None
    if pub_date is not None:
        year = pub_date.findtext("year", "")
        month = pub_date.findtext("month", "01")
        day = pub_date.findtext("day", "01")
        if year:
            date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    # Abstract
    abstract_el = article.find(".//abstract")
    abstract = _element_text(abstract_el) if abstract_el is not None else None

    # Journal
    journal = article.findtext(".//journal-title", "")

    # Full text (body)
    body_el = article.find(".//body")
    full_text = _element_text(body_el) if body_el is not None else None

    return Paper(
        paper_id=paper_id,
        source=Source.PMC,
        title=title,
        authors=authors,
        doi=doi,
        date=date_str,
        abstract=abstract,
        journal=journal,
        url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{paper_id}/",
        full_text=full_text,
    )


def _element_text(el: ET.Element) -> str:
    """Extract all text content from an element and its children."""
    texts = []
    for item in el.itertext():
        texts.append(item.strip())
    return " ".join(t for t in texts if t)
