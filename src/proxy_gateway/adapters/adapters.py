from typing import Any, Callable, Optional, Sequence
from proxy_gateway.adapters.protocol_adapter import ProtocolAdapter
from proxy_gateway.adapters.anthropic_adapter import AnthropicAdapter
from proxy_gateway.utils.request_context import RequestContext
from proxy_gateway.diagnostics import get_logger

logger = get_logger("adapter_chain")

AdapterFactory = Callable[[], ProtocolAdapter]
class ProtocolAdapterChain:
    """Select the first protocol adapter that accepts an incoming request."""

    def __init__(self, adapter_factories: Sequence[AdapterFactory]):
        """Instantiate the enabled adapters in request matching order."""
        self._adapters = [factory() for factory in adapter_factories]
        logger.debug("ProtocolAdapterChain::__init__ initialized", extra={"adapter_count": len(self._adapters)})

    def resolve(
        self,
        context_or_method: RequestContext | str,
        path: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> Optional[ProtocolAdapter]:
        """Return the first adapter that can process a request context.

        The method and path form remains supported for existing integrations.
        """
        logger.debug(
            "ProtocolAdapterChain::resolve resolving adapter",
            extra={
                "context_type": type(context_or_method).__name__,
                "path": path,
                "headers_present": bool(headers),
            },
        )
        context = (
            context_or_method
            if isinstance(context_or_method, RequestContext)
            else RequestContext.from_request(
                method=context_or_method,
                path=path or "",
                headers=headers,
            )
        )
        logger.debug(
            "ProtocolAdapterChain::resolve context normalized",
            extra={"method": context.method, "path": context.path, "headers_keys": list(context.headers.keys()) if context.headers else None},
        )
        for idx, adapter in enumerate(self._adapters):
            try:
                matches = adapter.can_handle(context)
            except (AttributeError, TypeError):
                # Allow older adapters that still accept method and path.
                matches = adapter.can_handle(context.method, context.path)
            if matches:
                logger.debug(
                    "ProtocolAdapterChain::resolve adapter matched",
                    extra={"adapter_index": idx, "adapter_type": type(adapter).__name__},
                )
                return adapter
            else:
                logger.debug(
                    "ProtocolAdapterChain::resolve adapter did not match",
                    extra={"adapter_index": idx, "adapter_type": type(adapter).__name__},
                )
        logger.debug("ProtocolAdapterChain::resolve no adapter matched")
        return None

    @property
    def protocols(self) -> list[str]:
        """List the protocol names currently registered in the chain."""
        return [adapter.protocol_name for adapter in self._adapters]


def get_protocol_adapter(protocol: str) -> Optional[AdapterFactory]:
    """Return an enabled protocol adapter without exposing future routes yet."""
    adapters: dict[str, AdapterFactory] = {
        "anthropic": AnthropicAdapter,
    }
    return adapters.get(protocol)


def build_protocol_adapter_chain() -> ProtocolAdapterChain:
    """Build the enabled adapter chain in request matching order."""
    logger.debug("build_protocol_adapter_chain::build_protocol_adapter_chain building adapter chain")
    return ProtocolAdapterChain([AnthropicAdapter])