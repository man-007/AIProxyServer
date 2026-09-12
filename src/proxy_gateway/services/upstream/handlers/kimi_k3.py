# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from __future__ import annotations

from proxy_gateway.services.upstream.handlers.base import UpstreamHandler
from proxy_gateway.diagnostics import get_logger

logger = get_logger("kimi_k3_handler")


"""
KimiK3UpstreamHandler handles Kimi K3 model requests.

Contributor: @man-007
"""
class KimiK3UpstreamHandler(UpstreamHandler):
    model_id = "moonshotai/kimi-k3"

    def can_handle(self, model: str) -> bool:
        logger.debug(
            "KimiK3UpstreamHandler.can_handle called",
            extra={"model": model, "model_id": self.model_id, "result": model == self.model_id},
        )
        return model == self.model_id