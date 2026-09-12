from __future__ import annotations

from proxy_gateway.services.upstream.handlers.base import UpstreamHandler


class GenericModelUpstreamHandler(UpstreamHandler):
    def can_handle(self, model: str) -> bool:
        return bool(model)
