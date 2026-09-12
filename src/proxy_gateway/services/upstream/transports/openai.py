from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from proxy_gateway.services.upstream.errors import UpstreamError
from proxy_gateway.services.upstream.transports.base import UpstreamTransport
from proxy_gateway.diagnostics import get_logger

logger = get_logger("upstream")


class OpenAIStreamResponse:
    """Expose OpenAI SDK chunks as the SSE lines consumed by the route."""

    def __init__(self, response: Any):
        self.response = response

    async def aiter_lines(self) -> AsyncIterator[str]:
        try:
            async for chunk in self.response:
                payload = chunk.model_dump(exclude_none=True, mode="json") if hasattr(chunk, "model_dump") else chunk
                yield f"data: {json.dumps(payload)}"
            yield "data: [DONE]"
        except UpstreamError:
            raise
        except Exception as exc:
            status_code = getattr(exc, "status_code", 502)
            payload = getattr(exc, "body", None) or str(exc)
            raise UpstreamError(status_code, payload) from exc


class OpenAIUpstreamClient(UpstreamTransport):
    """Chat-completions transport backed by the OpenAI-compatible SDK."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0):
        logger.debug(
            "IN:OpenAIUpstreamClient::__init__ started",
            extra={"base_url": base_url, "timeout": timeout},
        )
        super().__init__(base_url, api_key, timeout)
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            logger.error("OpenAIUpstreamClient::__init__ OpenAI package not installed")
            raise RuntimeError("UPSTREAM_CLIENT=openai requires the openai package.") from exc

        sdk_base_url = self.base_url
        if not sdk_base_url.endswith("/v1"):
            sdk_base_url = f"{sdk_base_url}/v1"
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=sdk_base_url, timeout=self.timeout)
        logger.debug("OUT:OpenAIUpstreamClient::__init__ completed")

    @staticmethod
    def _payload(response: Any) -> dict[str, Any]:
        return response.model_dump(exclude_none=True, mode="json") if hasattr(response, "model_dump") else response

    @staticmethod
    def _error(exc: Exception) -> UpstreamError:
        return UpstreamError(getattr(exc, "status_code", 502), getattr(exc, "body", None) or str(exc))

    async def complete(self, payload: dict[str, Any], request_id: str = "", idempotency_key: str = "") -> dict[str, Any]:
        logger.debug(
            "IN:OpenAIUpstreamClient::complete started",
            extra={"request_id": request_id, "payload_keys": list(payload.keys()) if isinstance(payload, dict) else None, "idempotency_key": bool(idempotency_key)},
        )
        extra_headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        try:
            response = await self.client.chat.completions.create(**payload, extra_headers=extra_headers)
            result = self._payload(response)
            logger.debug(
                "OUT:OpenAIUpstreamClient::complete completed",
                extra={"request_id": request_id, "response_keys": list(result.keys()) if isinstance(result, dict) else None},
            )
            return result
        except UpstreamError:
            raise
        except Exception as exc:
            logger.error(
                "OpenAIUpstreamClient::complete request failed",
                extra={"request_id": request_id},
                exc_info=True,
            )
            raise self._error(exc) from exc

    @asynccontextmanager
    async def stream(self, payload: dict[str, Any], request_id: str = "", idempotency_key: str = "") -> AsyncIterator[OpenAIStreamResponse]:
        logger.debug(
            "IN:OpenAIUpstreamClient::stream started",
            extra={"request_id": request_id, "payload_keys": list(payload.keys()) if isinstance(payload, dict) else None, "idempotency_key": bool(idempotency_key)},
        )
        extra_headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        try:
            response = await self.client.chat.completions.create(**payload, extra_headers=extra_headers)
            logger.debug(
                "OUT:OpenAIUpstreamClient::stream connection established",
                extra={"request_id": request_id},
            )
            yield OpenAIStreamResponse(response)
        except UpstreamError:
            raise
        except Exception as exc:
            logger.error(
                "OpenAIUpstreamClient::stream request failed",
                extra={"request_id": request_id},
                exc_info=True,
            )
            raise self._error(exc) from exc