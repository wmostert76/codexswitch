import importlib.machinery
import importlib.util
import json
from pathlib import Path


def load_proxy():
    path = Path(__file__).resolve().parents[1] / "bin/codex-claude-proxy"
    loader = importlib.machinery.SourceFileLoader("codex_claude_proxy_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_messages_request_converts_text_tools_and_results():
    proxy = load_proxy()
    request = proxy.messages_to_responses(
        {
            "model": "vendor/model",
            "system": [{"type": "text", "text": "Be precise"}],
            "max_tokens": 123,
            "messages": [
                {"role": "user", "content": "inspect"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "read_file",
                            "input": {"path": "README.md"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "tool-1", "content": "ok"}
                    ],
                },
            ],
            "tools": [
                {
                    "name": "read_file",
                    "description": "read",
                    "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
                }
            ],
        }
    )
    assert request["instructions"] == "Be precise"
    assert request["max_output_tokens"] == 123
    assert request["input"][1] == {
        "type": "function_call",
        "call_id": "tool-1",
        "name": "read_file",
        "arguments": '{"path":"README.md"}',
    }
    assert request["input"][2]["type"] == "function_call_output"
    assert request["tools"][0]["parameters"]["properties"]["path"]["type"] == "string"


def test_responses_output_converts_text_and_tool_use():
    proxy = load_proxy()
    message = proxy.responses_to_message(
        {
            "id": "response-1",
            "model": "model-x",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "calling"}]},
                {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "shell",
                    "arguments": json.dumps({"cmd": "true"}),
                },
            ],
            "usage": {"input_tokens": 7, "output_tokens": 3},
        }
    )
    assert message["content"][0] == {"type": "text", "text": "calling"}
    assert message["content"][1]["input"] == {"cmd": "true"}
    assert message["stop_reason"] == "tool_use"
    assert message["usage"] == {"input_tokens": 7, "output_tokens": 3}
