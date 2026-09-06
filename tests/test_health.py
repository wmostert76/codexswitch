"""Malformed local health endpoints must not crash status or startup."""
import io
import json

import pytest
import codexswitch_backend as cs


@pytest.mark.parametrize("payload", [None, [], {"ok": False},
    {"ok": True, "implementation": [], "providers": []},
    {"ok": True, "implementation": "go", "providers": [{}]},
    {"ok": True, "implementation": "other", "providers": ["openrouter", "opencode-go"]}])
def test_invalid_health_is_unhealthy(monkeypatch, payload):
    response = io.BytesIO(json.dumps(payload).encode())
    response.status = 200
    monkeypatch.setattr(cs.urllib.request, "urlopen", lambda *args, **kwargs: response)
    assert cs.proxy_healthy() is False


def test_valid_health(monkeypatch):
    response = io.BytesIO(json.dumps({"ok": True, "implementation": "go",
                                      "providers": ["openrouter", "opencode-go"]}).encode())
    response.status = 200
    monkeypatch.setattr(cs.urllib.request, "urlopen", lambda *args, **kwargs: response)
    assert cs.proxy_healthy() is True
