"""Static MCP-Cortex-style capability profiles for agentmedq tools."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


METHODOLOGY_IDS = [
    "95e0e1fa-60b3-405d-af61-abcf5e870b28",
    "23b71c68-9073-40b6-9fce-9bfdeddfd2c2",
]


def _network_read_tool(name: str, capability: str) -> dict[str, Any]:
    return {
        "tool_name": name,
        "capability": capability,
        "assurance_level": "A1",
        "risk_class": "yellow",
        "read_only": True,
        "external_network": True,
        "effects": ["external_network_read"],
        "preconditions": ["User supplies a biomedical literature query or paper identifier."],
        "postconditions": [
            "Returns literature metadata, abstracts, full text when available, or an error."
        ],
        "data_flow": {
            "input": "User-provided search terms or paper identifiers",
            "external_destinations": [
                "Europe PMC",
                "NCBI E-utilities",
                "arXiv API",
                "OpenAlex API",
            ],
            "output": "Provider responses normalized into agentmedq result dictionaries",
        },
        "rollback": "No rollback required: read-only external lookup.",
        "runtime_dependency": "none",
        "policy_notes": (
            "Conservatively classified as network-effectful despite read-only behavior."
        ),
    }


MCP_CORTEX_CAPABILITIES: dict[str, Any] = {
    "schema_version": "agentmedq.mcp_cortex_capabilities.v1",
    "profile_type": "static_capability_contracts",
    "runtime_dependency": "none",
    "methodology_ids": METHODOLOGY_IDS,
    "effect_vocabulary": {
        "external_network_read": "Read-only request to an external literature provider.",
        "local_static_metadata_read": "Read-only access to static in-process metadata.",
    },
    "tools": {
        "search_papers": _network_read_tool(
            "search_papers",
            "Search biomedical literature providers for papers matching a query.",
        ),
        "get_paper": _network_read_tool(
            "get_paper",
            "Retrieve a specific paper by source-specific identifier.",
        ),
        "lookup_paper": _network_read_tool(
            "lookup_paper",
            "Resolve DOI, PMID, or PMC identifiers to a paper record.",
        ),
        "search_abstracts": _network_read_tool(
            "search_abstracts",
            "Search OpenAlex abstract metadata for broad literature discovery.",
        ),
        "list_sources": {
            "tool_name": "list_sources",
            "capability": "List configured literature sources and static capability profiles.",
            "assurance_level": "A1",
            "risk_class": "green",
            "read_only": True,
            "external_network": False,
            "effects": ["local_static_metadata_read"],
            "preconditions": [],
            "postconditions": [
                "Returns configured source metadata and static capability profiles."
            ],
            "data_flow": {
                "input": "None",
                "external_destinations": [],
                "output": "Static source registry and MCP-Cortex-style capability profiles",
            },
            "rollback": "No rollback required: read-only local metadata lookup.",
            "runtime_dependency": "none",
            "policy_notes": "Local metadata read; no external API request is made.",
        },
    },
}


def get_mcp_cortex_capabilities() -> dict[str, Any]:
    """Return a JSON-serializable copy of static capability profiles."""

    return deepcopy(MCP_CORTEX_CAPABILITIES)
