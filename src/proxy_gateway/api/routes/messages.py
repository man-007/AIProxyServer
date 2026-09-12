import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from proxy_gateway.config import settings
from proxy_gateway.diagnostics import (
    GatewayUnavailableError,
    ModelUnavailableError,
    get_logger,
    log_method_entry_exit,
    normalize_error,
)
from proxy_gateway.idempotency import DuplicateRequestError, request_key
from proxy_gateway.state import gateway, protocol_adapters, request_coordinator, upstream_client
from proxy_gateway.upstream import UpstreamError
from proxy_gateway.validation import RequestValidationError, proxy_auth_dependency
from proxy_gateway.utils.request_context import RequestContext

logger = get_logger("server")
router = APIRouter()


@router.post("/v1/messages", include_in_schema=False)
@log_method_entry_exit("server")
async def anthropic_messages(request: Request, _: None = Depends(proxy_auth_dependency(settings.proxy_api_key if settings.proxy_auth_enabled else None))) -> Any:
    """Validate, translate, execute, and format one Anthropic Messages request."""
    try:
        payload = await request.json()
    except ValueError as exc:
        logger.warning("anthropic_messages::anthropic_messages invalid JSON", extra={"request_id": getattr(request.state, "request_id", None)})
        raise HTTPException(status_code=400, detail=normalize_error(400, str(exc)))
    context = RequestContext.from_request(
        method=request.method,
        path=request.url.path,
        headers=dict(request.headers),
        body=payload,
        request_id=getattr(request.state, "request_id", ""),
        client_host=request.client.host if request.client else None,
    )
    adapter = protocol_adapters.resolve(context)
    if adapter is None:
        logger.warning("anthropic_messages::anthropic_messages unsupported protocol endpoint", extra={"request_id": getattr(request.state, "request_id", None), "path": request.url.path})
        raise HTTPException(status_code=404, detail=normalize_error(404, "Unsupported protocol endpoint"))

    try:
        transformed = await gateway.prepare(adapter, payload, request_id=getattr(request.state, "request_id", ""))
    except RequestValidationError as exc:
        status_code = 500 if "UPSTREAM_API_KEY" in str(exc) else 400
        logger.warning(
            "anthropic_messages::anthropic_messages request validation failed",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "status_code": status_code,
                "reason": str(exc),
            },
        )
        raise HTTPException(status_code=status_code, detail=normalize_error(status_code, str(exc)))
    except ModelUnavailableError as exc:
        logger.warning("anthropic_messages::anthropic_messages model unavailable", extra={"request_id": getattr(request.state, "request_id", None)})
        raise HTTPException(
            status_code=404,
            detail=normalize_error(404, str(exc)),
        )
    except GatewayUnavailableError as exc:
        logger.error("anthropic_messages::anthropic_messages gateway unavailable", extra={"request_id": getattr(request.state, "request_id", None)}, exc_info=True)
        raise HTTPException(status_code=502, detail=normalize_error(502, str(exc)))

    logger.info(
        "anthropic_messages::anthropic_messages upstream request prepared",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "model": transformed.get("model"),
            "stream": bool(transformed.get("stream")),
            "tool_calls": bool(transformed.get("tools")),
        },
    )
    idempotency_key = request_key(
        transformed,
        supplied_key=request.headers.get("idempotency-key", ""),
    )

    if transformed.get("stream"):
        try:
            await request_coordinator.claim_stream(idempotency_key, request_id=getattr(request.state, "request_id", ""))
        except DuplicateRequestError as exc:
            logger.warning(
                "anthropic_messages::anthropic_messages duplicate stream rejected",
                extra={"request_id": getattr(request.state, "request_id", None)},
            )
            raise HTTPException(status_code=409, detail=normalize_error(409, str(exc)))

        async def stream_response():
            """Yield translated server-sent events and release the stream reservation."""
            assembler = adapter.create_stream_assembler()
            stream_started_at = time.perf_counter()
            emitted_events = 0
            received_upstream_event = False
            logger.debug(
                "stream_response::stream_response stream response started",
                extra={"request_id": getattr(request.state, "request_id", None)},
            )
            try:
                async with upstream_client.stream(
                    transformed,
                    request_id=getattr(request.state, "request_id", ""),
                    idempotency_key=idempotency_key,
                ) as upstream:
                    logger.debug(
                        "stream_response::stream_response upstream connected",
                        extra={"request_id": getattr(request.state, "request_id", None)},
                    )
                    async for line in upstream.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            events = assembler.finish() if received_upstream_event else []
                        else:
                            try:
                                decoded = json.loads(data)
                            except (ValueError, json.JSONDecodeError):
                                continue
                            received_upstream_event = True
                            events = assembler.consume(decoded)
                        for event in events:
                            emitted_events += 1
                            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
                    if not received_upstream_event:
                        raise UpstreamError(502, "The upstream returned an empty stream.")
                    for event in assembler.finish():
                        emitted_events += 1
                        yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
            except UpstreamError as exc:
                logger.error("stream_response::stream_response upstream failed", extra={"request_id": getattr(request.state, "request_id", None), "status_code": exc.status_code}, exc_info=True)
                error = normalize_error(exc.status_code, exc.payload)
                yield f"event: error\ndata: {json.dumps(error)}\n\n"
            except Exception:
                logger.exception("stream_response::stream_response translation failed", extra={"request_id": getattr(request.state, "request_id", None)})
                error = normalize_error(502, "The upstream stream could not be translated.")
                yield f"event: error\ndata: {json.dumps(error)}\n\n"
            finally:
                logger.debug(
                    "stream_response::stream_response stream response finished",
                    extra={
                        "request_id": getattr(request.state, "request_id", None),
                        "duration_ms": round((time.perf_counter() - stream_started_at) * 1000, 2),
                        "emitted_events": emitted_events,
                    },
                )
                await request_coordinator.release_stream(idempotency_key, request_id=getattr(request.state, "request_id", ""))

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    async def complete_request() -> dict[str, Any]:
        """Execute the prepared non-streaming request through the upstream client."""
        return await upstream_client.complete(
            transformed,
            request_id=getattr(request.state, "request_id", ""),
            idempotency_key=idempotency_key,
        )

    try:
        data = await request_coordinator.execute(idempotency_key, complete_request, request_id=getattr(request.state, "request_id", ""))
    except DuplicateRequestError as exc:
        logger.warning(
            "anthropic_messages::anthropic_messages duplicate completion rejected",
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        raise HTTPException(status_code=409, detail=normalize_error(409, str(exc)))
    except UpstreamError as exc:
        logger.error("anthropic_messages::anthropic_messages completion upstream failed", extra={"request_id": getattr(request.state, "request_id", None), "status_code": exc.status_code}, exc_info=True)
        raise HTTPException(status_code=exc.status_code, detail=normalize_error(exc.status_code, exc.payload))
    return JSONResponse(content=adapter.from_upstream(data))
