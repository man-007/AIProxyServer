# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from proxy_gateway.services.gateway import GatewayService
from proxy_gateway.diagnostics.exceptions import GatewayUnavailableError, ModelUnavailableError

"""
Gateway-related utilities and exceptions for the proxy gateway.

Contributor: @man-007
"""
__all__ = ["GatewayService", "GatewayUnavailableError", "ModelUnavailableError"]
