# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
# Contributor: @man-007
from .metrics import IDEMPOTENCY_REJECTED, MetricsMiddleware, metrics_endpoint

"""
Metrics components for the proxy gateway, including request counting, latency measurement, and cache hit/miss tracking.
This module serves as the entry point for importing all metrics-related components.
It provides easy access to the main metrics components used throughout the proxy gateway.

Contributor: @man-007
"""
__all__ = ["IDEMPOTENCY_REJECTED", "MetricsMiddleware", "metrics_endpoint"]
