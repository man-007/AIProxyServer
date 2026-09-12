from __future__ import annotations

from proxy_gateway.services.upstream.chains import ModelUpstreamChain, TransportChain
from proxy_gateway.services.upstream.handlers import GenericModelUpstreamHandler, KimiK3UpstreamHandler
from proxy_gateway.services.upstream.transports import HttpxUpstreamClient, OpenAIUpstreamClient, UpstreamTransport
from proxy_gateway.diagnostics import get_logger

logger = get_logger("upstream_factory")


def build_upstream_client(
    *,
    base_url: str,
    api_key: str,
    chat_path: str,
    client_name: str,
    timeout: float = 120.0,
) -> ModelUpstreamChain:
    logger.debug(
        "IN:build_upstream_client::build_upstream_client started",
        extra={"base_url": base_url, "chat_path": chat_path, "client_name": client_name, "timeout": timeout},
    )
    httpx_client = HttpxUpstreamClient(base_url, api_key, chat_path, timeout)
    transports: dict[str, UpstreamTransport] = {"httpx": httpx_client}
    if client_name.lower() == "openai":
        transports["openai"] = OpenAIUpstreamClient(base_url, api_key, timeout)
        logger.debug("build_upstream_client::build_upstream_client OpenAI transport added")
    else:
        logger.debug("build_upstream_client::build_upstream_client using httpx transport only")
    transport = TransportChain(transports).resolve(client_name)
    logger.debug(
        "build_upstream_client::build_upstream_client transport resolved",
        extra={"client_name": client_name, "selected_transport": type(transport).__name__ if transport else None},
    )
    handlers = [
        KimiK3UpstreamHandler(transport),
        GenericModelUpstreamHandler(transport),
    ]
    logger.debug(
        "build_upstream_client::build_upstream_client upstream handlers created",
        extra={"handler_count": len(handlers), "handler_types": [h.__class__.__name__ for h in handlers]},
    )
    result = ModelUpstreamChain(handlers)
    logger.debug("OUT:build_upstream_client::build_upstream_client completed")
    return result