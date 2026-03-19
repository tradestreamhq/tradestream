"""Abstract delivery channel interface."""

import abc


class DeliveryChannel(abc.ABC):
    """Base class for all signal delivery channels.

    Each channel must implement `send_signal` and provide a `name` property.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique channel identifier (e.g. 'telegram', 'discord')."""

    @abc.abstractmethod
    def send_signal(self, signal: dict) -> bool:
        """Deliver a trading signal through this channel.

        Args:
            signal: Signal payload dict containing at minimum:
                - signal_id, symbol, action, confidence

        Returns:
            True if the signal was delivered successfully.
        """

    def supports_priority(self, priority: str) -> bool:
        """Whether this channel handles the given priority level.

        Override to restrict a channel to certain priority levels.
        Default: all priorities supported.
        """
        return True
