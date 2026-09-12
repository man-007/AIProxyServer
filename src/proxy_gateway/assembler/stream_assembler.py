# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from abc import ABC, abstractmethod
from typing import Any

"""
StreamAssembler defines the interface for assembling streamed responses.

Contributor: @man-007
"""
class StreamAssembler(ABC):
    """Define the interface for stateful upstream-to-client stream conversion."""

    @abstractmethod
    def consume(self, chunk: dict[str, Any]) -> list[dict[str, Any]]:
        """Consume one upstream chunk and return client-facing events."""
        pass
