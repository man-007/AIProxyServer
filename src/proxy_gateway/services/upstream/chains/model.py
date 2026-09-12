from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from proxy_gateway.services.upstream.errors import UpstreamError
from proxy_gateway.services.upstream.handlers.base import UpstreamHandler
from proxy_gateway.services.upstream.transports.base import UpstreamTransport


class ModelUpstreamChain:
    """Route models through model-specific handlers before invoking transport."""

    def __init__(self, handlers: list[UpstreamHandler]):
        """Link handlers into the order used for model resolution."""
        self.handlers = handlers
        for current, following in zip(handlers, handlers[1:]):
            current.set_next(following)

    def resolve(self, model: str) -> UpstreamTransport:
        """Return the first handler transport that accepts the model."""
        if self.handlers:
            transport = self.handlers[0].handle(model)
            if transport is not None:
                return transport
        raise UpstreamError(404, f"No upstream handler is configured for model: {model}")

    async def complete(self, payload: dict[str, Any], request_id: str = "", idempotency_key: str = "") -> dict[str, Any]:
        """Send one completion through the handler selected for its model."""
        return await self.resolve(str(payload.get("model", ""))).complete(payload, request_id, idempotency_key)

    @asynccontextmanager
    async def stream(self, payload: dict[str, Any], request_id: str = "", idempotency_key: str = "") -> AsyncIterator[Any]:
        """Open a streaming response through the selected model handler."""
        async with self.resolve(str(payload.get("model", ""))).stream(payload, request_id, idempotency_key) as response:
            yield response
