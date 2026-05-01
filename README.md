# agentmedq

MCP server for agentic biomedical literature search across bioRxiv, medRxiv, PubMed Central, arXiv, and OpenAlex.

Provides AI agents with unified, rate-safe, cached access to 5 open biomedical literature databases via the [Model Context Protocol](https://modelcontextprotocol.io/).

## Sources

| Source | Coverage | Content |
|--------|----------|---------|
| bioRxiv | ~400K preprints, 2013-present | Search + metadata (via Europe PMC) |
| medRxiv | ~100K preprints, 2019-present | Search + metadata (via Europe PMC) |
| PubMed Central | ~7.5M articles | Search + full text (via NCBI E-utilities) |
| arXiv | ~3M papers | Search + abstract (full text in future version) |
| OpenAlex | ~50M works | Abstract-only search |

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_papers` | Search a specific source by keyword. Returns ranked results with title, authors, DOI, date, abstract. |
| `get_paper` | Retrieve full paper details by ID. Returns metadata and full text when available. |
| `lookup_paper` | Find a paper by DOI, PMID, or PMC ID. Cross-references across sources. |
| `search_abstracts` | Fast abstract-only search across ~50M works via OpenAlex. |
| `list_sources` | List available sources with capabilities and coverage info. |

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Usage

### stdio transport (default — for Claude Code, Cursor, etc.)

```bash
agentmedq
```

### HTTP/SSE transport

```bash
agentmedq --sse
```

### As a Python module

```bash
python -m agentmedq
python -m agentmedq --sse
```

## MCP Client Configuration

### Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "agentmedq": {
      "command": "agentmedq",
      "args": []
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentmedq": {
      "command": "agentmedq",
      "args": []
    }
  }
}
```

### SSE mode (for clients that support HTTP/SSE)

```bash
agentmedq --sse
# Server starts on http://127.0.0.1:8042
```

## Configuration

All settings are via environment variables. Copy `.env.example` to `.env` and edit:

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTMEDQ_HOST` | `127.0.0.1` | SSE server bind address |
| `AGENTMEDQ_PORT` | `8042` | SSE server port |
| `AGENTMEDQ_SEARCH_CACHE_TTL` | `86400` | Search cache TTL in seconds (24h) |
| `AGENTMEDQ_PAPER_CACHE_TTL` | `2592000` | Paper cache TTL in seconds (30d) |
| `AGENTMEDQ_DB_PATH` | `./agentmedq_cache.db` | SQLite cache file path |
| `NCBI_API_KEY` | _(none)_ | NCBI API key for 10 req/s (vs 3 req/s). [Register here](https://www.ncbi.nlm.nih.gov/account/) |
| `OPENALEX_EMAIL` | _(none)_ | Email for OpenAlex polite pool (higher rate limits) |

## Architecture

```
Agent ──MCP──> FastMCP Server ──> Search Router ──> 5 Search Providers
                                  Fetch Router ──> 4 Fetch Providers
                                  SQLite Cache (TTL-based)
                                  Token-Bucket Rate Limiter (per API)
```

- **Search and fetch are separate concerns** — the API used to find papers differs from the API to get full text
- **Retriever Protocol** — abstract interface designed as a swap-point for future backend integration
- **No AI model** — agentmedq is a protocol translator; AI analysis is handled by the connected agent

## Testing

```bash
pytest                                          # run all tests
pytest --cov=agentmedq --cov-report=term-missing  # with coverage
```

173 tests, 100% coverage. All tests hit real APIs (no mocks).

## License

MIT
