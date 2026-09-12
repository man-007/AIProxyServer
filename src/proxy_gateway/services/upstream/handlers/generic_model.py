# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from __future__ import annotations

from proxy_gateway.services.upstream.handlers.base import UpstreamHandler
from proxy_gateway.diagnostics import get_logger

logger = get_logger("generic_model_handler")


"""
GenericModelUpstreamHandler handles generic model requests.

Contributor: @man-007
"""
class GenericModelUpstreamHandler(UpstreamHandler):
    def can_handle(self, model: str) -> bool:
        logger.debug(
            "GenericModelUpstreamHandler.can_handle called",
            extra={"model": model, "result": bool(model)},
        )
        return bool(model)