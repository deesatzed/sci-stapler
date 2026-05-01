"""Tests for server creation."""

from agentmedq.config import Settings
from agentmedq.server import create_server


class TestCreateServer:
    def test_creates_all_components(self):
        settings = Settings()
        mcp, retriever, cache = create_server(settings)
        assert mcp is not None
        assert retriever is not None
        assert cache is not None

    def test_server_name(self):
        mcp, _, _ = create_server(Settings())
        assert mcp.name == "agentmedq"

    def test_custom_settings(self):
        settings = Settings(host="0.0.0.0", port=9999)
        mcp, _, cache = create_server(settings)
        assert cache.db_path
