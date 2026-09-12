# Copyright (c) 2026 Manas Taunk
# SPDX-License-Identifier: BSL-1.0
from typing import Any, Optional
from proxy_gateway.assembler.stream_assembler import StreamAssembler

"""
AnthropicStreamAssembler builds Anthropic-compatible streaming events.

Contributor: @man-007
"""
class AnthropicStreamAssembler(StreamAssembler):
    """Translate OpenAI-compatible streaming chunks to Anthropic events."""

    def __init__(self) -> None:
        """Initialize lifecycle, content-block, tool-call, and usage state."""
        self.started = False
        self.finished = False
        self.message_id = "msg_stream"
        self.model = "unknown"
        self._next_block_index = 0
        self._open_blocks: dict[int, str] = {}
        self._tool_blocks: dict[int, int] = {}
        self._usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def _record_usage(self, usage: Any) -> None:
        """Store the latest upstream token counts for the final event."""
        if not isinstance(usage, dict):
            return
        self._usage["input_tokens"] = usage.get("prompt_tokens", self._usage["input_tokens"])
        self._usage["output_tokens"] = usage.get("completion_tokens", self._usage["output_tokens"])
        self._usage["total_tokens"] = usage.get("total_tokens", self._usage["total_tokens"])

    def _anthropic_usage(self) -> dict[str, int]:
        """Return usage values using Anthropic response field names."""
        return {
            "input_tokens": int(self._usage["input_tokens"] or 0),
            "output_tokens": int(self._usage["output_tokens"] or 0),
        }

    def _start_message(self, chunk: dict[str, Any]) -> dict[str, Any]:
        """Create the initial Anthropic message event from an upstream chunk."""
        self.started = True
        self.message_id = chunk.get("id", self.message_id)
        self.model = chunk.get("model", self.model)
        return {
            "type": "message_start",
            "message": {
                "id": self.message_id,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": self.model,
            },
        }

    def _open_block(self, index: int, block: dict[str, Any], block_type: str) -> dict[str, Any]:
        """Register a content block and create its start event."""
        self._open_blocks[index] = block_type
        return {"type": "content_block_start", "index": index, "content_block": block}

    def _close_blocks(self) -> list[dict[str, Any]]:
        """Close all active content blocks in stable index order."""
        events = [{"type": "content_block_stop", "index": index} for index in sorted(self._open_blocks)]
        self._open_blocks.clear()
        return events

    def consume(self, chunk: dict[str, Any]) -> list[dict[str, Any]]:
        """Translate one upstream chunk into message, content, and finish events."""
        if self.finished:
            return []

        events: list[dict[str, Any]] = []
        self._record_usage(chunk.get("usage"))
        if not self.started:
            events.append(self._start_message(chunk))

        choice = (chunk.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}
        reasoning = delta.get("reasoning_content")
        if reasoning:
            reasoning_index = next((index for index, block_type in self._open_blocks.items() if block_type == "thinking"), None)
            if reasoning_index is None:
                reasoning_index = self._next_block_index
                self._next_block_index += 1
                events.append(self._open_block(reasoning_index, {"type": "thinking", "thinking": ""}, "thinking"))
            events.append({"type": "content_block_delta", "index": reasoning_index, "delta": {"type": "thinking_delta", "thinking": reasoning}})

        content = delta.get("content")
        if content:
            text_index = next((index for index, block_type in self._open_blocks.items() if block_type == "text"), None)
            if text_index is None:
                text_index = self._next_block_index
                self._next_block_index += 1
                events.append(self._open_block(text_index, {"type": "text", "text": ""}, "text"))
            events.append({"type": "content_block_delta", "index": text_index, "delta": {"type": "text_delta", "text": content}})

        for tool_call in delta.get("tool_calls") or []:
            tool_call_index = int(tool_call.get("index", 0))
            block_index = self._tool_blocks.get(tool_call_index)
            function = tool_call.get("function") or {}
            if block_index is None:
                block_index = self._next_block_index
                self._next_block_index += 1
                self._tool_blocks[tool_call_index] = block_index
                events.append(self._open_block(block_index, {
                    "type": "tool_use",
                    "id": tool_call.get("id") or f"tool_call_{tool_call_index}",
                    "name": function.get("name") or "unknown_tool",
                    "input": {},
                }, "tool_use"))
            arguments = function.get("arguments")
            if arguments:
                events.append({"type": "content_block_delta", "index": block_index, "delta": {"type": "input_json_delta", "partial_json": arguments}})

        finish_reason = choice.get("finish_reason")
        if finish_reason:
            events.extend(self._close_blocks())
            events.append({"type": "message_delta", "delta": {"stop_reason": self._map_finish_reason(finish_reason)}, "usage": self._anthropic_usage()})
            events.append({"type": "message_stop", "message": {"id": self.message_id}})
            self.finished = True
        return events

    def finish(self, reason: str = "stop") -> list[dict[str, Any]]:
        """Close an incomplete stream and emit its final lifecycle events."""
        if self.finished:
            return []
        self.finished = True
        return self._close_blocks() + [
            {"type": "message_delta", "delta": {"stop_reason": self._map_finish_reason(reason)}, "usage": self._anthropic_usage()},
            {"type": "message_stop", "message": {"id": self.message_id}},
        ]

    @staticmethod
    def _map_finish_reason(reason: Optional[str]) -> str:
        """Map upstream finish reasons to Anthropic stop reasons."""
        return {
            "tool_calls": "tool_use",
            "stop": "end_turn",
            "length": "max_tokens",
            "max_tokens": "max_tokens",
            "content_filter": "filtered",
            "filtered": "filtered",
        }.get(reason, reason or "end_turn")
