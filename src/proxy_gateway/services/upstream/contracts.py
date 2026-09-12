# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
# Contributor: @man-007
from __future__ import annotations

from typing import AsyncIterator, Protocol

from proxy_gateway.services.upstream.transports.base import UpstreamTransport


"""
UpstreamStream defines the asynchronous upstream stream contract.

Contributor: @man-007
"""
class UpstreamStream(Protocol):
    """Describe the line iterator exposed by a streaming upstream response."""

    async def aiter_lines(self) -> AsyncIterator[str]:
        """Yield raw server-sent-event lines from the upstream transport."""
        ...


"""
ModelUpstreamHandler defines model-specific upstream behavior.

Contributor: @man-007
"""
class ModelUpstreamHandler(Protocol):
    """Define model matching and transport creation for upstream handlers."""

    def can_handle(self, model: str) -> bool:
        """Report whether this handler owns the requested model."""
        ...

    def client(self) -> UpstreamTransport:
        """Return the transport configured for the matched model."""
        ...
