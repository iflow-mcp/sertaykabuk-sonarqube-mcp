"""Configuration utilities for accessing the SonarQube API."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional


class MissingConfigurationError(RuntimeError):
    """Raised when mandatory SonarQube configuration values are missing."""


DEFAULT_TIMEOUT = 15.0


@dataclass(slots=True)
class SonarQubeConfig:
    """Runtime configuration required to connect to a SonarQube instance."""

    base_url: str
    token: str
    timeout: float = DEFAULT_TIMEOUT

    @classmethod
    def from_env(
        cls,
        base_url_var: str = "SONARQUBE_BASE_URL",
        token_var: str = "SONARQUBE_TOKEN",
        timeout_var: str = "SONARQUBE_TIMEOUT",
    ) -> "SonarQubeConfig":
        """Load configuration values from environment variables.

        Args:
            base_url_var: Name of the environment variable that contains the
                SonarQube base URL (e.g. ``https://sonarqube.example.com``).
            token_var: Name of the environment variable containing a SonarQube
                user or service account token.
            timeout_var: Optional environment variable overriding the default
                request timeout in seconds.

        Raises:
            MissingConfigurationError: if either the base URL or token are not
                provided.
            ValueError: if the timeout value cannot be parsed into a positive
                float.
        """

        base_url = _read_env(base_url_var)
        token = _read_env(token_var)
        timeout_value = os.getenv(timeout_var)

        if not base_url:
            raise MissingConfigurationError(
                f"Environment variable '{base_url_var}' must be set."
            )
        if not token:
            raise MissingConfigurationError(
                f"Environment variable '{token_var}' must be set."
            )

        timeout = (
            cls._parse_timeout(timeout_value)
            if timeout_value
            else DEFAULT_TIMEOUT
        )

        return cls(base_url=_normalize_base_url(base_url), token=token, timeout=timeout)

    @staticmethod
    def _parse_timeout(value: str) -> float:
        try:
            timeout = float(value)
        except ValueError as exc:
            raise ValueError(
                "SONARQUBE_TIMEOUT must be a number representing seconds"
            ) from exc

        if timeout <= 0:
            raise ValueError("SONARQUBE_TIMEOUT must be greater than zero")

        return timeout


def _read_env(var_name: str) -> Optional[str]:
    value = os.getenv(var_name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_base_url(url: str) -> str:
    return url[:-1] if url.endswith("/") else url
