# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
# Contributor: @man-007
from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any
from typing import TypeVar

from proxy_gateway.diagnostics import get_logger
from proxy_gateway.metrics import IDEMPOTENCY_REJECTED


"""
Idempotency utilities for the proxy gateway, including request key generation and in-flight request coordination.

Contributor: @man-007
"""
logger = get_logger("idempotency")
ResultT = TypeVar("ResultT")


def request_key(payload: dict[str, Any], supplied_key: str = "") -> str:
    """Return a stable opaque key without logging or exposing request content."""
    if supplied_key.strip():
        digest = hashlib.sha256(supplied_key.strip().encode("utf-8")).hexdigest()
    else:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"proxy-{digest}"


"""
DuplicateRequestError identifies an already-running duplicate request.
"""
class DuplicateRequestError(RuntimeError):
    """Signal that an equivalent request is already active."""

    pass


"""
InFlightRequestCoordinator prevents duplicate work for active requests.
"""
class InFlightRequestCoordinator:
    """Reject identical requests while the original request is active."""

    def __init__(self, max_entries: int = 10000):
        """Initialize the bounded active-request set and synchronization lock."""
        self.max_entries = max_entries
        self._lock = asyncio.Lock()
        self._active: set[str] = set()

    async def execute(self, key: str, operation: Callable[[], Awaitable[ResultT]], request_id: str = "") -> ResultT:
        """Run a completion while preventing another request with the same key."""
        async with self._lock:
            if key in self._active:
                logger.warning("InFlightRequestCoordinator::execute duplicate request rejected", extra={"request_key": key, "request_id": request_id})
                IDEMPOTENCY_REJECTED.inc()
                raise DuplicateRequestError("An identical request is currently being processed.")
            if len(self._active) >= self.max_entries:
                raise DuplicateRequestError("Too many in-flight requests.")
            self._active.add(key)

        try:
            return await operation()
        finally:
            async with self._lock:
                self._active.discard(key)

    async def claim_stream(self, key: str, request_id: str = "") -> None:
        """Reserve a stream key until the route releases it."""
        async with self._lock:
            if key in self._active:
                logger.warning("InFlightRequestCoordinator::claim_stream duplicate stream rejected", extra={"request_key": key, "request_id": request_id})
                IDEMPOTENCY_REJECTED.inc()
                raise DuplicateRequestError("An identical request is currently being processed.")
            if len(self._active) >= self.max_entries:
                raise DuplicateRequestError("Too many in-flight streams.")
            self._active.add(key)

    async def release_stream(self, key: str, request_id: str = "") -> None:
        """Release a stream key after completion or client disconnect."""
        async with self._lock:
            self._active.discard(key)
