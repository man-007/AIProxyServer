import asyncio
import json
import logging

import pytest

from proxy_gateway.config import Settings
from proxy_gateway.diagnostics import JsonFormatter, log_method_entry_exit, normalize_log_level
from proxy_gateway.middleware import InMemoryRateLimitStore
from proxy_gateway.assembler.anthropic_stream_assembler import AnthropicStreamAssembler
from proxy_gateway.validation import RequestValidationError, validate_anthropic_request


def test_settings_reject_auth_without_proxy_key():
    with pytest.raises(ValueError, match="PROXY_API_KEY"):
        Settings(proxy_auth_enabled=True, proxy_api_key="").validate()


def test_settings_reject_non_loopback_without_auth():
    with pytest.raises(ValueError, match="PROXY_AUTH_ENABLED"):
        Settings(host="0.0.0.0", proxy_auth_enabled=False).validate()


def test_settings_reject_nonpositive_upstream_timeout():
    with pytest.raises(ValueError, match="UPSTREAM_TIMEOUT_SECONDS"):
        Settings(upstream_timeout_seconds=0).validate()


def test_rate_limit_settings_are_configurable():
    settings = Settings(rate_limit_enabled=True, rate_limit_requests_per_minute=30)
    settings.validate()
    assert settings.rate_limit_requests_per_minute == 30


def test_rate_limit_can_be_disabled_without_validating_rate_value():
    settings = Settings(rate_limit_enabled=False, rate_limit_requests_per_minute=0)
    settings.validate()
    assert settings.rate_limit_enabled is False


def test_log_level_normalizes_warn_and_rejects_unknown_values():
    assert normalize_log_level("debug") == logging.DEBUG
    assert normalize_log_level("WARN") == logging.WARNING
    with pytest.raises(ValueError, match="LOG_LEVEL"):
        normalize_log_level("trace")


def test_json_formatter_includes_safe_structured_fields():
    record = logging.LogRecord("test", logging.INFO, "", 0, "request completed", (), None)
    record.request_id = "request-1"
    formatted = json.loads(JsonFormatter().format(record))

    assert formatted["message"] == "request completed"
    assert formatted["request_id"] == "request-1"


def test_method_boundary_logger_emits_entry_and_exit(caplog):
    @log_method_entry_exit("test")
    def sample_method():
        return "ok"

    with caplog.at_level(logging.DEBUG, logger="proxy_gateway.test"):
        assert sample_method() == "ok"

    def _get_log_message(record):
        msg = record.getMessage()
        try:
            parsed = json.loads(msg)
            return parsed["message"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return msg

    messages = [_get_log_message(r) for r in caplog.records]
    assert "IN:test::sample_method entry" in messages
    assert "OUT:test::sample_method exit" in messages


def test_validation_rejects_unknown_content_blocks():
    payload = {
        "model": "model",
        "messages": [{"role": "user", "content": [{"type": "image", "source": {}}]}],
        "max_tokens": 16,
    }

    with pytest.raises(RequestValidationError, match="Unsupported content block type"):
        validate_anthropic_request(payload)


def test_stream_assembler_preserves_lifecycle_and_fragmented_tool_arguments():
    assembler = AnthropicStreamAssembler()

    def chunk(delta, finish_reason=None):
        choice = {"delta": delta}
        if finish_reason is not None:
            choice["finish_reason"] = finish_reason
        return {"id": "m1", "model": "model", "choices": [choice]}

    chunks = [
        chunk({"content": "Hello"}),
        chunk({"content": " world"}),
        chunk({"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "read", "arguments": "{"}}]}),
        chunk({"tool_calls": [{"index": 0, "function": {"arguments": '"path":"a"}'}}]}),
        chunk({}, "tool_calls"),
    ]

    events = [event for chunk in chunks for event in assembler.consume(chunk)]
    event_types = [event["type"] for event in events]

    assert event_types.count("message_start") == 1
    assert event_types.count("content_block_start") == 2
    assert [event["index"] for event in events if event["type"] == "content_block_delta"] == [0, 0, 1, 1]
    assert event_types[-4:] == ["content_block_stop", "content_block_stop", "message_delta", "message_stop"]
    assert json.loads('{"path":"a"}') == {"path": "a"}


def test_rate_limit_store_is_bounded_and_enforces_limit():
    async def scenario():
        store = InMemoryRateLimitStore(max_clients=1)
        assert await store.allow("one", 1, 60)
        assert not await store.allow("one", 1, 60)
        assert await store.allow("two", 1, 60)

    asyncio.run(scenario())