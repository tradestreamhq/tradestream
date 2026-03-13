"""
Exchange registry for managing multiple exchange connectors.
"""

from typing import Dict, List, Optional

from services.exchange_connector.base import ExchangeConnector


class ExchangeRegistry:
    """Registry for managing multiple exchange connectors."""

    def __init__(self):
        self._connectors: Dict[str, ExchangeConnector] = {}

    def register(self, connector: ExchangeConnector) -> None:
        """Register an exchange connector."""
        self._connectors[connector.name] = connector

    def get(self, name: str) -> Optional[ExchangeConnector]:
        """Get connector by exchange name."""
        return self._connectors.get(name)

    def list_exchanges(self) -> List[str]:
        """List registered exchange names."""
        return list(self._connectors.keys())

    def remove(self, name: str) -> bool:
        """Remove an exchange connector. Returns True if it existed."""
        return self._connectors.pop(name, None) is not None

    def __len__(self) -> int:
        return len(self._connectors)

    def __contains__(self, name: str) -> bool:
        return name in self._connectors
