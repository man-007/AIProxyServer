# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
"""
ModelUnavailableError indicates that a requested model is unavailable.

Contributor: @man-007
"""
class ModelUnavailableError(LookupError):
    pass


"""
GatewayUnavailableError indicates that the gateway cannot serve a request.

Contributor: @man-007
"""
class GatewayUnavailableError(RuntimeError):
    pass
