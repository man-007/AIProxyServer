from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx

from proxy_gateway.diagnostics import get_logger
from proxy_gateway.services.upstream.errors import UpstreamError, error_metadata, raise_for_upstream_error
from proxy_gateway.services.upstream.transports.base import UpstreamTransport


logger = get_logger("upstream")


class HttpxUpstreamClient(UpstreamTransport):
    """Generic chat-completions transport implemented with httpx."""

    def __init__(self, base_url: str, api_key: str, chat_path: str, timeout: float = 120.0):
        super().__init__(base_url, api_key, timeout)
        self.url = f"{self.base_url}{chat_path}"

    def build_headers(self, idempotency_key: str = "") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @property
    def headers(self) -> dict[str, str]:
        return self.build_headers()

    def stream_headers(self, idempotency_key: str = "") -> dict[str, str]:
        headers = self.build_headers(idempotency_key=idempotency_key)
        headers["Accept"] = "text/event-stream"
        return headers

    @staticmethod
    async def _raise_for_error(response: httpx.Response) -> None:
        await raise_for_upstream_error(response)

    async def complete(self, payload: dict[str, Any], request_id: str = "", idempotency_key: str = "") -> dict[str, Any]:
        started_at = time.perf_counter()
        logger.debug("IN:HttpxUpstreamClient::complete upstream request started", extra={"request_id": request_id, "stream": False, "model": payload.get("model")})
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.url, headers=self.build_headers(idempotency_key), json=payload)
                await raise_for_upstream_error(response)
                logger.debug("OUT:HttpxUpstreamClient::complete upstream request completed", extra={"request_id": request_id, "status_code": response.status_code, "stream": False, "duration_ms": round((time.perf_counter() - started_at) * 1000, 2)})
                try:
                    return response.json()
                except (ValueError, json.JSONDecodeError) as exc:
                    raise UpstreamError(502, "The upstream returned malformed JSON.") from exc
        except UpstreamError as exc:
            logger.warning("HttpxUpstreamClient::complete upstream request rejected", extra={"request_id": request_id, "stream": False, "status_code": exc.status_code, **error_metadata(exc.payload)})
            raise
        except httpx.TimeoutException as exc:
            logger.error("HttpxUpstreamClient::complete upstream request timed out", extra={"request_id": request_id, "stream": False}, exc_info=True)
            raise UpstreamError(504, "The upstream request timed out.") from exc
        except httpx.HTTPError as exc:
            logger.error("HttpxUpstreamClient::complete upstream transport error", extra={"request_id": request_id, "stream": False}, exc_info=True)
            raise UpstreamError(502, str(exc)) from exc

    @asynccontextmanager
    async def stream(self, payload: dict[str, Any], request_id: str = "", idempotency_key: str = "") -> AsyncIterator[httpx.Response]:
        started_at = time.perf_counter()
        logger.debug("IN:HttpxUpstreamClient::stream upstream request started", extra={"request_id": request_id, "stream": True, "model": payload.get("model")})
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", self.url, headers=self.stream_headers(idempotency_key), json=payload) as response:
                    await raise_for_upstream_error(response)
                    logger.debug("OUT:HttpxUpstreamClient::stream upstream request connected", extra={"request_id": request_id, "status_code": response.status_code, "stream": True, "duration_ms": round((time.perf_counter() - started_at) * 1000, 2)})
                    yield response
        except UpstreamError as exc:
            logger.warning("HttpxUpstreamClient::stream upstream stream rejected", extra={"request_id": request_id, "stream": True, "status_code": exc.status_code, **error_metadata(exc.payload)})
            raise
        except httpx.TimeoutException as exc:
            logger.error("HttpxUpstreamClient::stream upstream stream timed out", extra={"request_id": request_id, "stream": True}, exc_info=True)
            raise UpstreamError(504, "The upstream stream timed out.") from exc
        except httpx.HTTPError as exc:
            logger.error("HttpxUpstreamClient::stream upstream transport error", extra={"request_id": request_id, "stream": True}, exc_info=True)
            raise UpstreamError(502, str(exc)) from exc
