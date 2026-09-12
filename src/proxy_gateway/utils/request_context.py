# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from dataclasses import dataclass, field
from typing import Any

"""
RequestContext carries request metadata through the proxy pipeline.

Contributor: @man-007
"""
@dataclass
class RequestContext:
    """Carry normalized request data and routing decisions through the gateway."""

    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    client_host: str | None = None
    protocol: str | None = None
    provider_name: str | None = None
    destination: str | None = None

    @classmethod
    def from_request(
        cls,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        request_id: str = "",
        client_host: str | None = None,
    ) -> "RequestContext":
        """Create a context with case-insensitive normalized HTTP header names."""
        normalized_headers = {
            key.lower(): value for key, value in (headers or {}).items()
        }
        return cls(
            method=method.upper(),
            path=path,
            headers=normalized_headers,
            body=body or {},
            request_id=request_id,
            client_host=client_host,
        )
