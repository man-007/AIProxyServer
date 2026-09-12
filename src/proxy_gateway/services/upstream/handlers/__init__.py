# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from proxy_gateway.services.upstream.handlers.base import UpstreamHandler
from proxy_gateway.services.upstream.handlers.kimi_k3 import KimiK3UpstreamHandler
from proxy_gateway.services.upstream.handlers.generic_model import GenericModelUpstreamHandler

"""
Upstream handler implementations for the proxy gateway, including generic model and Kimi K3 handlers.
This module serves as the entry point for importing all upstream handler implementations.

Contributor: @man-007
"""
__all__ = ["GenericModelUpstreamHandler", "KimiK3UpstreamHandler", "UpstreamHandler"]
