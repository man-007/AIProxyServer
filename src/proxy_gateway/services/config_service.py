from __future__ import annotations

import asyncio
import math
from dataclasses import replace
from typing import Any

from proxy_gateway.config import Settings, _validated_https_url
from proxy_gateway.diagnostics import get_logger
from proxy_gateway.model_registry import ModelRegistry
from proxy_gateway.services.gateway import GatewayService
from proxy_gateway.services.upstream import build_upstream_client
from proxy_gateway.utils.logging import configure_logging


logger = get_logger("config_service")


class ConfigService:
    """Validate and apply configuration changes to the running proxy process."""

    _EDITABLE_FIELDS = {
        "upstream_base_url",
        "models_path",
        "chat_path",
        "upstream_api_key",
        "api_key",
        "upstream_client",
        "model_discovery_enabled",
        "log_level",
        "request_timeout_seconds",
        "default_model",
    }
    _SETTING_FIELD_NAMES = {
        "request_timeout_seconds": "upstream_timeout_seconds",
        "api_key": "upstream_api_key",
    }

    def __init__(self, settings: Settings, registry: ModelRegistry, gateway: GatewayService, upstream_client: Any):
        """Store the singleton settings and services affected by runtime updates."""
        self.settings = settings
        self.registry = registry
        self.gateway = gateway
        self.upstream_client = upstream_client
        self._lock = asyncio.Lock()

    async def public_config(self) -> dict[str, Any]:
        """Return non-secret settings that are safe to display in Swagger."""
        async with self._lock:
            return self._snapshot()

    def _snapshot(self) -> dict[str, Any]:
        """Build a snapshot of editable, non-secret settings while the lock is held."""
        return {
            "upstream_base_url": self.settings.upstream_base_url,
            "upstream_client": self.settings.upstream_client,
            "upstream_api_key": self.settings.upstream_api_key,
            "models_path": self.settings.models_path,
            "chat_path": self.settings.chat_path,
            "model_discovery_enabled": self.settings.model_discovery_enabled,
            "default_model": self.settings.default_model,
            "log_level": self.settings.log_level,
            "request_timeout_seconds": self.settings.upstream_timeout_seconds,
        }

    def _build_candidate(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Validate all proposed values before changing live configuration."""
        if "api_key" in changes and "upstream_api_key" in changes:
            raise ValueError("Use either api_key or upstream_api_key, not both")
        normalized_changes = dict(changes)
        if "api_key" in normalized_changes:
            normalized_changes["upstream_api_key"] = normalized_changes.pop("api_key")

        candidate = {
            field: getattr(self.settings, self._SETTING_FIELD_NAMES.get(field, field))
            for field in self._EDITABLE_FIELDS
            if field != "api_key"
        }
        candidate.update(normalized_changes)
        candidate["upstream_base_url"] = _validated_https_url(str(candidate["upstream_base_url"] or ""))
        candidate["models_path"] = str(candidate["models_path"] or "")
        candidate["chat_path"] = str(candidate["chat_path"] or "")
        candidate["upstream_api_key"] = str(candidate["upstream_api_key"] or "")
        candidate["upstream_client"] = str(candidate["upstream_client"] or "").lower()
        try:
            candidate["request_timeout_seconds"] = float(candidate["request_timeout_seconds"])
        except (TypeError, ValueError) as exc:
            raise ValueError("request_timeout_seconds must be a number") from exc
        if candidate["upstream_client"] not in {"httpx", "openai"}:
            raise ValueError("upstream_client must be either 'httpx' or 'openai'")
        if not math.isfinite(candidate["request_timeout_seconds"]) or candidate["request_timeout_seconds"] <= 0:
            raise ValueError("request_timeout_seconds must be a finite positive number")
        for field in ("models_path", "chat_path"):
            if not candidate[field].startswith("/") or "?" in candidate[field] or "#" in candidate[field]:
                raise ValueError(f"{field} must start with '/' without query or fragment")
        if not isinstance(candidate["model_discovery_enabled"], bool):
            raise ValueError("model_discovery_enabled must be a boolean")
        if "default_model" in changes and (not isinstance(candidate["default_model"], str) or not candidate["default_model"].strip()):
            raise ValueError("default_model must be a non-empty string")
        if not isinstance(candidate["log_level"], str):
            raise ValueError("log_level must be a string")
        from proxy_gateway.utils.logging import normalize_log_level
        normalize_log_level(candidate["log_level"])
        if "upstream_api_key" in normalized_changes and not candidate["upstream_api_key"].strip():
            raise ValueError("api_key must be a non-empty string")
        candidate_settings = replace(
            self.settings,
            upstream_base_url=candidate["upstream_base_url"],
            models_path=candidate["models_path"],
            chat_path=candidate["chat_path"],
            upstream_api_key=candidate["upstream_api_key"],
            upstream_client=candidate["upstream_client"],
            upstream_timeout_seconds=candidate["request_timeout_seconds"],
            model_discovery_enabled=candidate["model_discovery_enabled"],
            log_level=candidate["log_level"],
            default_model=candidate["default_model"],
        )
        candidate_settings.validate()
        return candidate

    async def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Validate and apply all non-secret settings exposed by the config API."""
        unknown = set(changes) - self._EDITABLE_FIELDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"Runtime updates are not allowed for: {names}")

        async with self._lock:
            candidate = self._build_candidate(changes)
            replacement = build_upstream_client(
                base_url=candidate["upstream_base_url"],
                api_key=candidate["upstream_api_key"],
                chat_path=candidate["chat_path"],
                client_name=candidate["upstream_client"],
                timeout=candidate["request_timeout_seconds"],
            )
            self.settings.upstream_base_url = candidate["upstream_base_url"]
            self.settings.models_path = candidate["models_path"]
            self.settings.chat_path = candidate["chat_path"]
            self.settings.upstream_api_key = candidate["upstream_api_key"]
            self.settings.upstream_client = candidate["upstream_client"]
            self.settings.upstream_timeout_seconds = candidate["request_timeout_seconds"]
            self.settings.model_discovery_enabled = candidate["model_discovery_enabled"]
            self.settings.log_level = str(candidate["log_level"])
            self.settings.default_model = str(candidate["default_model"] or "")
            configure_logging(self.settings.log_level)

            self.registry.base_url = self.settings.upstream_base_url
            self.registry.models_url = f"{self.registry.base_url}/{self.settings.models_path.lstrip('/')}"
            self.registry.api_key = self.settings.upstream_api_key
            self.registry.timeout = self.settings.upstream_timeout_seconds
            self.gateway.model_discovery_enabled = self.settings.model_discovery_enabled
            self.gateway.api_key = self.settings.upstream_api_key
            self.upstream_client.__dict__.clear()
            self.upstream_client.__dict__.update(replacement.__dict__)
            logger.info(
                "ConfigService::update configuration updated",
                extra={"fields": sorted(changes)},
            )
            return self._snapshot()