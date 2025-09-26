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

You must configure the base URL of your SonarQube instance. Authentication can
be provided in two ways:

1. Per-user Bearer token via an `Authorization: Bearer <token>` HTTP header
	when using the HTTP/SSE transports (recommended – allows each user/agent to
	have least-privilege access).
2. A static environment variable token (`SONARQUBE_TOKEN`) used as a fallback
	when no header is present (needed for stdio transport where HTTP headers
	are not available).

Set the following environment variables before starting the server:

| Variable | Description | Example |
| --- | --- | --- |
| `SONARQUBE_BASE_URL` | Base URL of your SonarQube instance (no trailing slash) | `https://sonarqube.internal` |
| `SONARQUBE_TOKEN` *(optional)* | Fallback personal access token with `Browse` access to projects. Used only if no Authorization header is supplied. | `squ_XXXXXXXXXXXXXXXXXXXXXXXXXXXX` |
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

Supported transports mirror the ones from FastMCP (`stdio`, `http`, `sse`). When
using `http`/`sse`, send an `Authorization` header with each request so the
server can perform SonarQube calls on behalf of that user:

```
Authorization: Bearer squ_XXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

If the header is omitted the server will fall back to `SONARQUBE_TOKEN`.

### Header-based auth example

The server internally inspects incoming headers (via FastMCP's
`get_http_headers`) on every tool call. A simplified example:

```python
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

mcp = FastMCP(name="Demo")

@mcp.tool
async def who_am_i() -> dict:
	headers = get_http_headers()
	auth = headers.get("authorization", "") if headers else ""
	return {
		"has_auth": bool(auth),
		"auth_is_bearer": auth.lower().startswith("bearer "),
		"user_agent": headers.get("user-agent") if headers else None,
	}
```

This mirrors the mechanism used by the SonarQube tools to resolve the active
token for each request.

### VS Code MCP client configuration

If you are using the VS Code built‑in MCP client (or an extension that reads a
`mcp.json` style manifest), you can prompt the user for their SonarQube token
and pass it as a bearer header. Example configuration snippet:

```json
{
	"servers": {
		"sonarqube": {
			"url": "http://localhost:8765/mcp",
			"type": "http",
			"headers": {
				"Authorization": "Bearer ${input:sonarqube_token}"
			}
		}
	},
	"inputs": [
		{
			"id": "sonarqube_token",
			"type": "promptString",
			"description": "SonarQube Token"
		}
	]
}
```

Notes:

- The `${input:...}` placeholder ensures the token is not stored in plain text
	in the config file; the user will be prompted in VS Code.
- If you prefer not to prompt each time, you can instead set the environment
	variable `SONARQUBE_TOKEN` and omit the `headers` block (less granular for
	multi-user scenarios).
- When using a remote SonarQube instance over HTTPS behind a corporate CA,
	ensure your Python environment trusts that CA (e.g. via `REQUESTS_CA_BUNDLE`
	/ `SSL_CERT_FILE`).

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
