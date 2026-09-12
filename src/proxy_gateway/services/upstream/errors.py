# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
# Contributor: @man-007
from __future__ import annotations

import json
from typing import Any

import httpx


"""
UpstreamError represents a normalized upstream provider failure.

Contributor: @man-007
"""
class UpstreamError(RuntimeError):
    def __init__(self, status_code: int, payload: Any):
        super().__init__(str(payload))
        self.status_code = status_code
        self.payload = payload


def error_metadata(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    error = payload.get("error") if isinstance(payload.get("error"), dict) else payload
    metadata = {}
    for field in ("type", "code"):
        if error.get(field) is not None:
            metadata[field] = str(error[field])
    return metadata


async def raise_for_upstream_error(response: httpx.Response) -> None:
    if response.status_code == 202:
        request_id = response.headers.get("nvcf-reqid", "unknown")
        raise UpstreamError(
            503,
            f"The upstream accepted the request but it is still pending (request id: {request_id}).",
        )
    if response.status_code < 400:
        return
    await response.aread()
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        payload = response.text
    raise UpstreamError(response.status_code, payload)
