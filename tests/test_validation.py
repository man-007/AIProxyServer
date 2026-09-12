import pytest

from proxy_gateway.validation import RequestValidationError, validate_anthropic_request, validate_proxy_auth


def test_validate_anthropic_request_rejects_missing_model():
    with pytest.raises(RequestValidationError, match="model"):
        validate_anthropic_request({"messages": [{"role": "user", "content": "hi"}], "max_tokens": 64})


def test_validate_anthropic_request_accepts_tool_result_message():
    request = {
        "model": "claude-3-5-sonnet",
        "messages": [
            {"role": "user", "content": "Read the file."},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tool_1", "content": "42"}]},
        ],
        "max_tokens": 128,
    }

    validated = validate_anthropic_request(request)
    assert validated["messages"][1]["content"][0]["tool_use_id"] == "tool_1"


def test_validate_anthropic_request_accepts_thinking_block():
    request = {
        "model": "model",
        "messages": [{"role": "assistant", "content": [{"type": "thinking", "thinking": "reasoning"}]}],
        "max_tokens": 16,
    }

    validate_anthropic_request(request)


def test_validate_proxy_auth_rejects_missing_token():
    with pytest.raises(RequestValidationError, match="Invalid proxy authorization token"):
        validate_proxy_auth({"Authorization": "Bearer wrong"}, "expected-token")
