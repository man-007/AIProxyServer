import logging
import json
import sys
import uuid
import inspect
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, cast, get_type_hints


_STANDARD_LOG_FIELDS = set(logging.LogRecord(None, 0, "", 0, "", (), None).__dict__)
F = TypeVar("F", bound=Callable[..., Any])


def _redact(value: object) -> object:
    if isinstance(value, str):
        for marker in ("Bearer ", "api_key", "API_KEY", "PROXY_API_KEY"):
            if marker in value:
                return "[REDACTED]"
    return value


# Logging guideline:
# - Use exc_info=True only for unexpected exceptions; expected validation/business warnings should omit it.


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = {
            key: _redact(value)
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_FIELDS and not key.startswith("_")
        }
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact(record.getMessage()),
            **fields,
        }
        if record.exc_info:
            payload["exception"] = _redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def normalize_log_level(level: str) -> int:
    normalized = level.upper()
    if normalized == "WARN":
        normalized = "WARNING"
    numeric_level = getattr(logging, normalized, None)
    if not isinstance(numeric_level, int):
        raise ValueError("LOG_LEVEL must be one of DEBUG, INFO, WARN, WARNING, or ERROR.")
    if numeric_level not in {logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR}:
        raise ValueError("LOG_LEVEL must be one of DEBUG, INFO, WARN, WARNING, or ERROR.")
    return numeric_level


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("proxy_gateway")
    logger.setLevel(normalize_log_level(level))
    logger.propagate = True

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    return logger


def get_logger(component: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(
        "proxy_gateway" if not component else f"proxy_gateway.{component}"
    )


def log_method_entry_exit(component: Optional[str] = None) -> Callable[[F], F]:
    """Log method boundaries without logging arguments or return payloads."""
    def decorator(function: F) -> F:
        method_logger = get_logger(component or function.__module__.rsplit(".", 1)[-1])
        symbol = function.__name__
        prefix = f"{component or function.__module__.rsplit('.', 1)[-1]}:#sym:{symbol}"

        try:
            resolved_annotations = get_type_hints(function)
        except (NameError, TypeError):
            resolved_annotations = getattr(function, "__annotations__", {})

        original_signature = inspect.signature(function)
        resolved_signature = original_signature.replace(
            parameters=[
                parameter.replace(
                    annotation=resolved_annotations.get(parameter.name, parameter.annotation)
                )
                for parameter in original_signature.parameters.values()
            ],
            return_annotation=resolved_annotations.get("return", original_signature.return_annotation),
        )

        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                method_logger.debug("IN:%s entry", prefix.replace(":#sym:", "::"))
                try:
                    return await function(*args, **kwargs)
                finally:
                    method_logger.debug("OUT:%s exit", prefix.replace(":#sym:", "::"))

            async_wrapper.__annotations__ = resolved_annotations
            async_wrapper.__signature__ = resolved_signature
            return cast(F, async_wrapper)

        @wraps(function)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            method_logger.debug("IN:%s entry", prefix.replace(":#sym:", "::"))
            try:
                return function(*args, **kwargs)
            finally:
                method_logger.debug("OUT:%s exit", prefix.replace(":#sym:", "::"))

        sync_wrapper.__annotations__ = resolved_annotations
        sync_wrapper.__signature__ = resolved_signature
        return cast(F, sync_wrapper)

    return decorator


def new_request_id() -> str:
    return uuid.uuid4().hex
