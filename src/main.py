"""Entry point for the SonarQube MCP server."""

from __future__ import annotations

import argparse
import sys
from typing import Annotated, Optional

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from fastmcp.exceptions import ToolError

from .sonarqube import (
    MissingConfigurationError,
    SonarQubeAPIError,
    SonarQubeClient,
    SonarQubeConfig,
    SonarQubeIssueNotFound,
    build_issue_context,
)

_creation_error: Optional[MissingConfigurationError] = None


def create_mcp(
    config: Optional[SonarQubeConfig] = None,
    client: Optional[SonarQubeClient] = None,
) -> FastMCP:
    """Create and configure the FastMCP server instance.

    Authentication strategy:
    1. If an Authorization header with a Bearer token is present on the
       incoming HTTP/SSE request it is used for that call.
    2. Otherwise we fall back to the static token configured via
       environment variable.

    This allows each user/agent session to supply their own SonarQube token
    (with appropriate scoped permissions) when connecting over HTTP, while
    still supporting stdio transports where a global token is required.
    """

    if config is None:
        config = SonarQubeConfig.from_env()

    mcp = FastMCP("SonarQube")

    def _header_token_provider() -> Optional[str]:
        headers = get_http_headers()
        auth = headers.get("authorization") if headers else None
        if not auth:
            return None
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1]
        return None

    sonar_client = client or SonarQubeClient(config, token_provider=_header_token_provider)

    @mcp.tool(description="Fetch a single issue and enrich it with rule metadata.")
    async def get_issue_context(
        issue_key: Annotated[str, "SonarQube issue key (for example, AXd8...)"]
    ) -> dict:
        """Return detailed remediation context for a SonarQube issue."""

        try:
            payload = await sonar_client.fetch_issue_by_key(issue_key)
        except SonarQubeIssueNotFound as exc:  # pragma: no cover - integration guard
            raise ToolError(str(exc)) from exc
        except SonarQubeAPIError as exc:
            raise ToolError(str(exc)) from exc

        issue = payload["issue"]
        components = payload.get("components", [])
        rule_payload = None
        rule_error: Optional[str] = None
        rule_key = issue.get("rule")
        if rule_key:
            try:
                rule_payload = await sonar_client.fetch_rule(rule_key)
            except SonarQubeAPIError as exc:
                rule_error = str(exc)

        context = build_issue_context(issue=issue, components=components, rule=rule_payload)
        result = context.to_dict()
        if rule_error is not None:
            result["ruleFetchError"] = rule_error
        return result

    @mcp.tool(description="Search SonarQube issues using the official search API.")
    async def search_issues(
        issue_keys: Annotated[
            Optional[list[str]],
            "Specific SonarQube issue keys to include (max 50).",
        ] = None,
        components: Annotated[
            Optional[list[str]],
            "Component keys (project/module/file) to filter issues by.",
        ] = None,
        severities: Annotated[
            Optional[list[str]],
            "Limit results to the given severities (e.g. BLOCKER, CRITICAL).",
        ] = None,
        issue_statuses: Annotated[
            Optional[list[str]],
            "Filter by issue statuses (e.g. OPEN, CONFIRMED, FIXED).",
        ] = None,
        resolutions: Annotated[
            Optional[list[str]],
            "Limit to specific resolutions such as FIXED or WONTFIX.",
        ] = None,
        types: Annotated[
            Optional[list[str]],
            "Limit to issue types such as BUG, VULNERABILITY, CODE_SMELL.",
        ] = None,
        tags: Annotated[
            Optional[list[str]],
            "Filter issues that include any of the provided tags.",
        ] = None,
        assignees: Annotated[
            Optional[list[str]],
            "Restrict to issues assigned to these logins.",
        ] = None,
        languages: Annotated[
            Optional[list[str]],
            "Limit to issues detected in these languages.",
        ] = None,
        created_after: Annotated[
            Optional[str],
            "Return issues created after this ISO date/datetime (inclusive).",
        ] = None,
        created_before: Annotated[
            Optional[str],
            "Return issues created before this ISO date/datetime (exclusive).",
        ] = None,
        resolved: Annotated[
            Optional[bool],
            "Only resolved (true) or unresolved (false) issues.",
        ] = None,
        sort_field: Annotated[
            Optional[str],
            "Sort field (CREATION_DATE, UPDATE_DATE, SEVERITY, etc.).",
        ] = None,
        ascending: Annotated[
            Optional[bool],
            "Sort ascending (true) or descending (false).",
        ] = None,
        page: Annotated[int, "Page index (1-based) to retrieve."] = 1,
        page_size: Annotated[
            int,
            "Number of issues per page (1-500).",
        ] = 50,
    ) -> dict:
        """Run an issues search and surface a concise, agent-friendly payload."""

        if page < 1:
            raise ToolError("page must be >= 1")
        if page_size < 1 or page_size > 500:
            raise ToolError("page_size must be between 1 and 500")

        filters = {
            "issues": issue_keys,
            "components": components,
            "severities": severities,
            "issueStatuses": issue_statuses,
            "resolutions": resolutions,
            "types": types,
            "tags": tags,
            "assignees": assignees,
            "languages": languages,
            "createdAfter": created_after,
            "createdBefore": created_before,
            "resolved": resolved,
            "s": sort_field,
            "asc": ascending,
            "p": page,
            "ps": page_size,
        }

        try:
            payload = await sonar_client.search_issues(**filters)
        except SonarQubeAPIError as exc:
            raise ToolError(str(exc)) from exc

        components_lookup = {
            component.get("key"): component
            for component in payload.get("components", [])
            if isinstance(component, dict)
        }

        issues = []
        for issue in payload.get("issues", []):
            component = components_lookup.get(issue.get("component"))
            issues.append(
                {
                    "key": issue.get("key"),
                    "message": issue.get("message"),
                    "severity": issue.get("severity"),
                    "status": issue.get("status"),
                    "type": issue.get("type"),
                    "project": issue.get("project"),
                    "component": issue.get("component"),
                    "componentPath": component.get("path") if component else None,
                    "line": issue.get("line"),
                    "assignee": issue.get("assignee"),
                    "author": issue.get("author"),
                    "rule": issue.get("rule"),
                    "creationDate": issue.get("creationDate"),
                    "updateDate": issue.get("updateDate"),
                    "cleanCodeAttribute": issue.get("cleanCodeAttribute"),
                    "cleanCodeAttributeCategory": issue.get(
                        "cleanCodeAttributeCategory"
                    ),
                    "impacts": issue.get("impacts"),
                    "tags": issue.get("tags"),
                }
            )

        return {
            "total": payload.get("total"),
            "paging": payload.get("paging"),
            "issues": issues,
        }

    @mcp.tool(description="Retrieve metadata for a SonarQube rule.")
    async def get_rule(
        rule_key: Annotated[str, "Rule key such as csharpsquid:S2178"]
    ) -> dict:
        try:
            payload = await sonar_client.fetch_rule(rule_key)
        except SonarQubeAPIError as exc:
            raise ToolError(str(exc)) from exc
        rule_payload = payload.get("rule") if isinstance(payload, dict) else None
        if rule_payload is None:
            raise ToolError(f"Rule '{rule_key}' not found")
        return rule_payload

    return mcp


def main(argv: Optional[list[str]] = None) -> None:
    """Run the MCP server using stdio transport by default."""

    if _creation_error is not None:
        raise SystemExit(
            "SonarQube MCP server misconfigured: "
            f"{_creation_error}. Ensure required environment variables are set."
        )

    parser = argparse.ArgumentParser(description="Run the SonarQube MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport to use when serving MCP clients.",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind when using network transports (default varies by transport).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind when using network transports.",
    )
    args = parser.parse_args(argv)

    run_kwargs = {
        "transport": args.transport,
    }
    if args.host:
        run_kwargs["host"] = args.host
    if args.port:
        run_kwargs["port"] = args.port

    mcp.run(**run_kwargs)


try:
    mcp = create_mcp()
except MissingConfigurationError as exc:
    _creation_error = exc
    mcp = FastMCP("SonarQube (unconfigured)")

    @mcp.tool(description="Report configuration issues for the SonarQube MCP server.")
    async def configuration_status() -> dict:  # pragma: no cover - diagnostic path
        raise ToolError(
            "SonarQube MCP server is misconfigured. Ensure SONARQUBE_BASE_URL and "
            "SONARQUBE_TOKEN environment variables are set before starting the server."
        )


if __name__ == "__main__":
    main(sys.argv[1:])
