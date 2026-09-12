from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from proxy_gateway.config import settings
from proxy_gateway.diagnostics import get_logger, log_method_entry_exit, normalize_error
from proxy_gateway.state import registry
from proxy_gateway.validation import proxy_auth_dependency

logger = get_logger("server")
router = APIRouter()


@router.get("/v1/models")
@log_method_entry_exit("server")
async def list_models(request: Request, _: None = Depends(proxy_auth_dependency(settings.proxy_api_key if settings.proxy_auth_enabled else None))) -> dict[str, Any]:
    if not settings.upstream_api_key:
        raise HTTPException(
            status_code=500,
            detail=normalize_error(500, "UPSTREAM_API_KEY is not configured"),
        )

    try:
        if settings.model_discovery_enabled:
            await registry.refresh(force=False)
        return registry.to_openai_model_list()
    except Exception as exc:
        logger.error("list_models::list_models model list request failed", extra={"request_id": getattr(request.state, "request_id", None)}, exc_info=True)
        raise HTTPException(status_code=502, detail=normalize_error(502, str(exc)))
