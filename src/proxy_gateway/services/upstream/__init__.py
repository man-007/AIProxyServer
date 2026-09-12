# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from proxy_gateway.services.upstream.errors import UpstreamError
from proxy_gateway.services.upstream.factory import build_upstream_client
from proxy_gateway.services.upstream.chains import ModelUpstreamChain, TransportChain
from proxy_gateway.services.upstream.contracts import ModelUpstreamHandler, UpstreamStream, UpstreamTransport
from proxy_gateway.services.upstream.handlers import GenericModelUpstreamHandler, KimiK3UpstreamHandler, UpstreamHandler
from proxy_gateway.services.upstream.transports import HttpxUpstreamClient, OpenAIStreamResponse, OpenAIUpstreamClient, UpstreamTransport

"""
Composition root for the upstream services in the proxy gateway.

Contributor: @man-007
"""
__all__ = [
    "KimiK3UpstreamHandler",
    "ModelUpstreamChain",
    "ModelUpstreamHandler",
    "GenericModelUpstreamHandler",
    "HttpxUpstreamClient",
    "OpenAIStreamResponse",
    "OpenAIUpstreamClient",
    "TransportChain",
    "UpstreamHandler",
    "UpstreamError",
    "UpstreamStream",
    "UpstreamTransport",
    "build_upstream_client",
]
