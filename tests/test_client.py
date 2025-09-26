import httpx
import pytest
import respx

from sonarqube import SonarQubeClient, SonarQubeConfig, SonarQubeIssueNotFound


@pytest.mark.asyncio
async def test_fetch_issue_by_key_success():
    config = SonarQubeConfig(base_url="https://sonarqube.example.com", token="token")
    client = SonarQubeClient(config)

    issue_payload = {
        "issues": [
            {
                "key": "ISSUE-1",
                "rule": "csharpsquid:S2178",
                "message": "Fix this issue",
            }
        ],
        "components": [
            {
                "key": "component-key",
                "path": "path/to/file.cs",
            }
        ],
    }

    with respx.mock(assert_all_called=True) as router:
        router.get(
            "https://sonarqube.example.com/api/issues/search",
            params={"issues": "ISSUE-1"},
        ).mock(return_value=httpx.Response(200, json=issue_payload))

        result = await client.fetch_issue_by_key("ISSUE-1")

    assert result["issue"]["key"] == "ISSUE-1"
    assert result["components"][0]["path"] == "path/to/file.cs"


@pytest.mark.asyncio
async def test_fetch_issue_by_key_not_found():
    config = SonarQubeConfig(base_url="https://sonarqube.example.com", token="token")
    client = SonarQubeClient(config)

    with respx.mock(assert_all_called=True) as router:
        router.get(
            "https://sonarqube.example.com/api/issues/search",
            params={"issues": "MISSING"},
        ).mock(return_value=httpx.Response(200, json={"issues": []}))

        with pytest.raises(SonarQubeIssueNotFound):
            await client.fetch_issue_by_key("MISSING")


@pytest.mark.asyncio
async def test_fetch_rule_success():
    config = SonarQubeConfig(base_url="https://sonarqube.example.com", token="token")
    client = SonarQubeClient(config)

    rule_payload = {
        "rule": {
            "key": "csharpsquid:S2178",
            "name": "Short-circuit logic should be used in boolean contexts",
        }
    }

    with respx.mock(assert_all_called=True) as router:
        router.get(
            "https://sonarqube.example.com/api/rules/show",
            params={"key": "csharpsquid:S2178"},
        ).mock(return_value=httpx.Response(200, json=rule_payload))

        result = await client.fetch_rule("csharpsquid:S2178")

    assert result["rule"]["key"] == "csharpsquid:S2178"
