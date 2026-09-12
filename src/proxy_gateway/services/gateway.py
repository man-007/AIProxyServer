from __future__ import annotations

from typing import Any

from proxy_gateway.adapters import ProtocolAdapter
from proxy_gateway.diagnostics import GatewayUnavailableError, ModelUnavailableError, get_logger
from proxy_gateway.model import ModelRegistry
from proxy_gateway.validation import RequestValidationError


logger = get_logger("gateway")


class GatewayService:
    """Coordinates validation, model resolution, and protocol conversion."""

    def __init__(self, registry: ModelRegistry, api_key: str, model_discovery_enabled: bool = True):
        """Store shared dependencies used to prepare every upstream request."""
        self.registry = registry
        self.api_key = api_key
        self.model_discovery_enabled = model_discovery_enabled

    async def prepare(self, adapter: ProtocolAdapter, payload: dict[str, Any], request_id: str = "") -> dict[str, Any]:
        """Validate the client payload and convert it into the upstream format."""
        logger.debug(
            "IN:GatewayService::prepare started",
            extra={
                "adapter_type": type(adapter).__name__,
                "payload_keys": list(payload.keys()),
                "request_id": request_id,
            },
        )
        payload = adapter.validate_request(payload)
        if not self.api_key:
            raise RequestValidationError("UPSTREAM_API_KEY is not configured")

        requested_model = payload.get("model", "")
        resolved_model = self.registry.resolve_model_id(requested_model)
        logger.debug(
            "GatewayService::prepare model resolution completed",
            extra={"requested_model": requested_model, "resolved_model": resolved_model, "request_id": request_id},
        )
        if self.model_discovery_enabled and not self.registry.is_model_known(resolved_model):
            try:
                await self.registry.refresh(force=True, request_id=request_id)
            except Exception as exc:
                logger.error(
                    "GatewayService::prepare model refresh failed",
                    extra={"requested_model": requested_model, "request_id": request_id},
                    exc_info=True,
                )
                raise GatewayUnavailableError(str(exc)) from exc
        if self.model_discovery_enabled and not self.registry.is_model_known(resolved_model):
            logger.warning("GatewayService::prepare model unavailable", extra={"requested_model": requested_model, "request_id": request_id})
            raise ModelUnavailableError(f"Model not available: {requested_model}")

        transformed = adapter.to_upstream(payload)
        transformed["model"] = resolved_model
        if self.model_discovery_enabled:
            model_record = self.registry.get_model(resolved_model)
            capabilities = model_record.get("capabilities", {})
            if transformed.get("tools") and capabilities.get("tool_calling") is False:
                raise RequestValidationError(f"Model does not support tool calling: {resolved_model}")
            if transformed.get("stream") and capabilities.get("streaming") is False:
                raise RequestValidationError(f"Model does not support streaming: {resolved_model}")
        tool_choice = transformed.get("tool_choice")

        if isinstance(tool_choice, dict):
            tool_choice_summary = "configured"
        elif tool_choice in {None, "auto", "none", "required"}:
            tool_choice_summary = tool_choice if tool_choice is not None else "not_set"
        else:
            tool_choice_summary = "configured"
        logger.debug(
            "GatewayService::prepare upstream payload prepared",
            extra={
                "model": resolved_model,
                "message_count": len(transformed.get("messages", [])),
                "tool_count": len(transformed.get("tools", [])),
                "tool_names": [
                    tool.get("function", {}).get("name")
                    for tool in transformed.get("tools", [])
                    if isinstance(tool, dict)
                ],
                "tool_choice": tool_choice_summary,
                "max_tokens": transformed.get("max_tokens"),
                "stream": bool(transformed.get("stream")),
                "request_id": request_id,
            },
        )
        logger.debug(
            "OUT:GatewayService::prepare completed",
            extra={
                "upstream_keys": list(transformed.keys()),
                "request_id": request_id,
            },
        )
        return transformed