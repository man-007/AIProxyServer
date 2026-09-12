from typing import Any


def _extract_message(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        if "error" in payload and isinstance(payload["error"], dict):
            msg = payload["error"].get("message")
            if msg:
                return str(msg)
            if "code" in payload["error"]:
                return str(payload["error"]["code"])
        if "message" in payload:
            return str(payload["message"])
        return str(payload)
    return str(payload)


def normalize_error(status_code: int, payload: Any) -> dict[str, Any]:
    message = _extract_message(payload)
    mapping = {
        400: ("invalid_request_error", "The request was invalid or malformed."),
        401: ("authentication_error", "Authentication failed for the upstream."),
        403: ("permission_error", "The upstream rejected the request."),
        404: ("not_found_error", "The requested resource or model was not found."),
        409: ("conflict_error", "An identical request is currently being processed."),
        429: ("rate_limit_error", "The upstream rate limit was exceeded."),
        500: ("api_error", "The upstream API encountered an internal error."),
        502: ("api_error", "The upstream gateway returned an invalid response."),
        503: ("api_error", "The upstream service is temporarily unavailable."),
        504: ("api_error", "The upstream timed out."),
    }
    error_type, default_text = mapping.get(status_code, ("api_error", "The upstream API request failed."))
    return {
        "type": "error",
        "error": {"type": error_type, "message": message or default_text, "status": status_code},
    }
