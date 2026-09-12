from proxy_gateway.adapters import AnthropicAdapter, ProtocolAdapterChain, build_protocol_adapter_chain


def test_adapter_chain_selects_anthropic_messages_endpoint():
    chain = build_protocol_adapter_chain()

    adapter = chain.resolve("POST", "/v1/messages")

    assert isinstance(adapter, AnthropicAdapter)
    assert chain.protocols == ["anthropic"]


def test_adapter_chain_rejects_unregistered_protocol_endpoint():
    chain = build_protocol_adapter_chain()

    assert chain.resolve("POST", "/v1/chat/completions") is None
    assert chain.resolve("GET", "/v1/messages") is None


def test_adapter_chain_uses_first_matching_adapter():
    class FutureAdapter(AnthropicAdapter):
        protocol_name = "future"

        def can_handle(self, method: str, path: str) -> bool:
            return method == "POST" and path == "/future"

    chain = ProtocolAdapterChain([FutureAdapter, AnthropicAdapter])

    assert isinstance(chain.resolve("POST", "/future"), FutureAdapter)
    assert isinstance(chain.resolve("POST", "/v1/messages"), AnthropicAdapter)