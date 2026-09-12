# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from proxy_gateway.diagnostics import get_logger, log_method_entry_exit
from proxy_gateway.services.state import config_service


logger = get_logger("config_routes")
router = APIRouter(prefix="", tags=["Configuration"])

"""
ConfigUpdate describes settings accepted by the runtime configuration API.

Contributor: @man-007
"""
class ConfigUpdate(BaseModel):
    """Document settings that can be changed at runtime; the API key is write-only."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_discovery_enabled: bool | None = Field(default=None, description="Enable or disable model discovery at runtime.")
    log_level: str | None = Field(default=None, description="Logging level for the application.")
    upstream_base_url: str | None = Field(default=None, description="Base URL for the upstream service.")
    models_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("models_path", "UPSTREAM_MODELS_PATH"),
        description="UPSTREAM_MODELS_PATH used for model discovery.",
    )
    chat_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("chat_path", "UPSTREAM_CHAT_COMPLETIONS_PATH"),
        description="UPSTREAM_CHAT_COMPLETIONS_PATH used for chat requests.",
    )
    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("api_key", "upstream_api_key", "UPSTREAM_API_KEY"),
        description="Upstream API key used for upstream requests.",
    )
    upstream_client: str | None = Field(default=None, description="Client identifier for the upstream service.")
    request_timeout_seconds: float | None = Field(default=None, description="Request timeout for the upstream service in seconds.")
    default_model: str | None = Field(default=None, description="Default model to use if none is specified, please choose an known model present in the registry.")


@router.get("/config")
@log_method_entry_exit("config_routes")
async def get_config() -> dict[str, Any]:
    """Return non-secret runtime configuration for the Swagger UI."""
    return await config_service.public_config()


@router.patch("/config")
@log_method_entry_exit("config_routes")
async def update_config(changes: ConfigUpdate) -> dict[str, Any]:
    """Apply supported runtime settings without returning secret values."""
    try:
        return await config_service.update(changes.model_dump(exclude_unset=True, exclude_none=True))
    except ValueError as exc:
        logger.warning("update_config::update_config invalid configuration", extra={"reason": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc