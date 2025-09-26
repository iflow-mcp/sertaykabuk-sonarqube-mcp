"""Utilities for building structured context blocks for SonarQube issues."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from html import unescape
import re
from typing import Any, Dict, Iterable, List, Optional

__all__ = ["IssueContext", "build_issue_context"]


@dataclass(slots=True)
class IssueContext:
    """Structured representation of the information we surface to agents."""

    issue: Dict[str, Any]
    component: Optional[Dict[str, Any]]
    rule: Optional[Dict[str, Any]]
    markdown: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_issue_context(
    *,
    issue: Dict[str, Any],
    components: Iterable[Dict[str, Any]] | None = None,
    rule: Optional[Dict[str, Any]] = None,
) -> IssueContext:
    """Build a convenient representation of an issue and its remediation guidance."""

    component = _match_component(issue.get("component"), components)
    markdown = _render_markdown(issue=issue, component=component, rule=rule)

    rule_payload = rule.get("rule") if isinstance(rule, dict) and "rule" in rule else rule

    return IssueContext(
        issue=_select_issue_fields(issue),
        component=component,
        rule=_select_rule_fields(rule_payload),
        markdown=markdown,
    )


def _match_component(
    component_key: Optional[str], components: Iterable[Dict[str, Any]] | None
) -> Optional[Dict[str, Any]]:
    if not component_key or components is None:
        return None
    for component in components:
        if component.get("key") == component_key:
            return component
    return None


def _select_issue_fields(issue: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "key",
        "message",
        "severity",
        "type",
        "status",
        "assignee",
        "author",
        "project",
        "component",
        "line",
        "effort",
        "debt",
        "creationDate",
        "updateDate",
        "cleanCodeAttribute",
        "cleanCodeAttributeCategory",
        "impacts",
        "tags",
        "hash",
        "textRange",
        "flows",
    ]
    return {k: issue.get(k) for k in keys if k in issue}


def _select_rule_fields(rule: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(rule, dict):
        return None
    keys = [
        "key",
        "name",
        "severity",
        "type",
        "status",
        "lang",
        "langName",
        "repo",
        "createdAt",
        "updatedAt",
        "cleanCodeAttribute",
        "cleanCodeAttributeCategory",
        "defaultRemFnBaseEffort",
        "descriptionSections",
        "tags",
        "sysTags",
    ]
    filtered = {k: rule.get(k) for k in keys if k in rule}
    filtered["descriptionSections"] = _transform_description_sections(
        rule.get("descriptionSections", [])
    )
    return filtered


def _transform_description_sections(
    sections: Iterable[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    formatted_sections: List[Dict[str, Any]] = []
    for section in sections or []:
        key = section.get("key")
        content = section.get("content", "")
        formatted_sections.append(
            {
                "key": key,
                "markdown": _html_to_markdown(content),
                "rawHtml": content,
            }
        )
    return formatted_sections


def _render_markdown(
    *,
    issue: Dict[str, Any],
    component: Optional[Dict[str, Any]],
    rule: Optional[Dict[str, Any]],
) -> str:
    component_path = component.get("path") if isinstance(component, dict) else None
    lines: List[str] = []

    lines.append(f"# SonarQube Issue {issue.get('key')}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- **Message:** {issue.get('message')}")
    lines.append(f"- **Severity:** {issue.get('severity')}")
    lines.append(f"- **Type:** {issue.get('type')}")
    lines.append(f"- **Status:** {issue.get('status')}")
    if issue.get("project"):
        lines.append(f"- **Project:** {issue.get('project')}")
    if component_path:
        lines.append(f"- **Component path:** {component_path}")
    if issue.get("line"):
        lines.append(f"- **Line:** {issue.get('line')}")
    if issue.get("assignee"):
        lines.append(f"- **Assignee:** {issue.get('assignee')}")
    if issue.get("author"):
        lines.append(f"- **Author:** {issue.get('author')}")
    if issue.get("effort"):
        lines.append(f"- **Estimated effort:** {issue.get('effort')}")

    if issue.get("cleanCodeAttribute"):
        lines.append(
            f"- **Clean code attribute:** {issue.get('cleanCodeAttribute')}"
        )
    if issue.get("cleanCodeAttributeCategory"):
        lines.append(
            "- **Clean code category:** "
            f"{issue.get('cleanCodeAttributeCategory')}"
        )

    tags = issue.get("tags")
    if tags:
        lines.append("- **Tags:** " + ", ".join(tags))

    impacts = issue.get("impacts")
    if impacts:
        formatted_impacts = ", ".join(
            f"{impact.get('softwareQuality')}: {impact.get('severity')}"
            for impact in impacts
            if isinstance(impact, dict)
        )
        if formatted_impacts:
            lines.append(f"- **Impacts:** {formatted_impacts}")

    lines.append("")

    text_range = issue.get("textRange")
    if isinstance(text_range, dict):
        lines.append("## Location")
        start_line = text_range.get("startLine")
        end_line = text_range.get("endLine")
        if start_line and end_line and start_line != end_line:
            lines.append(f"Lines {start_line}-{end_line}")
        elif start_line:
            lines.append(f"Line {start_line}")
        lines.append("")

    rule_payload = rule.get("rule") if isinstance(rule, dict) and "rule" in rule else rule
    if isinstance(rule_payload, dict):
        lines.append(f"## Rule {rule_payload.get('key')}")
        lines.append(f"**Name:** {rule_payload.get('name')}")
        lines.append(
            f"**Severity:** {rule_payload.get('severity')} ({rule_payload.get('type')})"
        )
        lines.append("")
        for section in rule_payload.get("descriptionSections", []) or []:
            title = section.get("key")
            if title:
                lines.append(f"### {title.replace('_', ' ').title()}")
            content = section.get("content", "")
            lines.append(_html_to_markdown(content))
            lines.append("")

    return "\n".join(line.rstrip() for line in lines if line is not None)


def _html_to_markdown(content: str) -> str:
    if not content:
        return ""

    text = content
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<pre[^>]*>", "\n```\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</pre>", "\n```\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<code>", "`", text, flags=re.IGNORECASE)
    text = re.sub(r"</code>", "`", text, flags=re.IGNORECASE)
    text = re.sub(r"<li>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|section|ul|ol|h\d)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<(h[1-6])>", lambda m: "\n" + "#" * int(m.group(1)[1]) + " ", text)
    text = re.sub(r"<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"\2 (\1)", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
