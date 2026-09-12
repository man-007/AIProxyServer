from abc import ABC, abstractmethod
from typing import Any

class StreamAssembler(ABC):
    """Define the interface for stateful upstream-to-client stream conversion."""

    @abstractmethod
    def consume(self, chunk: dict[str, Any]) -> list[dict[str, Any]]:
        """Consume one upstream chunk and return client-facing events."""
        pass
