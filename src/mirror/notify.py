from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

import requests


class NotificationError(RuntimeError):
    """Raised when a notifier fails to dispatch a notification."""


class Notifier(Protocol):
    """Interface for notification backends."""

    def notify_new_stemcell(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Send a notification that a new stemcell version has been published."""


@dataclass
class GitHubNotifierConfig:
    api_base_url: str
    repository_owner: str
    repository_name: str
    workflow_identifier: str
    ref: str
    token: str
    timeout_seconds: int = 10


class GitHubNotifier:
    """Dispatches a GitHub Actions workflow via the workflow_dispatch event."""

    def __init__(self, config: GitHubNotifierConfig, logger: Optional[logging.Logger] = None) -> None:
        self._config = config
        self._logger = logger or logging.getLogger(__name__)

    def notify_new_stemcell(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        metadata_dict: Dict[str, Any] = dict(metadata or {})
        inputs: Dict[str, str] = {key: str(value) for key, value in metadata_dict.items()}

        payload: Dict[str, Any] = {"ref": self._config.ref, "inputs": inputs}

        url = self._build_dispatch_url()
        headers = {
            "Authorization": f"Bearer {self._config.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        self._logger.info(
            "Dispatching GitHub workflow '%s' for %s/%s",
            self._config.workflow_identifier,
            self._config.repository_owner,
            self._config.repository_name,
        )

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=self._config.timeout_seconds,
        )

        if response.status_code not in (200, 204):
            self._logger.error(
                "GitHub workflow dispatch failed: %s %s",
                response.status_code,
                response.text,
            )
            raise NotificationError(f"Failed to dispatch workflow '{self._config.workflow_identifier}'.")

        self._logger.info("GitHub workflow dispatch accepted (status %s).", response.status_code)

    def _build_dispatch_url(self) -> str:
        base = self._config.api_base_url.rstrip("/")
        return (
            f"{base}/repos/{self._config.repository_owner}/{self._config.repository_name}"
            f"/actions/workflows/{self._config.workflow_identifier}/dispatches"
        )
