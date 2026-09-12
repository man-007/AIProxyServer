from __future__ import annotations

import hmac
from typing import Any, Dict, Optional

from fastapi import Request, HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED


class RequestValidationError(ValueError):
    pass


def validate_proxy_auth(headers: Optional[Dict[str, str]], expected_token: Optional[str]) -> None:
    if not expected_token:
        return
    if not headers:
        raise RequestValidationError("Authorization header is required.")

    auth = headers.get("Authorization") or headers.get("authorization")
    if not auth:
        raise RequestValidationError("Authorization header is required.")
    if not auth.startswith("Bearer "):
        raise RequestValidationError("Authorization header must use Bearer token format.")

    token = auth.split(" ", 1)[1].strip()
    if not hmac.compare_digest(token, expected_token):
        raise RequestValidationError("Invalid proxy authorization token.")


def proxy_auth_dependency(expected_token: Optional[str]):
    """FastAPI dependency that validates the proxy Authorization header."""
    def _dependency(request: Request) -> None:
        if not expected_token:
            return
        validate_proxy_auth(dict(request.headers), expected_token)
    return _dependency


def _ensure_message_shape(message: Dict[str, Any]) -> Dict[str, Any]:
    if "role" not in message:
        raise RequestValidationError("Each message must include a role.")
    if "content" not in message:
        raise RequestValidationError("Each message must include content.")
    return message


def validate_anthropic_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise RequestValidationError("Request body must be a JSON object.")

    if "model" not in payload or not payload.get("model"):
        raise RequestValidationError("Request is missing required field: model")

    if "messages" not in payload or not isinstance(payload.get("messages"), list) or not payload["messages"]:
        raise RequestValidationError("Request is missing required field: messages")

    for message in payload["messages"]:
        if not isinstance(message, dict):
            raise RequestValidationError("Every message must be an object.")
        _ensure_message_shape(message)

        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    raise RequestValidationError("Content blocks must be objects.")
                block_type = block.get("type")
                if block_type == "text":
                    if not isinstance(block.get("text"), str):
                        raise RequestValidationError("text blocks require string text.")
                elif block_type == "tool_result":
                    if "tool_use_id" not in block:
                        raise RequestValidationError("tool_result blocks require tool_use_id.")
                    if "content" not in block:
                        raise RequestValidationError("tool_result blocks require content.")
                elif block_type == "tool_use":
                    if "id" not in block or "name" not in block or "input" not in block:
                        raise RequestValidationError("tool_use blocks require id, name, and input.")
                elif block_type == "thinking":
                    if not isinstance(block.get("thinking"), str):
                        raise RequestValidationError("thinking blocks require string thinking content.")
                elif block_type == "image":
                    source = block.get("source")
                    if not isinstance(source, dict):
                        raise RequestValidationError("image blocks require a source object.")
                    source_type = source.get("type")
                    if source_type == "base64":
                        if not source.get("media_type") or not isinstance(source.get("data"), str):
                            raise RequestValidationError("base64 image sources require media_type and data.")
                    elif source_type == "url":
                        if not isinstance(source.get("url"), str) or not source.get("url"):
                            raise RequestValidationError("URL image sources require a URL.")
                    else:
                        raise RequestValidationError("Unsupported content block type: image source.")
                else:
                    raise RequestValidationError(f"Unsupported content block type: {block_type}")
        elif not isinstance(content, str):
            raise RequestValidationError("Message content must be a string or a list of content blocks.")

    if "max_tokens" not in payload or not payload["max_tokens"]:
        raise RequestValidationError("Request is missing required field: max_tokens")

    return payload
