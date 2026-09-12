from proxy_gateway.adapters.anthropic_adapter import AnthropicAdapter
from proxy_gateway.assembler.anthropic_stream_assembler import AnthropicStreamAssembler


def test_openai_stream_to_anthropic_events_for_text():
    chunk = {
        "id": "msg_stream_1",
        "model": "meta/llama-3.1-70b-instruct",
        "choices": [{
            "index": 0,
            "delta": {"content": "Hello"},
            "finish_reason": None,
        }],
    }

    events = AnthropicAdapter.stream_events(chunk)
    assert any(event["type"] == "message_start" for event in events)
    assert any(event["type"] == "content_block_start" and event["content_block"]["type"] == "text" for event in events)
    assert any(event["type"] == "content_block_delta" and event["delta"].get("text") == "Hello" for event in events)


def test_openai_stream_to_anthropic_events_for_tool_calls():
    chunk = {
        "id": "msg_stream_tool",
        "model": "meta/llama-3.1-70b-instruct",
        "choices": [{
            "index": 0,
            "delta": {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_1",
                        "function": {"name": "read_file", "arguments": '{"path":"/tmp/test.txt"}'},
                    }
                ]
            },
            "finish_reason": "tool_calls",
        }],
    }

    events = AnthropicAdapter.stream_events(chunk)
    assert any(event["type"] == "content_block_start" and event.get("content_block", {}).get("type") == "tool_use" for event in events)
    assert any(event["type"] == "message_delta" and event["delta"].get("stop_reason") == "tool_use" for event in events)


def test_openai_stream_to_anthropic_events_maps_finish_reasons():
    chunk = {
        "id": "msg_stream_stop",
        "model": "meta/llama-3.1-70b-instruct",
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop",
        }],
    }

    events = AnthropicAdapter.stream_events(chunk)
    assert any(event["type"] == "message_delta" and event["delta"].get("stop_reason") == "end_turn" for event in events)


def test_stream_helper_preserves_assembler_state():
    assembler = AnthropicStreamAssembler()
    first = {"id": "m1", "model": "model", "choices": [{"delta": {"content": "Hello"}}]}
    second = {"id": "m1", "model": "model", "choices": [{"delta": {}, "finish_reason": "stop"}]}

    first_events = AnthropicAdapter.stream_events(first, assembler)
    second_events = AnthropicAdapter.stream_events(second, assembler)

    assert [event["type"] for event in first_events].count("message_start") == 1
    assert not any(event["type"] == "message_start" for event in second_events)


def test_stream_usage_uses_upstream_usage():
    assembler = AnthropicStreamAssembler()
    chunk = {
        "id": "m1",
        "model": "model",
        "choices": [{"delta": {}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
    }

    events = assembler.consume(chunk)
    usage = next(event["usage"] for event in events if event["type"] == "message_delta")
    assert usage == {"input_tokens": 12, "output_tokens": 6}
