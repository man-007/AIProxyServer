# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from typing import Any


"""
UpstreamTransport defines the interface for upstream clients.

Contributor: @man-007
"""
class UpstreamTransport(ABC):
    """Common contract and configuration for upstream transport implementations."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @abstractmethod
    async def complete(
        self,
        payload: dict[str, Any],
        request_id: str = "",
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        """Complete a chat request using the transport implementation."""

    @abstractmethod
    def stream(
        self,
        payload: dict[str, Any],
        request_id: str = "",
        idempotency_key: str = "",
    ) -> AbstractAsyncContextManager[Any]:
        """Return an async context manager for a streaming chat request."""
