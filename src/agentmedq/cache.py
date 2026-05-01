"""SQLite cache layer with TTL support."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .models import Paper, SearchResult, Source

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_cache (
    query_hash TEXT NOT NULL,
    source TEXT NOT NULL,
    results_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (query_hash, source)
);

CREATE TABLE IF NOT EXISTS papers (
    paper_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT,
    authors_json TEXT,
    doi TEXT,
    date TEXT,
    abstract TEXT,
    journal TEXT,
    url TEXT,
    full_text TEXT,
    metadata_json TEXT,
    cached_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _query_hash(query: str, source: str, limit: int) -> str:
    raw = f"{query.strip().lower()}|{source}|{limit}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _seconds_since(iso_str: str) -> float:
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()


class Cache:
    """Async SQLite cache with TTL-based expiry."""

    def __init__(self, db_path: str | Path, search_ttl: int = 86400, paper_ttl: int = 2592000):
        self.db_path = str(db_path)
        self.search_ttl = search_ttl
        self.paper_ttl = paper_ttl
        self._db: aiosqlite.Connection | None = None

    async def init_db(self) -> None:
        """Initialize the database and create tables."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Cache not initialized. Call init_db() first.")
        return self._db

    # -- Search cache --

    async def get_search(
        self, query: str, source: str, limit: int
    ) -> list[SearchResult] | None:
        """Get cached search results if fresh. Returns None if expired or missing."""
        h = _query_hash(query, source, limit)
        cursor = await self.db.execute(
            "SELECT results_json, created_at FROM search_cache WHERE query_hash = ? AND source = ?",
            (h, source),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        results_json, created_at = row
        if _seconds_since(created_at) > self.search_ttl:
            await self.db.execute(
                "DELETE FROM search_cache WHERE query_hash = ? AND source = ?", (h, source)
            )
            await self.db.commit()
            return None

        data = json.loads(results_json)
        return [SearchResult.model_validate(r) for r in data]

    async def put_search(
        self, query: str, source: str, limit: int, results: list[SearchResult]
    ) -> None:
        """Cache search results."""
        h = _query_hash(query, source, limit)
        results_json = json.dumps([r.model_dump(mode="json") for r in results])
        await self.db.execute(
            """INSERT OR REPLACE INTO search_cache (query_hash, source, results_json, created_at)
               VALUES (?, ?, ?, ?)""",
            (h, source, results_json, _now_iso()),
        )
        await self.db.commit()

    # -- Paper cache --

    async def get_paper(self, paper_id: str) -> Paper | None:
        """Get cached paper if fresh. Returns None if expired or missing."""
        cursor = await self.db.execute(
            "SELECT * FROM papers WHERE paper_id = ?", (paper_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        cols = [d[0] for d in cursor.description]
        data = dict(zip(cols, row))

        if _seconds_since(data["cached_at"]) > self.paper_ttl:
            await self.db.execute("DELETE FROM papers WHERE paper_id = ?", (paper_id,))
            await self.db.commit()
            return None

        authors = json.loads(data["authors_json"]) if data["authors_json"] else []
        metadata = json.loads(data["metadata_json"]) if data["metadata_json"] else None

        return Paper(
            paper_id=data["paper_id"],
            source=Source(data["source"]),
            title=data["title"] or "",
            authors=authors,
            doi=data["doi"],
            date=data["date"],
            abstract=data["abstract"],
            journal=data["journal"],
            url=data["url"],
            full_text=data["full_text"],
            metadata=metadata,
            cached_at=datetime.fromisoformat(data["cached_at"]),
        )

    async def put_paper(self, paper: Paper) -> None:
        """Cache a paper."""
        await self.db.execute(
            """INSERT OR REPLACE INTO papers
               (paper_id, source, title, authors_json, doi, date, abstract,
                journal, url, full_text, metadata_json, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                paper.paper_id,
                paper.source.value,
                paper.title,
                json.dumps(paper.authors),
                paper.doi,
                paper.date,
                paper.abstract,
                paper.journal,
                paper.url,
                paper.full_text,
                json.dumps(paper.metadata) if paper.metadata else None,
                _now_iso(),
            ),
        )
        await self.db.commit()

    async def get_paper_by_doi(self, doi: str) -> Paper | None:
        """Look up cached paper by DOI."""
        cursor = await self.db.execute(
            "SELECT paper_id FROM papers WHERE doi = ?", (doi,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return await self.get_paper(row[0])
