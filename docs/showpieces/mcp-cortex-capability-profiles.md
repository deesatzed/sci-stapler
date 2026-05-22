# MCP-Cortex Capability Profiles Showpiece

Date: 2026-05-22

## What This Proves

This showpiece demonstrates a small, practical MCP-Cortex adoption path for an
existing MCP server. `agentmedq` keeps its normal FastMCP tool surface, but now
advertises MCP-Cortex-style static capability profiles through the existing
`list_sources` tool.

The result is intentionally conservative:

- no new MCP tool was added;
- no runtime dependency on `mcp-cortex` was introduced;
- all five existing tools keep their current behavior;
- external literature lookups are labeled as read-only but network-effectful;
- local metadata reads are separated from external provider calls.

## Why It Matters

MCP tells a client which tools exist. MCP-Cortex adds a second layer of
machine-readable operating context: what a tool is expected to do, which effects
it has, what data leaves the process, whether rollback is meaningful, and how
risky the call should be treated.

For `agentmedq`, this means a client can inspect:

- `search_papers`
- `get_paper`
- `lookup_paper`
- `search_abstracts`
- `list_sources`

and distinguish read-only external-network tools from local static metadata
without requiring a new protocol, new server process, or new approval flow.

## How It Works

The static profiles live in `src/agentmedq/cortex.py`.

`tool_list_sources()` now returns the original `sources` payload plus a new
additive key:

```json
{
  "sources": [],
  "mcp_cortex_capabilities": {
    "schema_version": "agentmedq.mcp_cortex_capabilities.v1",
    "profile_type": "static_capability_contracts",
    "tools": {}
  }
}
```

Each tool profile includes:

- `tool_name`
- `capability`
- `assurance_level`
- `risk_class`
- `read_only`
- `external_network`
- `effects`
- `preconditions`
- `postconditions`
- `data_flow`
- `rollback`
- `policy_notes`

The public MCP tool registry remains exactly five tools.

## Codex-CAM Provenance

This was implemented through a Codex-CAM proof run. The agent recalled and cited
freshly mined MCP-Cortex methodologies before editing `agentmedq`.

`95e0e1fa-60b3-405d-af61-abcf5e870b28`
: Source `mcp-cortex-handoff-self` / `src/mcp_cortex/models.py`.
  Applied as static capability contracts for each existing MCP tool.

`23b71c68-9073-40b6-9fce-9bfdeddfd2c2`
: Source `mcp-cortex-handoff-self` / `src/mcp_cortex/policy.py`.
  Applied as conservative effect vocabulary for external network and local
  metadata reads.

Native CAM outcome:

```text
e5fae0ff-7d1f-4fc4-8c26-195dc406070d
```

## Verification

MCP-Cortex handoff package was tested before applying it:

```text
python -m pytest -q
10 passed

python scripts/validate_examples.py
all schema examples OK

PYTHONPATH=src python -m mcp_cortex.cli --help
CLI help rendered
```

`agentmedq` verification:

```text
PYTHONPATH=src python -m pytest \
  tests/test_cortex.py \
  tests/test_tools_unit.py::TestToolListSources \
  tests/test_server.py \
  tests/test_tools.py \
  -q

11 passed
```

Whitespace gate:

```text
git diff --check
clean
```

## Current Boundary

This is an adoption showpiece, not a full policy engine integration. It does not
block tool calls, add an authorization layer, or change transport behavior.
Those can be layered later. The point of this pass is to show that an existing
MCP server can expose useful MCP-Cortex metadata without rewriting its core MCP
implementation.
