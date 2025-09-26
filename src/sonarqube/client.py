"""Async SonarQube API client."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import httpx

from .config import SonarQubeConfig

__all__ = [
    "SonarQubeClient",
    "SonarQubeAPIError",
    "SonarQubeIssueNotFound",
]

ISSUE_SEARCH_ENDPOINT = "/api/issues/search"
RULE_SHOW_ENDPOINT = "/api/rules/show"


class SonarQubeAPIError(RuntimeError):
    """Error raised when the SonarQube API returns a non-successful response."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SonarQubeIssueNotFound(SonarQubeAPIError):
    """Raised when an issue key cannot be found in SonarQube."""


class SonarQubeClient:
    """Small wrapper around the SonarQube REST API."""

    def __init__(self, config: SonarQubeConfig) -> None:
        self._config = config

    async def search_issues(self, **filters: Any) -> Dict[str, Any]:
        """Search for issues using SonarQube's /api/issues/search endpoint."""

        params = _prepare_params(filters)
        return await self._get_json(ISSUE_SEARCH_ENDPOINT, params=params)

    async def fetch_issue_by_key(self, issue_key: str) -> Dict[str, Any]:
        """Return a single issue given its key."""

        payload = await self.search_issues(issues=issue_key)
        issues = payload.get("issues", [])
        if not issues:
            raise SonarQubeIssueNotFound(
                f"Issue '{issue_key}' not found", status_code=404
            )

        issue = issues[0]
        components = payload.get("components", [])
        return {"issue": issue, "components": components, "raw": payload}

    async def fetch_rule(self, rule_key: str) -> Dict[str, Any]:
        payload = await self._get_json(RULE_SHOW_ENDPOINT, params={"key": rule_key})
        return payload

    async def _get_json(
        self,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._config.token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(
            base_url=self._config.base_url,
            headers=headers,
            timeout=self._config.timeout,
        ) as client:
            response = await client.get(path, params=params)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = _build_error_message(exc.response)
            raise SonarQubeAPIError(
                message, status_code=exc.response.status_code
            ) from exc

        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover - unexpected response
            raise SonarQubeAPIError(
                "SonarQube returned invalid JSON payload"
            ) from exc


def _prepare_params(filters: Mapping[str, Any]) -> Dict[str, Any]:
    prepared: Dict[str, Any] = {}
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            prepared[key] = ",".join(str(item) for item in value)
        else:
            prepared[key] = str(value)
    return prepared


def _build_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"SonarQube API error ({response.status_code})"

    message = payload.get("errors")
    if isinstance(message, list) and message:
        first = message[0]
        if isinstance(first, Mapping) and "msg" in first:
            return f"SonarQube API error ({response.status_code}): {first['msg']}"

    if "error" in payload:
        return f"SonarQube API error ({response.status_code}): {payload['error']}"

    return f"SonarQube API error ({response.status_code})"
