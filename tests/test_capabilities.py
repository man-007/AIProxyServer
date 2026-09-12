from proxy_gateway.server import registry


def test_nemotron_super_is_configured_for_tool_calling():
    record = registry._normalize_model_record({"id": "nvidia/nemotron-3-super-120b-a12b"})

    assert record["capabilities"]["tool_calling"] is True
    assert record["capabilities"]["reasoning"] is True