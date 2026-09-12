import pytest

from proxy_gateway.gateway import GatewayService
from proxy_gateway.model import ModelRegistry
from proxy_gateway.validation import RequestValidationError


class Adapter:
    @staticmethod
    def validate_request(payload):
        return payload

    @staticmethod
    def to_upstream(payload):
        return {"model": payload["model"], "messages": [], "tools": payload.get("tools", [])}


@pytest.mark.asyncio
async def test_gateway_rejects_tools_for_model_without_tool_capability():
    registry = ModelRegistry("https://example.test", "secret", capability_overrides={})
    registry._models["plain-model"] = {"capabilities": {"tool_calling": False, "streaming": True}}
    gateway = GatewayService(registry, "secret")

    with pytest.raises(RequestValidationError, match="does not support tool calling"):
        await gateway.prepare(Adapter(), {"model": "plain-model", "tools": [{"name": "x"}]})