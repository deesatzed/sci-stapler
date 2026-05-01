"""Tests for configuration."""

import os
from pathlib import Path

from agentmedq.config import Settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.host == "127.0.0.1"
        assert s.port == 8042
        assert s.search_cache_ttl == 86400
        assert s.paper_cache_ttl == 2592000
        assert s.ncbi_api_key is None
        assert s.openalex_email is None

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("AGENTMEDQ_HOST", "0.0.0.0")
        monkeypatch.setenv("AGENTMEDQ_PORT", "9000")
        monkeypatch.setenv("AGENTMEDQ_SEARCH_CACHE_TTL", "3600")
        monkeypatch.setenv("AGENTMEDQ_DB_PATH", "/tmp/test.db")

        s = Settings.from_env()
        assert s.host == "0.0.0.0"
        assert s.port == 9000
        assert s.search_cache_ttl == 3600
        assert s.db_path == "/tmp/test.db"

    def test_ncbi_api_key_boosts_rate(self, monkeypatch):
        monkeypatch.setenv("NCBI_API_KEY", "test_key")
        s = Settings.from_env()
        assert s.ncbi_api_key == "test_key"
        assert s.rate_limits["ncbi"] == 10.0

    def test_no_ncbi_key_default_rate(self, monkeypatch):
        monkeypatch.delenv("NCBI_API_KEY", raising=False)
        s = Settings.from_env()
        assert s.rate_limits["ncbi"] == 3.0

    def test_db_full_path(self):
        s = Settings(db_path="./test.db")
        assert s.db_full_path.is_absolute()
        assert str(s.db_full_path).endswith("test.db")

    def test_openalex_email(self, monkeypatch):
        monkeypatch.setenv("OPENALEX_EMAIL", "test@example.com")
        s = Settings.from_env()
        assert s.openalex_email == "test@example.com"
