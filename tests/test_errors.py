from proxy_gateway.diagnostics import normalize_error


def test_normalize_error_for_upstream_401():
    payload = {"error": {"message": "Invalid API key", "type": "invalid_request_error"}}
    result = normalize_error(401, payload)

    assert result["type"] == "error"
    assert result["error"]["type"] == "authentication_error"
    assert "Invalid API key" in result["error"]["message"]


def test_normalize_error_for_missing_model():
    result = normalize_error(404, {"error": {"message": "Model not available"}})

    assert result["error"]["type"] == "not_found_error"
    assert "Model not available" in result["error"]["message"]


def test_normalize_error_handles_plain_string():
    result = normalize_error(500, "Upstream unavailable")

    assert result["error"]["type"] == "api_error"
    assert "Upstream unavailable" in result["error"]["message"]
