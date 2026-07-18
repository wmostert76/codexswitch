import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path


def load_proxy():
    path = Path(__file__).resolve().parents[1] / "bin/codex-openai-proxy"
    loader = importlib.machinery.SourceFileLoader("codex_openai_proxy_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_chatgpt_body_enforces_stream_and_removes_system_fields():
    proxy = load_proxy()
    body = proxy.prepare_upstream_body(
        {
            "stream": False,
            "store": True,
            "max_output_tokens": 123,
            "instructions": "Claude system prompt",
            "input": [
                {"type": "message", "role": "system", "content": []},
                {"type": "message", "role": "developer", "content": []},
                {"type": "message", "role": "user", "content": []},
            ],
        }
    )
    assert body["stream"] is True
    assert body["store"] is False
    assert "max_output_tokens" not in body
    assert "instructions" not in body
    assert [item["role"] for item in body["input"]] == ["user"]


def test_sse_completed_response_collects_text_and_tool_items():
    proxy = load_proxy()
    item = {
        "type": "function_call",
        "call_id": "call-1",
        "name": "Write",
        "arguments": json.dumps({"path": "RESULT.txt"}),
    }
    lines = [
        f"data: {json.dumps({'type': 'response.output_item.done', 'output_index': 0, 'item': item})}\n".encode(),
        f"data: {json.dumps({'type': 'response.completed', 'response': {'id': 'resp-1', 'output': []}})}\n".encode(),
        b"data: [DONE]\n",
    ]
    response = proxy.completed_response_from_sse(lines)
    assert response["id"] == "resp-1"
    assert response["output"] == [item]


def test_streaming_request_is_forwarded_without_buffering_or_rewriting():
    proxy = load_proxy()

    class RecordingHandler(proxy.Handler):
        def __init__(self):
            self.status = None
            self.headers = []
            self.wfile = io.BytesIO()
            self.close_connection = False

        def send_response(self, status):
            self.status = status

        def send_header(self, name, value):
            self.headers.append((name, value))

        def end_headers(self):
            pass

    lines = [b'data: {"type":"response.created"}\n', b"data: [DONE]\n"]
    handler = RecordingHandler()
    handler._forward_sse(iter(lines))

    assert handler.status == 200
    assert ("content-type", "text/event-stream") in handler.headers
    assert handler.wfile.getvalue() == b"".join(lines)
    assert handler.close_connection is True
