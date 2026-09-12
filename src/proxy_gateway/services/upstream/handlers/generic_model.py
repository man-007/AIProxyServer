from __future__ import annotations

from proxy_gateway.services.upstream.handlers.base import UpstreamHandler
from proxy_gateway.diagnostics import get_logger

logger = get_logger("generic_model_handler")


class GenericModelUpstreamHandler(UpstreamHandler):
    def can_handle(self, model: str) -> bool:
        logger.debug(
            "GenericModelUpstreamHandler.can_handle called",
            extra={"model": model, "result": bool(model)},
        )
        return bool(model)