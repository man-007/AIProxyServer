# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from proxy_gateway.diagnostics.errors import normalize_error
from proxy_gateway.diagnostics.exceptions import GatewayUnavailableError, ModelUnavailableError
from proxy_gateway.utils.logging import (
    JsonFormatter,
    configure_logging,
    get_logger,
    log_method_entry_exit,
    new_request_id,
    normalize_log_level,
)

"""
Diagnostics components for the proxy gateway, including error normalization and custom exception handling.
This module serves as the entry point for importing all diagnostics-related components.
It provides easy access to the main diagnostics components used throughout the proxy gateway.   

Contributor: @man-007
"""
__all__ = [
    "normalize_error",
    "GatewayUnavailableError",
    "ModelUnavailableError",
    "JsonFormatter",
    "configure_logging",
    "get_logger",
    "log_method_entry_exit",
    "new_request_id",
    "normalize_log_level",
]
