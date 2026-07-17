import importlib.machinery
import importlib.util
from pathlib import Path


def load_helper():
    path = Path(__file__).resolve().parents[1] / "bin" / "codexswitch-claude-token"
    loader = importlib.machinery.SourceFileLoader("codexswitch_claude_token_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_direct_openrouter_anthropic_returns_provider_key_without_proxy(
    monkeypatch, capsys
):
    helper = load_helper()
    calls = []
    monkeypatch.setattr(
        helper,
        "read_json",
        lambda _path, _default: {
            "provider": "openrouter",
            "model": "anthropic/claude-sonnet-5",
        },
    )
    monkeypatch.setattr(
        helper, "openrouter_credentials", lambda: {"api_key": "fixture-key"}
    )
    monkeypatch.setattr(
        helper, "ensure_unified_provider_proxy", lambda: calls.append("proxy")
    )

    assert helper.main() == 0
    assert capsys.readouterr().out.strip() == "fixture-key"
    assert calls == []


def test_non_anthropic_openrouter_returns_loopback_token_and_starts_proxy(
    monkeypatch, capsys
):
    helper = load_helper()
    calls = []
    monkeypatch.setattr(
        helper,
        "read_json",
        lambda _path, _default: {
            "provider": "openrouter",
            "model": "deepseek/deepseek-v4-pro",
        },
    )
    monkeypatch.setattr(
        helper, "ensure_unified_provider_proxy", lambda: calls.append("proxy")
    )

    assert helper.main() == 0
    assert capsys.readouterr().out.strip() == helper.CLAUDE_PROXY_TOKEN
    assert calls == ["proxy"]
