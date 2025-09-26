"""Entry point for the SonarQube MCP server."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from fastmcp import FastMCP
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
    """Create and configure the FastMCP server instance."""

    if config is None:
        config = SonarQubeConfig.from_env()

    mcp = FastMCP("SonarQube")
    sonar_client = client or SonarQubeClient(config)

    @mcp.tool(description="Fetch a single issue and enrich it with rule metadata.")
    async def get_issue_context(issue_key: str) -> dict:
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
        issue_keys: Optional[list[str]] = None,
        project: Optional[str] = None,
        component_keys: Optional[list[str]] = None,
        severities: Optional[list[str]] = None,
        statuses: Optional[list[str]] = None,
        types: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        assignees: Optional[list[str]] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Run an issues search and surface a concise, agent-friendly payload."""

        if page < 1:
            raise ToolError("page must be >= 1")
        if page_size < 1 or page_size > 500:
            raise ToolError("page_size must be between 1 and 500")

        filters = {
            "issues": issue_keys,
            "project": project,
            "componentKeys": component_keys,
            "severities": severities,
            "statuses": statuses,
            "types": types,
            "tags": tags,
            "assignees": assignees,
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
    async def get_rule(rule_key: str) -> dict:
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
