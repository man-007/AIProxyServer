import json
import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import httpx

from proxy_gateway.utils.logging import get_logger


logger = get_logger("registry")


class ModelRegistry:
    """Cache upstream model metadata and resolve configured model aliases."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        models_path: str = "/v1/models",
        aliases: Optional[Dict[str, str]] = None,
        capability_overrides: Optional[Dict[str, Dict[str, bool]]] = None,
        client_factory: Optional[Callable[..., Any]] = None,
        cache_ttl_seconds: int = 300,
        timeout: float = 30.0,
    ):
        """Configure discovery, cache storage, aliases, and capability overrides."""
        logger.debug(
            "IN:ModelRegistry::__init__ started",
            extra={
                "base_url": base_url,
                "models_path": models_path,
                "aliases_present": bool(aliases),
                "capability_overrides_present": bool(capability_overrides),
                "cache_ttl_seconds": cache_ttl_seconds,
                "timeout": timeout,
            },
        )
        self.base_url = base_url.rstrip("/")
        self.models_url = f"{self.base_url}/{models_path.lstrip('/')}"
        self.api_key = api_key
        self.aliases = aliases or {}
        self.capability_overrides = capability_overrides or {}
        self.client_factory = client_factory or httpx.AsyncClient
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout = timeout
        self._models: dict[str, dict[str, Any]] = {}
        self._last_refresh: datetime | None = None
        self._refresh_lock = asyncio.Lock()
        # self.refresh(force = False)
        logger.debug("OUT:ModelRegistry::__init__ completed")

    @property
    def models(self) -> dict[str, dict[str, Any]]:
        """Return the model records currently held in the cache."""
        return self._models

    def resolve_model_id(self, model_name: str) -> str:
        """Resolve a client-facing alias to its upstream model identifier."""
        logger.debug(
            "ModelRegistry::resolve_model_id resolving model",
            extra={"model_name": model_name},
        )
        if not model_name:
            logger.debug("ModelRegistry::resolve_model_id empty model name")
            return model_name
        if model_name in self.aliases:
            resolved = self.aliases[model_name]
            logger.debug(
                "ModelRegistry::resolve_model_id alias resolved",
                extra={"model_name": model_name, "resolved": resolved},
            )
            return resolved
        logger.debug(
            "ModelRegistry::resolve_model_id no alias, returning as-is",
            extra={"model_name": model_name},
        )
        return model_name

    def is_model_known(self, model_name: str) -> bool:
        """Check whether a resolved model exists in the cached registry."""
        logger.debug(
            "ModelRegistry::is_model_known checking model",
            extra={"model_name": model_name},
        )
        resolved = self.resolve_model_id(model_name)
        known = resolved in self._models
        logger.debug(
            "ModelRegistry::is_model_known result",
            extra={"model_name": model_name, "resolved": resolved, "known": known},
        )
        return known

    def get_model(self, model_name: str) -> dict[str, Any]:
        """Return one cached model record or raise for an unknown model."""
        logger.debug(
            "ModelRegistry::get_model loading model",
            extra={"model_name": model_name},
        )
        resolved = self.resolve_model_id(model_name)
        record = self._models.get(resolved)
        if not record:
            logger.warning(
                "ModelRegistry::get_model unknown model",
                extra={"model_name": model_name, "resolved": resolved},
            )
            raise KeyError(f"Unknown model: {model_name}")
        logger.debug(
            "ModelRegistry::get_model returning record",
            extra={"model_name": model_name, "resolved": resolved, "record_keys": list(record.keys())},
        )
        return record

    def _normalize_model_record(self, model: dict[str, Any]) -> dict[str, Any]:
        """Normalize provider metadata and merge capability overrides."""
        # This is internal; we can keep as is but add debug.
        logger.debug(
            "ModelRegistry::_normalize_model_record normalizing model",
            extra={"model_id": model.get("id") if isinstance(model, dict) else None},
        )
        model_id = model.get("id")
        if not model_id:
            logger.debug("ModelRegistry::_normalize_model_record missing id, returning empty")
            return {}

        capability_base = {
            "chat": True,
            "streaming": True,
            "tool_calling": False,
            "vision": False,
            "structured_output": False,
            "reasoning": False,
        }
        discovered_capabilities = model.get("capabilities")
        if isinstance(discovered_capabilities, dict):
            capability_base.update({
                key: bool(value)
                for key, value in discovered_capabilities.items()
                if key in capability_base
            })
        override = self.capability_overrides.get(model_id, {})
        capability_base.update(override)

        normalized = {
            "id": model_id,
            "object": model.get("object", "model"),
            "created": int(model.get("created", 0) or 0),
            "owned_by": model.get("owned_by", "upstream"),
            "available": bool(model.get("available", True)),
            "capabilities": capability_base,
            "source": "upstream",
            "compatibility_status": "unknown",
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
        logger.debug(
            "ModelRegistry::_normalize_model_record completed",
            extra={"model_id": model_id, "normalized_keys": list(normalized.keys())},
        )
        return normalized

    async def refresh(self, force: bool = False, request_id: str = "") -> dict[str, dict[str, Any]]:
        """Refresh stale metadata and atomically replace the model cache."""
        logger.debug(
            "IN:ModelRegistry::refresh started",
            extra={"force": force, "request_id": request_id},
        )
        async with self._refresh_lock:
            now = datetime.now(timezone.utc)
            if not force and self._last_refresh is not None:
                elapsed = (now - self._last_refresh).total_seconds()
                if elapsed < self.cache_ttl_seconds:
                    logger.debug(
                        "ModelRegistry::refresh cache hit",
                        extra={"model_count": len(self._models), "age_seconds": round(elapsed, 2), "request_id": request_id},
                    )
                    logger.debug("ModelRegistry::refresh returning cached")
                    return dict(self._models)

            logger.info("ModelRegistry::refresh upstream refresh started", extra={"force": force, "request_id": request_id})
            try:
                async with self.client_factory(timeout=self.timeout) as client:
                    response = await client.get(
                        self.models_url,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    response.raise_for_status()
                    payload = response.json()
            except Exception:
                if self._models:
                    logger.warning(
                        "ModelRegistry::refresh refresh failed, using stale cache",
                        extra={"model_count": len(self._models), "request_id": request_id},
                        exc_info=True,
                    )
                    logger.debug("ModelRegistry::refresh returning stale cache")
                    return dict(self._models)
                logger.error("ModelRegistry::refresh refresh failed without cache", extra={"request_id": request_id}, exc_info=True)
                raise

            refreshed_models: dict[str, dict[str, Any]] = {}
            for item in payload.get("data", []):
                normalized = self._normalize_model_record(item)
                if normalized:
                    refreshed_models[normalized["id"]] = normalized

            self._models = refreshed_models
            self._last_refresh = now
            logger.info("OUT:ModelRegistry::refresh completed", extra={"model_count": len(self._models), "request_id": request_id})
            return dict(self._models)

    def to_openai_model_list(self) -> dict[str, Any]:
        """Return cached models in the OpenAI-compatible list response shape."""
        logger.debug(
            "ModelRegistry::to_openai_model_list building model list",
            extra={"model_count": len(self._models)},
        )
        result = {"object": "list", "data": [
            {"id": model_id, "object": "model", "created": model.get("created", 0), "owned_by": model.get("owned_by", "upstream")}
            for model_id, model in self._models.items()
        ]}
        logger.debug(
            "ModelRegistry::to_openai_model_list completed",
            extra={"result_data_length": len(result["data"])},
        )
        return result