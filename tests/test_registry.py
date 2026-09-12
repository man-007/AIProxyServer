import asyncio

import pytest

from proxy_gateway.model import ModelRegistry


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("bad response")

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def get(self, *args, **kwargs):
        return DummyResponse({"data": self.payload})


@pytest.mark.asyncio
async def test_registry_resolves_alias_and_capabilities():
    registry = ModelRegistry(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key="secret",
        aliases={"claude-3-5-sonnet": "meta/llama-3.1-70b-instruct"},
        capability_overrides={
            "meta/llama-3.1-70b-instruct": {"chat": True, "streaming": True, "tool_calling": True}
        },
        client_factory=lambda *args, **kwargs: DummyClient([
            {"id": "meta/llama-3.1-70b-instruct", "object": "model", "owned_by": "meta"},
            {"id": "other/model", "object": "model", "owned_by": "other"},
        ]),
    )

    await registry.refresh(force=True)
    resolved = registry.resolve_model_id("claude-3-5-sonnet")

    assert resolved == "meta/llama-3.1-70b-instruct"
    model = registry.get_model("claude-3-5-sonnet")
    assert model["capabilities"]["tool_calling"] is True
    assert model["source"] == "upstream"


@pytest.mark.asyncio
async def test_registry_refreshes_on_unknown_model():
    registry = ModelRegistry(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key="secret",
        aliases={},
        capability_overrides={},
        client_factory=lambda *args, **kwargs: DummyClient([
            {"id": "new-model", "object": "model", "owned_by": "demo"},
        ]),
    )

    await registry.refresh(force=True)
    assert registry.is_model_known("new-model") is True
    assert registry.resolve_model_id("new-model") == "new-model"
