from dataclasses import dataclass
from typing import Any


@dataclass
class StreamInfo:
    """Hold state needed while translating one upstream streaming response."""

    chunk: dict[str, Any]
    assembler: Any | None = None
    adapter_name: str = ""
    destination: str | None = None

    def set_chunk(self, chunk: dict[str, Any]) -> None:
        """Replace the current upstream chunk being translated."""
        self.chunk = chunk

    def set_assembler(self, assembler: Any | None = None) -> None:
        """Set the stateful assembler responsible for this stream."""
        self.assembler = assembler

    def reset(self) -> None:
        """Clear stream state so the object can be reused safely."""
        self.chunk = {}
        self.assembler = None
        self.adapter_name = ""
        self.destination = None