## SonarQube MCP Server

This project packages a Model Context Protocol (MCP) server for AI coding agents that need to investigate and remediate SonarQube issues. The server is built with [FastMCP](https://github.com/jlowin/fastmcp) and wraps the official SonarQube REST API to deliver:

- High-signal issue search results that highlight severity, ownership, and file locations.
- Detailed remediation context for a specific SonarQube issue, including the associated rule description and fix suggestions.
- Direct access to rule metadata for bespoke workflows.

> 🧠 **Goal**: Provide enough structured context for an agent to understand an issue, locate the offending code, and apply the recommended fix without visiting the SonarQube UI.

### Requirements

- Python 3.12+
- Access to a SonarQube instance (cloud or self-hosted) with an API token that can read issues and rules.
- The `fastmcp` package is already included; no MCP client is bundled.

### Configuration

Set the following environment variables before starting the server:

| Variable | Description | Example |
| --- | --- | --- |
| `SONARQUBE_BASE_URL` | Base URL of your SonarQube instance (no trailing slash) | `https://sonarqube.internal` |
| `SONARQUBE_TOKEN` | Personal access token with `Browse` access to projects | `squ_XXXXXXXXXXXXXXXXXXXXXXXXXXXX` |
| `SONARQUBE_TIMEOUT` *(optional)* | Request timeout in seconds (defaults to `15`) | `20` |

You can store these in a `.env` file or provide them through your process manager.

### Installation

```pwsh
uv sync
```

For development and testing dependencies:

```pwsh
uv sync --extra test
```

### Running the server

By default the server runs over stdio, which is ideal for local MCP clients:

```pwsh
uv run python -m src.main
```

To expose an HTTP transport, add the appropriate options when you run it:

```pwsh
uv run python -m src.main --transport http --host 0.0.0.0 --port 8765
```

Supported transports mirror the ones from FastMCP (`stdio`, `http`, `sse`).

### Available tools

| Tool | Purpose | Key arguments |
| --- | --- | --- |
| `get_issue_context` | Fetch a single issue by key, pull its rule, and return a markdown-rich brief plus machine-readable metadata. | `issue_key` (string) |
| `search_issues` | Wrapper around `/api/issues/search` that exposes the most common filters and augments each result with the component path. | `issue_keys`, `components`, `severities`, `issue_statuses`, `resolutions`, `types`, `tags`, `assignees`, `languages`, `created_after`, `created_before`, `resolved`, `sort_field`, `ascending`, `page`, `page_size` |
| `get_rule` | Retrieve raw rule metadata from `/api/rules/show`. | `rule_key` (string) |

All tools return JSON-serialisable dictionaries, making them easy to chain in agent workflows.

### Example workflow

1. Call `search_issues` with `project="Agrega-Server"` to retrieve open issues.
2. For each issue, call `get_issue_context(issue_key)`.
3. Use the `markdown` field to brief an LLM, and the structured `issue`/`rule` sections to build automated fixes.

Sample API responses from the SonarQube reference instance are provided in `sample_search_api_response.json` and `sample_rule_api_response.json`.

### Testing

After installing the optional `test` extra:

```pwsh
uv run python -m pytest
```

The tests stub external HTTP calls using `respx`, so they run offline and quickly.

### Troubleshooting

- If the server starts but every tool call fails immediately, ensure the `Authorization` header is accepted by your SonarQube instance and that your token has permission to view the project/issue.
- You can invoke the `configuration_status` tool (only available when the server is misconfigured) to diagnose missing environment variables.
- Enable HTTP-level logging by setting `HTTPX_LOG_LEVEL=debug` when running the process for deeper visibility.

### Roadmap / Ideas

- Surface code snippets when available via the `flows` metadata.
- Cache rule metadata to reduce duplicate requests during long sessions.
- Add tooling metrics (latency, error rates) to help identify flaky integrations.
