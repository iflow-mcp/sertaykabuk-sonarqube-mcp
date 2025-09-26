from sonarqube.context import build_issue_context


def test_build_issue_context_renders_markdown():
    issue = {
        "key": "ISSUE-1",
        "message": "Correct this '|' to '||'",
        "severity": "BLOCKER",
        "type": "CODE_SMELL",
        "status": "OPEN",
        "project": "Agrega-Server",
        "component": "Agrega-Server:src/server/Common/Utility/IpRangeHelper.cs",
        "line": 21,
        "assignee": "ali.kayhan",
        "rule": "csharpsquid:S2178",
        "tags": ["csharp"],
        "impacts": [{"softwareQuality": "MAINTAINABILITY", "severity": "BLOCKER"}],
    }
    components = [
        {
            "key": "Agrega-Server:src/server/Common/Utility/IpRangeHelper.cs",
            "path": "src/server/Common/Utility/IpRangeHelper.cs",
        }
    ]
    rule = {
        "rule": {
            "key": "csharpsquid:S2178",
            "name": "Short-circuit logic should be used in boolean contexts",
            "severity": "BLOCKER",
            "type": "CODE_SMELL",
            "descriptionSections": [
                {
                    "key": "root_cause",
                    "content": "<p>Always use <code>||</code>.</p>",
                }
            ],
        }
    }

    context = build_issue_context(issue=issue, components=components, rule=rule)

    assert context.issue["key"] == "ISSUE-1"
    assert context.component["path"] == "src/server/Common/Utility/IpRangeHelper.cs"
    assert "Always use `||`." in context.markdown
    assert context.rule["descriptionSections"][0]["markdown"] == "Always use `||`."