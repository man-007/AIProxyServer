import httpx
import pytest

from proxy_gateway.upstream import (
    KimiK3UpstreamHandler,
    ModelUpstreamChain,
    GenericModelUpstreamHandler,
    HttpxUpstreamClient,
    TransportChain,
    UpstreamError,
    UpstreamHandler,
    UpstreamTransport,
)


def test_upstream_headers_negotiate_response_format():
    client = HttpxUpstreamClient(
        base_url="https://integrate.api.nvidia.com",
        api_key="secret",
        chat_path="/v1/chat/completions",
    )

    assert client.headers["Accept"] == "application/json"
    assert client.stream_headers()["Accept"] == "text/event-stream"
    assert isinstance(client, UpstreamTransport)


def test_transport_chain_resolves_configured_client():
    httpx_client = object()
    openai_client = object()
    chain = TransportChain({"httpx": httpx_client, "openai": openai_client})

    assert chain.resolve("httpx") is httpx_client
    assert chain.resolve("openai") is openai_client


def test_transport_chain_rejects_unknown_client():
    with pytest.raises(ValueError, match="Unsupported upstream client"):
        TransportChain({"httpx": object()}).resolve("unknown")


def test_model_handlers_share_parent_and_delegate_to_next_handler():
    transport = object()
    kimi = KimiK3UpstreamHandler(transport)
    generic = GenericModelUpstreamHandler(transport)
    chain = ModelUpstreamChain([kimi, generic])

    assert isinstance(kimi, UpstreamHandler)
    assert isinstance(generic, UpstreamHandler)
    assert kimi.next_handler is generic
    assert chain.resolve("moonshotai/kimi-k3") is transport
    assert chain.resolve("meta/llama-3.1-70b-instruct") is transport


@pytest.mark.asyncio
async def test_stream_error_reads_json_body_before_normalizing():
    response = httpx.Response(
        500,
        request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
        stream=httpx.ByteStream(b'{"message":"upstream failed"}'),
    )

    with pytest.raises(UpstreamError) as error:
        await HttpxUpstreamClient._raise_for_error(response)

    assert error.value.status_code == 500
    assert error.value.payload == {"message": "upstream failed"}


@pytest.mark.asyncio
async def test_stream_error_reads_plain_text_body_before_normalizing():
    response = httpx.Response(
        502,
        request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
        stream=httpx.ByteStream(b"bad gateway"),
    )

    with pytest.raises(UpstreamError) as error:
        await HttpxUpstreamClient._raise_for_error(response)

    assert error.value.status_code == 502
    assert error.value.payload == "bad gateway"


@pytest.mark.asyncio
async def test_pending_upstream_response_is_not_treated_as_completion():
    response = httpx.Response(
        202,
        headers={"nvcf-reqid": "request-123"},
        request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
    )

    with pytest.raises(UpstreamError) as error:
        await HttpxUpstreamClient._raise_for_error(response)

    assert error.value.status_code == 503
    assert "request-123" in error.value.payload