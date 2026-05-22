# MCP-Cortex Capability Profiles

Date: 2026-05-22
Repo: `/Volumes/WS4TB/_MyGhRepos/sci-stapler`

## Methodology Table

| Methodology ID | Source | Applied Use |
| --- | --- | --- |
| `95e0e1fa-60b3-405d-af61-abcf5e870b28` | `mcp-cortex-handoff-self` / `src/mcp_cortex/models.py` | Static capability contracts for each existing MCP tool, including assurance level, effects, data flow, and rollback metadata. |
| `23b71c68-9073-40b6-9fce-9bfdeddfd2c2` | `mcp-cortex-handoff-self` / `src/mcp_cortex/policy.py` | Conservative effect vocabulary: external-network reads are explicit and separate from local static metadata reads. |

## Application Plan

- Add deterministic static capability profiles in `src/agentmedq/cortex.py`.
- Preserve the five existing public MCP tools: `search_papers`, `get_paper`, `lookup_paper`, `search_abstracts`, and `list_sources`.
- Expose profiles additively from `tool_list_sources()` under `mcp_cortex_capabilities`.
- Avoid any runtime dependency on `mcp-cortex`.
- Avoid real network/API verification; use focused local unit/server tests only.

## Commands Run

| Command | Result |
| --- | --- |
| `PYTHONPATH=src python -m pytest tests/test_cortex.py tests/test_tools_unit.py::TestToolListSources -q` | RED: failed because `agentmedq.cortex` was missing. |
| `PYTHONPATH=src python -m pytest tests/test_cortex.py tests/test_tools_unit.py::TestToolListSources -q` | GREEN: `6 passed in 0.61s`. |
| `PYTHONPATH=src python -m pytest tests/test_cortex.py tests/test_tools_unit.py::TestToolListSources tests/test_server.py tests/test_tools.py -q` | PASS: `11 passed in 0.62s`. |
| `git diff --check` | PASS: no whitespace errors. |

## Result

Green. Static MCP-Cortex-style profiles are exposed additively from `list_sources`,
with no new MCP public tool and no runtime dependency on `mcp-cortex`.
CAM outcome recorded as `e5fae0ff-7d1f-4fc4-8c26-195dc406070d`.
