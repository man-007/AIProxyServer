from proxy_gateway.adapters.anthropic_adapter import AnthropicAdapter


def test_anthropic_to_openai_maps_messages_and_tools():
    payload = {
        "model": "claude-3-5-sonnet",
        "messages": [
            {"role": "user", "content": "Summarize this file."},
            {"role": "assistant", "content": [{"type": "text", "text": "I am ready."}]},
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "tool_1", "content": "42"}],
            },
        ],
        "system": "You are a helpful assistant.",
        "max_tokens": 256,
        "temperature": 0.2,
        "tools": [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            }
        ],
        "tool_choice": {"type": "tool", "name": "read_file"},
    }

    result = AnthropicAdapter.to_upstream(payload)

    assert result["model"] == "claude-3-5-sonnet"
    assert result["max_tokens"] == 256
    assert result["temperature"] == 0.2
    assert result["messages"][0]["role"] == "system"
    assert result["messages"][0]["content"] == "You are a helpful assistant."
    assert result["tools"][0]["type"] == "function"
    assert result["tools"][0]["function"]["name"] == "read_file"
    assert result["tool_choice"] == {"type": "function", "function": {"name": "read_file"}}


def test_anthropic_to_openai_maps_auto_tool_choice_to_openai_form():
    result = AnthropicAdapter.to_upstream({
        "model": "moonshotai/kimi-k3",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 32,
        "tools": [],
        "tool_choice": {"type": "auto"},
    })

    assert result["tool_choice"] == "auto"


def test_anthropic_to_openai_does_not_invent_temperature_or_reasoning_effort():
    result = AnthropicAdapter.to_upstream({
        "model": "moonshotai/kimi-k3",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 32,
    })

    assert "temperature" not in result
    assert "reasoning_effort" not in result


def test_anthropic_to_openai_maps_base64_image_and_generation_options():
    result = AnthropicAdapter.to_upstream({
        "model": "moonshotai/kimi-k3",
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": "aGVsbG8=",
                    },
                },
                {"type": "text", "text": "What is in this image?"},
            ],
        }],
        "max_tokens": 32,
        "stream": True,
        "seed": 0,
        "reasoning_effort": "max",
    })

    assert result["messages"][0]["content"] == [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGVsbG8="}},
        {"type": "text", "text": "What is in this image?"},
    ]
    assert result["seed"] == 0
    assert result["reasoning_effort"] == "max"


def test_openai_to_anthropic_maps_tool_call_response():
    payload = {
        "id": "msg_123",
        "model": "meta/llama-3.1-70b-instruct",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "I looked it up.",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "read_file", "arguments": '{"path":"/tmp/test.txt"}'},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
    }

    result = AnthropicAdapter.from_upstream(payload)

    assert result["id"] == "msg_123"
    assert result["role"] == "assistant"
    assert result["content"][0]["type"] == "text"
    assert result["content"][1]["type"] == "tool_use"
    assert result["content"][1]["name"] == "read_file"
    assert result["stop_reason"] == "tool_calls"
    assert result["usage"]["input_tokens"] == 12
    assert result["usage"]["output_tokens"] == 6


def test_openai_to_anthropic_preserves_reasoning_content_as_thinking():
    result = AnthropicAdapter.from_upstream({
        "id": "msg_reasoning",
        "model": "moonshotai/kimi-k3",
        "choices": [{
            "message": {"role": "assistant", "content": None, "reasoning_content": "Thinking"},
            "finish_reason": "stop",
        }],
    })

    assert result["content"] == [{"type": "thinking", "thinking": "Thinking"}]
