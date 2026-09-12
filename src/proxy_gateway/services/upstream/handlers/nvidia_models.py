# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from __future__ import annotations

from proxy_gateway.services.upstream.handlers.base import UpstreamHandler


"""
GenericModelUpstreamHandler handles standard NVIDIA model requests.

Contributor: @man-007
"""
class GenericModelUpstreamHandler(UpstreamHandler):
    def can_handle(self, model: str) -> bool:
        return bool(model)
