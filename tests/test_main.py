from unittest.mock import AsyncMock

import pytest

from fastmcp import Client

from sonarqube import SonarQubeConfig

from src.main import create_mcp


@pytest.mark.asyncio
async def test_get_issue_context_tool_returns_markdown():
    config = SonarQubeConfig(
        base_url="https://sonarqube.example.com",
        token="token",
    )

    issue_payload = {
        "issue": {
            "key": "ISSUE-1",
            "message": "Fix me",
            "severity": "MINOR",
            "type": "CODE_SMELL",
            "status": "OPEN",
            "rule": "rule-key",
        },
        "components": [],
    }
    rule_payload = {
        "rule": {
            "key": "rule-key",
            "name": "Rule Name",
            "severity": "MINOR",
            "type": "CODE_SMELL",
            "descriptionSections": [
                {"key": "root_cause", "content": "<p>Because reasons.</p>"}
            ],
        }
    }

    stub_client = AsyncMock()
    stub_client.fetch_issue_by_key.return_value = issue_payload
    stub_client.fetch_rule.return_value = rule_payload

    server = create_mcp(config=config, client=stub_client)

    async with Client(server) as client:
        result = await client.call_tool("get_issue_context", {"issue_key": "ISSUE-1"})

    stub_client.fetch_issue_by_key.assert_awaited_once_with("ISSUE-1")
    stub_client.fetch_rule.assert_awaited_once_with("rule-key")
    assert "Because reasons." in result.data["markdown"]


@pytest.mark.asyncio
async def test_search_issues_tool_formats_results():
    config = SonarQubeConfig(
        base_url="https://sonarqube.example.com",
        token="token",
    )
    payload = {
        "total": 1,
        "issues": [
            {
                "key": "ISSUE-1",
                "message": "Fix me",
                "severity": "MAJOR",
                "status": "OPEN",
                "type": "BUG",
                "project": "sample",
                "component": "sample:file.cs",
                "rule": "rule-key",
            }
        ],
        "components": [
            {
                "key": "sample:file.cs",
                "path": "src/file.cs",
            }
        ],
        "paging": {"pageIndex": 1, "pageSize": 50, "total": 1},
    }

    stub_client = AsyncMock()
    stub_client.search_issues.return_value = payload

    server = create_mcp(config=config, client=stub_client)

    async with Client(server) as client:
        result = await client.call_tool(
            "search_issues",
            {
                "components": ["sample"],
                "issue_statuses": ["OPEN"],
                "resolved": False,
                "sort_field": "CREATION_DATE",
                "ascending": False,
                "created_after": "2024-01-01",
                "languages": ["cs"],
            },
        )

    stub_call = stub_client.search_issues.await_args.kwargs
    assert stub_call["components"] == ["sample"]
    assert stub_call["issueStatuses"] == ["OPEN"]
    assert stub_call["resolved"] is False
    assert stub_call["s"] == "CREATION_DATE"
    assert stub_call["asc"] is False
    assert stub_call["createdAfter"] == "2024-01-01"
    assert stub_call["languages"] == ["cs"]
    assert result.data["issues"][0]["componentPath"] == "src/file.cs"