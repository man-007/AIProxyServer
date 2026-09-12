# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from __future__ import annotations

from proxy_gateway.services.upstream.transports.base import UpstreamTransport


"""
TransportChain selects the transport used for upstream requests.

Contributor: @man-007
"""
class TransportChain:
    """Select exactly one upstream transport by configured client name."""

    def __init__(self, transports: dict[str, UpstreamTransport]):
        """Store transports keyed by the configured upstream client name."""
        self.transports = transports

    def resolve(self, client_name: str) -> UpstreamTransport:
        """Return the configured transport or reject an unsupported client."""
        transport = self.transports.get(client_name.lower())
        if transport is None:
            raise ValueError(f"Unsupported upstream client: {client_name}")
        return transport
