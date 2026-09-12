import asyncio

import pytest

from proxy_gateway.idempotency import DuplicateRequestError, InFlightRequestCoordinator, request_key
from proxy_gateway.upstream import HttpxUpstreamClient


def test_request_key_is_stable_and_opaque():
    payload = {"model": "model", "messages": [{"role": "user", "content": "hello"}]}

    assert request_key(payload) == request_key({"messages": payload["messages"], "model": "model"})
    assert "hello" not in request_key(payload)


@pytest.mark.asyncio
async def test_non_stream_duplicates_are_rejected_while_active():
    coordinator = InFlightRequestCoordinator()
    started = 0
    release = asyncio.Event()

    async def operation():
        nonlocal started
        started += 1
        await release.wait()
        return {"ok": True}

    first = asyncio.create_task(coordinator.execute("same", operation))
    await asyncio.sleep(0)
    second = asyncio.create_task(coordinator.execute("same", operation))
    await asyncio.sleep(0)
    with pytest.raises(DuplicateRequestError, match="currently being processed"):
        await second
    release.set()

    assert await first == {"ok": True}
    assert started == 1


@pytest.mark.asyncio
async def test_duplicate_stream_is_rejected_until_released():
    coordinator = InFlightRequestCoordinator()
    await coordinator.claim_stream("same")

    with pytest.raises(DuplicateRequestError):
        await coordinator.claim_stream("same")

    await coordinator.release_stream("same")
    await coordinator.claim_stream("same")


def test_upstream_headers_do_not_include_idempotency_key():
    client = HttpxUpstreamClient("https://example.test", "secret", "/v1/chat/completions")

    assert "Idempotency-Key" not in client.build_headers("proxy-key")
    assert "Idempotency-Key" not in client.headers


@pytest.mark.asyncio
async def test_failed_operation_is_not_blocked_after_completion():
    coordinator = InFlightRequestCoordinator()
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        raise RuntimeError("failed")

    with pytest.raises(RuntimeError, match="failed"):
        await coordinator.execute("same", operation)
    with pytest.raises(RuntimeError, match="failed"):
        await coordinator.execute("same", operation)

    assert calls == 2
