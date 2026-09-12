from abc import ABC, abstractmethod
from typing import Any
from proxy_gateway.assembler.stream_assembler import StreamAssembler
from proxy_gateway.utils.request_context import RequestContext

class ProtocolAdapter(ABC):
    """Define the protocol operations required by the gateway request route."""

    @property
    @abstractmethod
    def protocol_name(self) -> str:
        """Return the stable name used to identify this protocol."""
        ...

    @abstractmethod
    def can_handle(self, context: RequestContext) -> bool:
        """Report whether this adapter owns the incoming HTTP request."""
        ...

    @abstractmethod
    def validate_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize a client request before conversion."""
        ...

    @abstractmethod
    def to_upstream(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Convert the protocol payload into the selected upstream format."""
        ...

    @abstractmethod
    def from_upstream(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Convert an upstream completion into the client protocol format."""
        ...

    @abstractmethod
    def create_stream_assembler(self) -> StreamAssembler:
        """Create the stateful assembler used for this protocol's stream events."""
        ...