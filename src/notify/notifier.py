from __future__ import annotations

from typing import Any, Protocol


class NotificationError(RuntimeError):
    """Raised when a notifier fails to dispatch a notification."""


class Notifier(Protocol):
    """Interface for notification backends."""

    def notify_new_stemcell(self, metadata: dict[str, Any] | None = None) -> None:
        """Send a notification that a new stemcell version has been published."""
