"""Abstract base class for delivery channels."""

import abc
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeliveryResult:
    """Result of a delivery attempt."""

    success: bool
    channel: str
    external_message_id: str = ""
    error: str = ""
    retryable: bool = False

    @staticmethod
    def ok(channel: str, external_id: str = "") -> "DeliveryResult":
        return DeliveryResult(success=True, channel=channel, external_message_id=external_id)

    @staticmethod
    def fail(channel: str, error: str, retryable: bool = True) -> "DeliveryResult":
        return DeliveryResult(
            success=False, channel=channel, error=error, retryable=retryable
        )


class DeliveryChannel(abc.ABC):
    """Abstract interface for signal delivery channels.

    All channel implementations must implement:
      - name: unique channel identifier
      - send(signal): deliver a signal dict and return DeliveryResult
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique channel identifier (e.g. 'telegram', 'discord')."""

    @abc.abstractmethod
    def send(self, signal: dict, recipient: str) -> DeliveryResult:
        """Send a signal to a specific recipient.

        Args:
            signal: Signal data dictionary.
            recipient: Channel-specific recipient identifier
                       (chat_id, webhook_url, email address, phone number, etc.)

        Returns:
            DeliveryResult indicating success or failure.
        """

    def validate_recipient(self, recipient: str) -> bool:
        """Validate that a recipient identifier is well-formed.

        Override in subclasses for channel-specific validation.
        """
        return bool(recipient)
