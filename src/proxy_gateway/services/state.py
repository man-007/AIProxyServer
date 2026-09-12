"""Composition root: builds the singleton services shared by all routes."""
from proxy_gateway.adapters import build_protocol_adapter_chain
from proxy_gateway.config import settings
from proxy_gateway.services.gateway import GatewayService
from proxy_gateway.services.idempotency import InFlightRequestCoordinator
from proxy_gateway.diagnostics import configure_logging
from proxy_gateway.model_registry import ModelRegistry
from proxy_gateway.services.upstream import build_upstream_client
from proxy_gateway.services.config_service import ConfigService

logger = configure_logging(settings.log_level)

registry = ModelRegistry(
    base_url=settings.upstream_base_url,
    api_key=settings.upstream_api_key,
    models_path=settings.models_path,
    aliases={
        "claude-3-5-sonnet": "meta/llama-3.1-70b-instruct",
        "claude-3-5-haiku": "meta/llama-3.1-8b-instruct",
        "claude-3-opus": "meta/llama-3.1-70b-instruct",
    },
    capability_overrides={
        "moonshotai/kimi-k3": {"chat": True, "streaming": True, "tool_calling": True, "vision": True, "reasoning": True},
        "nvidia/nemotron-3-super-120b-a12b": {"chat": True, "streaming": True, "tool_calling": True, "reasoning": True, "structured_output": True},
        "meta/llama-3.1-70b-instruct": {"chat": True, "streaming": True, "tool_calling": True},
        "meta/llama-3.1-8b-instruct": {"chat": True, "streaming": True, "tool_calling": True},
        "meta/llama-3.1-405b-instruct": {"chat": True, "streaming": True, "tool_calling": True},
    },
    cache_ttl_seconds=settings.model_cache_ttl_seconds,
    timeout=settings.upstream_timeout_seconds,
)
registry.refresh(force=False)
protocol_adapters = build_protocol_adapter_chain()
gateway = GatewayService(registry, settings.upstream_api_key, settings.model_discovery_enabled)
upstream_client = build_upstream_client(
    base_url=settings.upstream_base_url,
    api_key=settings.upstream_api_key,
    chat_path=settings.chat_path,
    client_name=settings.upstream_client,
    timeout=settings.upstream_timeout_seconds,
)
request_coordinator = InFlightRequestCoordinator()
config_service = ConfigService(settings, registry, gateway, upstream_client)
