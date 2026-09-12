import json
from typing import Any, Optional
from proxy_gateway.assembler.stream_assembler import StreamAssembler
from proxy_gateway.diagnostics import get_logger

from proxy_gateway.adapters.protocol_adapter import ProtocolAdapter
from proxy_gateway.validation import validate_anthropic_request
from proxy_gateway.assembler.anthropic_stream_assembler import AnthropicStreamAssembler
from proxy_gateway.utils.request_context import RequestContext


logger = get_logger("AnthropicAdapter")

class AnthropicAdapter(ProtocolAdapter):
    """Anthropic protocol boundary for the shared upstream gateway path."""

    protocol_name = "anthropic"

    def handle(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle an incoming Anthropic request by validating and translating it."""
        logger.debug(
            "IN:AnthropicAdapter::handle handling request",
            extra={"method": method, "path": path, "payload_keys": list(payload.keys())},
        )
        validated = self.validate_request(payload)
        logger.debug("AnthropicAdapter::handle request validated", extra={"validated_keys": list(validated.keys())})
        upstream = self.to_upstream(validated)
        logger.debug("OUT:AnthropicAdapter::handle request translated to upstream", extra={"upstream_keys": list(upstream.keys())})
        return upstream

    def can_handle(self, context: RequestContext) -> bool:
        """Match the Anthropic Messages route and its JSON request headers."""
        logger.debug("AnthropicAdapter::can_handle checking request", extra={"method": context.method, "path": context.path})
        if context.method != "POST" or context.path != "/v1/messages":
            logger.debug("AnthropicAdapter::can_handle method/path mismatch")
            return False
        if not context.headers:
            logger.debug("AnthropicAdapter::can_handle no headers")
            return True
        try:
            self._validate_headers(context.headers)
        except ValueError as e:
            logger.debug("AnthropicAdapter::can_handle header validation failed: %s", e)
            return False
        logger.debug("AnthropicAdapter::can_handle request accepted")
        return True

    def _validate_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        logger.debug("IN:AnthropicAdapter::_validate_headers validating headers")

        normalisedHeaders = {key.lower(): value for key, value in (headers or {}).items()}
        safe_headers = {
            key: "[REDACTED]" if key in {"authorization", "x-api-key"} else value
            for key, value in normalisedHeaders.items()
        }
        logger.debug("AnthropicAdapter::_validate_headers normalized headers", extra={"headers": safe_headers})

        if normalisedHeaders.get("content-type", "").split(";")[0] != "application/json":
            raise ValueError("Invalid content-type header")
        if not ("anthropic-version" in normalisedHeaders or "x-api-key" in normalisedHeaders or "anthropic-beta" in normalisedHeaders):
            raise ValueError("Missing required Anthropic headers")

        logger.debug("OUT:AnthropicAdapter::_validate_headers headers accepted")
        return normalisedHeaders

    @staticmethod
    def validate_request(payload: dict[str, Any]) -> dict[str, Any]:
        """Validate the required Anthropic Messages request fields."""
        logger = get_logger("AnthropicAdapter")
        logger.debug("IN:AnthropicAdapter::validate_request validating payload", extra={"payload_keys": list(payload.keys())})
        result = validate_anthropic_request(payload)
        logger.debug("OUT:AnthropicAdapter::validate_request validation completed", extra={"result_keys": list(result.keys())})
        return result

    @staticmethod
    def to_upstream(payload: dict[str, Any]) -> dict[str, Any]:
        """Translate Anthropic messages, tools, and options to upstream fields."""
        logger = get_logger("AnthropicAdapter")
        logger.debug("IN:AnthropicAdapter::to_upstream translating payload", extra={"payload_keys": list(payload.keys())})
        result = AnthropicAdapter._to_openai(payload)
        logger.debug("OUT:AnthropicAdapter::to_upstream translation completed", extra={"result_keys": list(result.keys())})
        return result

    @staticmethod
    def from_upstream(payload: dict[str, Any]) -> dict[str, Any]:
        """Translate an upstream completion into an Anthropic message response."""
        logger = get_logger("AnthropicAdapter")
        logger.debug("IN:AnthropicAdapter::from_upstream translating payload", extra={"payload_keys": list(payload.keys())})
        result = AnthropicAdapter._from_openai(payload)
        logger.debug("OUT:AnthropicAdapter::from_upstream translation completed", extra={"result_keys": list(result.keys())})
        return result

    @staticmethod
    def stream_events(
        chunk: dict[str, Any],
        assembler: Optional[AnthropicStreamAssembler] = None,
    ) -> list[dict[str, Any]]:
        """Convert one upstream stream chunk into Anthropic stream events."""
        logger = get_logger("AnthropicAdapter")
        logger.debug("IN:AnthropicAdapter::stream_events processing stream event", extra={"chunk_keys": list(chunk.keys()) if isinstance(chunk, dict) else None})
        result = (assembler or AnthropicStreamAssembler()).consume(chunk)
        logger.debug("OUT:AnthropicAdapter::stream_events stream event processed", extra={"event_count": len(result)})
        return result

    @staticmethod
    def create_stream_assembler() -> AnthropicStreamAssembler:
        """Create the state holder required to assemble an Anthropic stream."""
        logger = get_logger("AnthropicAdapter")
        logger.debug("IN:AnthropicAdapter::create_stream_assembler creating stream assembler")
        return AnthropicStreamAssembler()

    @staticmethod
    def _to_openai(payload: dict[str, Any]) -> dict[str, Any]:
        """Build the OpenAI-compatible request body from an Anthropic payload."""
        messages: list[dict[str, Any]] = []
        system = payload.get("system")
        if isinstance(system, str) and system:
            messages.append({"role": "system", "content": system})
        elif isinstance(system, list):
            messages.append({"role": "system", "content": system})

        for message in payload.get("messages", []):
            role = message.get("role")
            content = message.get("content")
            if isinstance(content, str):
                messages.append({"role": role, "content": content})
                continue
            blocks = AnthropicAdapter._parse_content(content)
            if not blocks:
                continue
            tool_calls = [block for block in blocks if block.get("type") == "tool_use"]
            text_blocks = [block for block in blocks if block.get("type") == "text"]
            thinking_blocks = [block for block in blocks if block.get("type") == "thinking"]
            if role == "assistant" and (tool_calls or thinking_blocks):
                assistant_message: dict[str, Any] = {"role": "assistant", "content": "\n".join(block.get("text", "") for block in text_blocks)}
                if tool_calls:
                    assistant_message["tool_calls"] = [{"id": block.get("id"), "type": "function", "function": {"name": block.get("name"), "arguments": json.dumps(block.get("input", {}))}} for block in tool_calls]
                if thinking_blocks:
                    assistant_message["reasoning_content"] = "\n".join(block.get("thinking", "") for block in thinking_blocks)
                messages.append(assistant_message)
            for result in [block for block in blocks if block.get("type") == "tool_result"]:
                messages.append({"role": "tool", "tool_call_id": result.get("tool_use_id"), "content": AnthropicAdapter._tool_result_content(result.get("content", ""))})
            if role != "assistant" or not (tool_calls or thinking_blocks):
                converted = [{"type": "text", "text": block.get("text", "")} if block.get("type") == "text" else block for block in blocks if block.get("type") in {"text", "image_url"}]
                if converted:
                    messages.append({"role": role, "content": converted[0]["text"] if len(converted) == 1 and converted[0].get("type") == "text" else converted})

        tools = [{"type": "function", "function": {"name": tool.get("name"), "description": tool.get("description", ""), "parameters": tool.get("input_schema") or {"type": "object", "properties": {}}}} for tool in payload.get("tools", [])]
        result: dict[str, Any] = {"model": payload.get("model"), "messages": messages, "max_tokens": payload.get("max_tokens", 1024), "stream": payload.get("stream", False)}
        for option in ("temperature", "seed", "reasoning_effort", "top_p", "stop"):
            if option in payload:
                result[option] = payload[option]
        if result["stream"]:
            result["stream_options"] = {"include_usage": True}
        if tools:
            result["tools"] = tools
        tool_choice = payload.get("tool_choice")
        if tool_choice:
            if isinstance(tool_choice, dict) and tool_choice.get("type") == "tool":
                result["tool_choice"] = {"type": "function", "function": {"name": tool_choice.get("name")}}
            else:
                result["tool_choice"] = tool_choice.get("type") if isinstance(tool_choice, dict) else tool_choice
        return result

    @staticmethod
    def _from_openai(payload: dict[str, Any]) -> dict[str, Any]:
        """Build the Anthropic response body from an upstream completion."""
        logger = get_logger("AnthropicAdapter")
        logger.debug("IN:AnthropicAdapter::_from_openai building response", extra={"payload_keys": list(payload.keys())})
        choice = payload.get("choices", [{}])[0]
        message = choice.get("message", {})
        blocks: list[dict[str, Any]] = []
        if message.get("reasoning_content"):
            blocks.append({"type": "thinking", "thinking": message["reasoning_content"]})
        if message.get("content"):
            blocks.append({"type": "text", "text": message["content"]})
        for tool_call in message.get("tool_calls") or []:
            function = tool_call.get("function", {})
            arguments = function.get("arguments")
            try:
                parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed = {"raw": arguments}
            blocks.append({"type": "tool_use", "id": tool_call.get("id", "tool_call"), "name": function.get("name", "unknown_tool"), "input": parsed})
        usage = payload.get("usage", {})
        result = {"id": payload.get("id", "msg_generated"), "type": "message", "role": "assistant", "content": blocks, "model": payload.get("model", "unknown"), "stop_reason": choice.get("finish_reason") or "end_turn", "usage": {"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0), "total_tokens": usage.get("total_tokens", 0)}}
        logger.debug("OUT:AnthropicAdapter::_from_openai response built", extra={"result_keys": list(result.keys())})
        return result

    @staticmethod
    def _parse_content(content: Any) -> list[dict[str, Any]]:
        """Normalize Anthropic content blocks before mapping them upstream."""
        if isinstance(content, str):
            return [{"type": "text", "text": content}]
        if not isinstance(content, list):
            return []
        blocks = []
        for item in content:
            item_type = item.get("type")
            if item_type == "text":
                blocks.append({"type": "text", "text": item.get("text", "")})
            elif item_type in {"tool_result", "tool_use", "thinking"}:
                blocks.append(item)
            elif item_type == "image":
                source = item.get("source") or {}
                if source.get("type") == "base64":
                    url = f"data:{source.get('media_type')};base64,{source.get('data')}"
                elif source.get("type") == "url":
                    url = source.get("url")
                else:
                    continue
                blocks.append({"type": "image_url", "image_url": {"url": url}})
        return blocks

    @staticmethod
    def _tool_result_content(content: Any) -> str:
        """Convert a tool result's text or blocks into upstream tool content."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
            if text_parts:
                return "\n".join(text_parts)
        return json.dumps(content, ensure_ascii=True)