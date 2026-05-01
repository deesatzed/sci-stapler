"""Configuration for agentmedq."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Settings:
    """Application settings loaded from environment variables."""

    # Server
    host: str = "127.0.0.1"
    port: int = 8042

    # Cache TTLs (seconds)
    search_cache_ttl: int = 86400  # 24 hours
    paper_cache_ttl: int = 2592000  # 30 days

    # Database
    db_path: str = "./agentmedq_cache.db"

    # Optional API keys
    ncbi_api_key: str | None = None
    openalex_email: str | None = None

    # Rate limits (requests per second)
    rate_limits: dict[str, float] = field(default_factory=lambda: {
        "ncbi": 3.0,
        "arxiv": 0.33,  # 1 request per 3 seconds
        "europe_pmc": 10.0,
        "openalex": 10.0,
        "biorxiv_fetch": 5.0,
    })

    @classmethod
    def from_env(cls) -> Settings:
        """Load settings from environment variables."""
        ncbi_key = os.environ.get("NCBI_API_KEY")

        rate_limits = {
            "ncbi": 10.0 if ncbi_key else 3.0,
            "arxiv": 0.33,
            "europe_pmc": 10.0,
            "openalex": 10.0,
            "biorxiv_fetch": 5.0,
        }

        return cls(
            host=os.environ.get("AGENTMEDQ_HOST", "127.0.0.1"),
            port=int(os.environ.get("AGENTMEDQ_PORT", "8042")),
            search_cache_ttl=int(os.environ.get("AGENTMEDQ_SEARCH_CACHE_TTL", "86400")),
            paper_cache_ttl=int(os.environ.get("AGENTMEDQ_PAPER_CACHE_TTL", "2592000")),
            db_path=os.environ.get("AGENTMEDQ_DB_PATH", "./agentmedq_cache.db"),
            ncbi_api_key=ncbi_key,
            openalex_email=os.environ.get("OPENALEX_EMAIL"),
            rate_limits=rate_limits,
        )

    @property
    def db_full_path(self) -> Path:
        return Path(self.db_path).resolve()
