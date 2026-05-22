"""Tests for static MCP-Cortex-style capability profiles."""

from agentmedq.cortex import MCP_CORTEX_CAPABILITIES
from agentmedq.config import Settings
from agentmedq.server import create_server


EXPECTED_TOOL_NAMES = {
    "search_papers",
    "get_paper",
    "lookup_paper",
    "search_abstracts",
    "list_sources",
}


def test_all_existing_mcp_tools_have_capability_profiles():
    tools = MCP_CORTEX_CAPABILITIES["tools"]

    assert set(tools) == EXPECTED_TOOL_NAMES
    for name, profile in tools.items():
        assert profile["tool_name"] == name
        assert profile["assurance_level"] == "A1"
        assert profile["effects"]
        assert profile["risk_class"] in {"green", "yellow"}
        assert profile["runtime_dependency"] == "none"


def test_network_read_effects_are_explicit_and_conservative():
    tools = MCP_CORTEX_CAPABILITIES["tools"]
    network_tools = EXPECTED_TOOL_NAMES - {"list_sources"}

    for name in network_tools:
        profile = tools[name]
        assert profile["read_only"] is True
        assert "external_network_read" in profile["effects"]
        assert "filesystem_write" not in profile["effects"]
        assert "process_execution" not in profile["effects"]
        assert profile["risk_class"] == "yellow"

    list_sources = tools["list_sources"]
    assert list_sources["read_only"] is True
    assert list_sources["effects"] == ["local_static_metadata_read"]
    assert list_sources["risk_class"] == "green"


def test_capability_profiles_do_not_add_a_public_mcp_tool():
    mcp, _, _ = create_server(Settings())

    assert set(mcp._tool_manager._tools) == EXPECTED_TOOL_NAMES
    assert len(mcp._tool_manager._tools) == 5
