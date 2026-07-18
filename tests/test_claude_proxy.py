import importlib.machinery
import importlib.util
import io
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


def test_anthropic_server_web_search_maps_to_native_responses_tool():
    proxy = load_proxy()
    request = proxy.messages_to_responses(
        {
            "model": "gpt-test",
            "messages": [{"role": "user", "content": "Search the web"}],
            "tools": [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 8,
                    "allowed_domains": ["example.com"],
                }
            ],
            "tool_choice": {"type": "tool", "name": "web_search"},
        }
    )

    assert request["tools"] == [
        {"type": "web_search", "filters": {"allowed_domains": ["example.com"]}}
    ]
    assert request["tool_choice"] == {"type": "web_search"}


def test_native_web_search_output_becomes_claude_server_tool_result():
    proxy = load_proxy()
    message = proxy.responses_to_message(
        {
            "id": "response-search",
            "model": "gpt-test",
            "output": [
                {
                    "type": "web_search_call",
                    "id": "ws-1",
                    "status": "completed",
                    "action": {
                        "type": "search",
                        "queries": ["current news"],
                        "sources": [{"type": "url", "url": "https://example.com/news"}],
                    },
                },
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "A current result.",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "title": "Example News",
                                    "url": "https://example.com/news",
                                },
                                {
                                    "type": "url_citation",
                                    "title": "Second Source",
                                    "url": "https://example.org/story",
                                },
                            ],
                        }
                    ],
                },
            ],
            "usage": {"input_tokens": 11, "output_tokens": 9},
        }
    )

    assert message["content"][0] == {
        "type": "server_tool_use",
        "id": "ws-1",
        "name": "web_search",
        "input": {"query": "current news"},
    }
    assert message["content"][1] == {
        "type": "web_search_tool_result",
        "tool_use_id": "ws-1",
        "content": [
            {
                "type": "web_search_result",
                "title": "Example News",
                "url": "https://example.com/news",
            },
            {
                "type": "web_search_result",
                "title": "Second Source",
                "url": "https://example.org/story",
            },
        ],
    }
    assert message["content"][2] == {"type": "text", "text": "A current result."}
    assert message["stop_reason"] == "end_turn"
    assert message["usage"]["server_tool_use"] == {"web_search_requests": 1}


def test_streaming_web_search_result_is_emitted_as_complete_start_block():
    proxy = load_proxy()

    class RecordingHandler(proxy.Handler):
        def __init__(self):
            self.events = []
            self.wfile = io.BytesIO()

        def send_response(self, status):
            assert status == 200

        def send_header(self, name, value):
            pass

        def end_headers(self):
            pass

        def sse(self, event, payload):
            self.events.append((event, payload))

    handler = RecordingHandler()
    handler._stream_message(
        {
            "id": "response-search",
            "type": "message",
            "role": "assistant",
            "model": "gpt-test",
            "content": [
                {
                    "type": "server_tool_use",
                    "id": "ws-1",
                    "name": "web_search",
                    "input": {"query": "current news"},
                },
                {
                    "type": "web_search_tool_result",
                    "tool_use_id": "ws-1",
                    "content": [
                        {
                            "type": "web_search_result",
                            "title": "Example",
                            "url": "https://example.com/news",
                        }
                    ],
                },
            ],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 3,
                "output_tokens": 5,
                "server_tool_use": {"web_search_requests": 1},
            },
        }
    )

    starts = [payload for event, payload in handler.events if event == "content_block_start"]
    deltas = [payload for event, payload in handler.events if event == "content_block_delta"]
    message_delta = next(payload for event, payload in handler.events if event == "message_delta")
    assert starts[1]["content_block"]["type"] == "web_search_tool_result"
    assert not any(payload["index"] == 1 for payload in deltas)
    assert message_delta["usage"]["server_tool_use"] == {"web_search_requests": 1}


def test_read_tool_drops_empty_optional_pages_argument():
    proxy = load_proxy()
    message = proxy.responses_to_message(
        {
            "output": [
                {
                    "type": "function_call",
                    "call_id": "read-1",
                    "name": "Read",
                    "arguments": json.dumps(
                        {
                            "file_path": "/tmp/example.png",
                            "offset": 0,
                            "limit": 2000,
                            "pages": "",
                        }
                    ),
                }
            ]
        }
    )

    assert message["content"][0]["input"] == {
        "file_path": "/tmp/example.png",
        "offset": 0,
        "limit": 2000,
    }


def test_images_inside_tool_result_are_preserved_for_responses_vision():
    proxy = load_proxy()
    request = proxy.messages_to_responses(
        {
            "model": "gpt-test",
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "read-image-1",
                            "name": "Read",
                            "input": {"file_path": "/tmp/example.png"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "read-image-1",
                            "content": [
                                {"type": "text", "text": "image follows"},
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": "aW1hZ2U=",
                                    },
                                },
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": "cGhvdG8=",
                                    },
                                },
                            ],
                        }
                    ],
                },
            ],
        }
    )

    assert request["input"][1] == {
        "type": "function_call_output",
        "call_id": "read-image-1",
        "output": [
            {"type": "input_text", "text": "image follows"},
            {
                "type": "input_image",
                "image_url": "data:image/png;base64,aW1hZ2U=",
                "detail": "high",
            },
            {
                "type": "input_image",
                "image_url": "data:image/jpeg;base64,cGhvdG8=",
                "detail": "high",
            },
        ],
    }


def test_mixed_content_order_and_long_identifiers_are_preserved_safely():
    proxy = load_proxy()
    long_name = "mcp__server__" + "tool_" * 20
    long_id = "toolu_" + "x" * 100
    body = {
        "model": "gpt-test",
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "before"},
                    {
                        "type": "tool_use",
                        "id": long_id,
                        "name": long_name,
                        "input": {"value": 1},
                    },
                    {"type": "text", "text": "after"},
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": long_id,
                        "content": "done",
                    }
                ],
            },
        ],
        "tools": [{"name": long_name, "input_schema": {"type": "object"}}],
        "tool_choice": {
            "type": "tool",
            "name": long_name,
            "disable_parallel_tool_use": True,
        },
    }

    request = proxy.messages_to_responses(body)
    call = request["input"][1]
    result = request["input"][3]
    assert request["input"][0]["content"][0]["text"] == "before"
    assert request["input"][2]["content"][0]["text"] == "after"
    assert len(call["call_id"]) == 64
    assert result["call_id"] == call["call_id"]
    assert len(call["name"]) == 64
    assert request["tools"][0]["name"] == call["name"]
    assert request["tool_choice"] == {"type": "function", "name": call["name"]}
    assert request["parallel_tool_calls"] is False

    _, reverse_names = proxy._tool_name_maps(body)
    message = proxy.responses_to_message(
        {
            "output": [
                {
                    "type": "function_call",
                    "call_id": call["call_id"],
                    "name": call["name"],
                    "arguments": "{}",
                }
            ]
        },
        tool_name_map=reverse_names,
    )
    assert message["content"][0]["name"] == long_name


def test_tool_choice_variants_and_web_location_are_translated():
    proxy = load_proxy()
    base = {
        "model": "gpt-test",
        "messages": [{"role": "user", "content": "test"}],
        "tools": [
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "user_location": {
                    "type": "approximate",
                    "city": "Amsterdam",
                    "country": "NL",
                },
            },
            {"name": "Bash", "input_schema": {"type": "object"}},
        ],
    }
    for choice, expected in [
        ({"type": "auto"}, "auto"),
        ({"type": "any"}, "required"),
        ({"type": "none"}, "none"),
    ]:
        request = proxy.messages_to_responses({**base, "tool_choice": choice})
        assert request["tool_choice"] == expected
    request = proxy.messages_to_responses(base)
    assert request["tools"][0]["user_location"]["city"] == "Amsterdam"


def test_thinking_cached_usage_and_terminal_reason_are_preserved():
    proxy = load_proxy()
    request = proxy.messages_to_responses(
        {
            "model": "gpt-test",
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "private summary",
                            "signature": "encrypted-state",
                        }
                    ],
                }
            ],
        }
    )
    assert request["input"][0] == {
        "type": "reasoning",
        "encrypted_content": "encrypted-state",
        "summary": [],
    }

    message = proxy.responses_to_message(
        {
            "model": "gpt-test",
            "output": [
                {
                    "type": "reasoning",
                    "summary": [{"type": "summary_text", "text": "summary"}],
                    "encrypted_content": "new-state",
                }
            ],
            "usage": {
                "input_tokens": 12,
                "output_tokens": 4,
                "input_tokens_details": {"cached_tokens": 9},
            },
            "incomplete_details": {"reason": "max_output_tokens"},
            "stop_sequence": "END",
        }
    )
    assert message["content"][0] == {
        "type": "thinking",
        "thinking": "summary",
        "signature": "new-state",
    }
    assert message["usage"]["cache_read_input_tokens"] == 9
    assert message["stop_reason"] == "max_tokens"
    assert message["stop_sequence"] == "END"


def test_responses_sse_is_translated_incrementally_to_claude_stream():
    proxy = load_proxy()

    class RecordingHandler(proxy.Handler):
        def __init__(self):
            self.events = []
            self.wfile = io.BytesIO()
            self.close_connection = False

        def send_response(self, status):
            assert status == 200

        def send_header(self, name, value):
            pass

        def end_headers(self):
            pass

        def sse(self, event, payload):
            self.events.append((event, payload))

    response_events = [
        {
            "type": "response.created",
            "response": {"id": "resp-stream", "model": "gpt-test"},
        },
        {"type": "response.reasoning_summary_text.delta", "delta": "reason"},
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {
                "type": "reasoning",
                "encrypted_content": "signature",
            },
        },
        {"type": "response.output_text.delta", "delta": "hello"},
        {
            "type": "response.output_item.added",
            "output_index": 2,
            "item": {
                "type": "function_call",
                "call_id": "call-1",
                "name": "short-name",
            },
        },
        {
            "type": "response.function_call_arguments.delta",
            "output_index": 2,
            "delta": '{"cmd":"true"}',
        },
        {
            "type": "response.output_item.done",
            "output_index": 2,
            "item": {
                "type": "function_call",
                "call_id": "call-1",
                "name": "short-name",
            },
        },
        {
            "type": "response.output_item.done",
            "output_index": 3,
            "item": {
                "type": "web_search_call",
                "id": "ws-stream",
                "action": {
                    "query": "official docs",
                    "sources": [
                        {"url": "https://example.com/docs", "title": "Docs"}
                    ],
                },
            },
        },
        {
            "type": "response.completed",
            "response": {
                "id": "resp-stream",
                "model": "gpt-test",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 6,
                    "input_tokens_details": {"cached_tokens": 4},
                },
            },
        },
    ]
    upstream = iter(
        [f"data: {json.dumps(event)}\n".encode() for event in response_events]
        + [b"data: [DONE]\n"]
    )
    handler = RecordingHandler()
    handler._stream_responses(
        upstream,
        {"model": "gpt-test"},
        {"short-name": "mcp__server__original-name"},
    )

    starts = [payload for event, payload in handler.events if event == "content_block_start"]
    deltas = [payload for event, payload in handler.events if event == "content_block_delta"]
    terminal = next(payload for event, payload in handler.events if event == "message_delta")
    assert [payload["content_block"]["type"] for payload in starts] == [
        "thinking",
        "text",
        "tool_use",
        "server_tool_use",
        "web_search_tool_result",
    ]
    assert any(payload["delta"] == {"type": "thinking_delta", "thinking": "reason"} for payload in deltas)
    assert any(payload["delta"] == {"type": "signature_delta", "signature": "signature"} for payload in deltas)
    assert any(payload["delta"] == {"type": "text_delta", "text": "hello"} for payload in deltas)
    assert starts[2]["content_block"]["name"] == "mcp__server__original-name"
    assert terminal["delta"]["stop_reason"] == "tool_use"
    assert terminal["usage"] == {
        "output_tokens": 6,
        "cache_read_input_tokens": 4,
        "server_tool_use": {"web_search_requests": 1},
    }
    assert handler.close_connection is True
