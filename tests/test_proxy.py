"""Tests for the proxy ThinkFilter and response conversion logic."""
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"

# The proxy has no .py extension and contains dashes in its filename,
# so a plain import is impossible. Use an explicit loader.
_loader = importlib.machinery.SourceFileLoader(
    "codex_opencode_go_proxy", str(BIN_DIR / "codex-opencode-go-proxy")
)
_spec = importlib.util.spec_from_file_location(
    "codex_opencode_go_proxy", BIN_DIR / "codex-opencode-go-proxy", loader=_loader
)
proxy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(proxy)


class TestThinkFilter:
    def _filter(self, chunks):
        tf = proxy.ThinkFilter()
        output = []
        for chunk in chunks:
            result = tf.feed(chunk)
            if result:
                output.append(result)
        final = tf.finish()
        if final:
            output.append(final)
        return "".join(output)

    def test_plain_text(self):
        assert self._filter(["Hello world"]) == "Hello world"

    def test_think_block_removed(self):
        text = "Before <think>secret thinking</think> After"
        assert self._filter([text]) == "Before  After"

    def test_think_split_across_chunks(self):
        chunks = ["Hello <thi", "nk>secret</think> world"]
        assert self._filter(chunks) == "Hello  world"

    def test_think_open_at_boundary(self):
        """The <think> tag (7 chars) split exactly at boundary."""
        chunks = ["Hello <think", ">hidden</think> visible"]
        assert self._filter(chunks) == "Hello  visible"

    def test_think_close_split(self):
        """The </think> tag (8 chars) split across chunks."""
        chunks = ["Hello <think>secret</thi", "nk> visible"]
        assert self._filter(chunks) == "Hello  visible"

    def test_multiple_think_blocks(self):
        text = "A<think>1</think>B<think>2</think>C"
        assert self._filter([text]) == "ABC"

    def test_unclosed_think(self):
        """Unclosed think block should produce no output after the tag."""
        result = self._filter(["Hello <think>still thinking..."])
        assert result == "Hello "

    def test_empty_input(self):
        assert self._filter([]) == ""

    def test_only_think(self):
        assert self._filter(["<think>all thinking</think>"]) == ""

    def test_nested_lookalike(self):
        """<think> inside think should not cause issues."""
        result = self._filter(["<think>outer <think> inner</think> still</think> done"])
        # After first </think>, "still" is output, then </think> is plain text
        assert "done" in result

    def test_single_char_chunks(self):
        text = "Hi <think>x</think> Bye"
        chunks = list(text)
        result = self._filter(chunks)
        assert "Hi" in result
        assert "Bye" in result
        assert "x" not in result


class TestResponsesInputToMessages:
    def test_string_input(self):
        body = {"input": "Hello"}
        msgs = proxy.responses_input_to_messages(body)
        assert msgs == [{"role": "user", "content": "Hello"}]

    def test_instructions_become_system(self):
        body = {"instructions": "Be helpful", "input": "Hi"}
        msgs = proxy.responses_input_to_messages(body)
        assert msgs[0] == {"role": "system", "content": "Be helpful"}
        assert msgs[1] == {"role": "user", "content": "Hi"}

    def test_list_input_with_roles(self):
        body = {
            "input": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": [{"type": "text", "text": "Hi there"}]},
            ]
        }
        msgs = proxy.responses_input_to_messages(body)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "Hi there"

    def test_developer_role_mapped_to_system(self):
        body = {"input": [{"role": "developer", "content": "System msg"}]}
        msgs = proxy.responses_input_to_messages(body)
        assert msgs[0]["role"] == "system"

    def test_function_call_output(self):
        body = {
            "input": [
                {"type": "function_call_output", "call_id": "call_1", "output": "result data"}
            ]
        }
        msgs = proxy.responses_input_to_messages(body)
        assert msgs[0]["role"] == "tool"
        assert msgs[0]["tool_call_id"] == "call_1"
        assert msgs[0]["content"] == "result data"

    def test_empty_input(self):
        body = {"input": ""}
        msgs = proxy.responses_input_to_messages(body)
        assert msgs == [{"role": "user", "content": ""}]

    def test_non_dict_item(self):
        body = {"input": ["plain string"]}
        msgs = proxy.responses_input_to_messages(body)
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "plain string"

    def test_image_input_is_preserved(self):
        body = {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "inspect"},
                        {
                            "type": "input_image",
                            "image_url": "data:image/png;base64,abc",
                        },
                    ],
                }
            ]
        }
        msgs = proxy.responses_input_to_messages(body)
        assert msgs[0]["content"][0] == {"type": "text", "text": "inspect"}
        assert msgs[0]["content"][1]["type"] == "image_url"


class TestResponsesToolsToChat:
    def test_function_tool(self):
        body = {
            "tools": [{
                "type": "function",
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {"type": "object", "properties": {}},
            }]
        }
        tools = proxy.responses_tools_to_chat(body)
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "get_weather"

    def test_custom_tool(self):
        body = {
            "tools": [{
                "type": "custom",
                "name": "shell",
                "description": "Run shell",
            }]
        }
        tools = proxy.responses_tools_to_chat(body)
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "shell"
        assert "input" in tools[0]["function"]["parameters"]["properties"]

    def test_empty_tools(self):
        assert proxy.responses_tools_to_chat({}) == []

    def test_strict_mode_preserved(self):
        body = {
            "tools": [{
                "type": "function",
                "name": "strict_fn",
                "parameters": {"type": "object", "properties": {}},
                "strict": True,
            }]
        }
        tools = proxy.responses_tools_to_chat(body)
        assert tools[0]["function"]["strict"] is True

    def test_custom_tool_state_is_request_local(self):
        custom_context = proxy.ToolContext()
        proxy.responses_tools_to_chat(
            {"tools": [{"type": "custom", "name": "shared"}]},
            custom_context,
        )
        normal_context = proxy.ToolContext()
        proxy.responses_tools_to_chat(
            {
                "tools": [
                    {
                        "type": "function",
                        "name": "shared",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ]
            },
            normal_context,
        )
        result = proxy.chat_tool_calls(
            {
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "shared", "arguments": "{}"},
                    }
                ]
            },
            normal_context,
        )
        assert result[0]["type"] == "function_call"

    def test_namespace_tools_are_flattened_and_reversible(self):
        context = proxy.ToolContext()
        tools = proxy.responses_tools_to_chat(
            {
                "tools": [
                    {
                        "type": "namespace",
                        "name": "agents",
                        "tools": [
                            {
                                "type": "function",
                                "name": "spawn",
                                "parameters": {"type": "object", "properties": {}},
                            }
                        ],
                    }
                ]
            },
            context,
        )
        upstream_name = tools[0]["function"]["name"]
        assert upstream_name == "agents__spawn"
        result = proxy.chat_tool_calls(
            {
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": upstream_name, "arguments": "{}"},
                    }
                ]
            },
            context,
        )
        assert result[0]["name"] == "agents.spawn"

    def test_custom_tool_uses_input_field(self):
        context = proxy.ToolContext()
        proxy.responses_tools_to_chat(
            {"tools": [{"type": "custom", "name": "apply_patch"}]},
            context,
        )
        result = proxy.chat_tool_calls(
            {
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "apply_patch",
                            "arguments": json.dumps({"input": "*** Begin Patch"}),
                        },
                    }
                ]
            },
            context,
        )
        assert result[0]["type"] == "custom_tool_call"
        assert result[0]["input"] == "*** Begin Patch"
        assert "arguments" not in result[0]

    def test_aliases_do_not_collide(self):
        context = proxy.ToolContext()
        first = context.alias("agents.spawn")
        second = context.alias("agents__spawn")
        assert first != second
        assert context.response_name(first) == "agents.spawn"
        assert context.response_name(second) == "agents__spawn"

    def test_explicit_tool_choice_uses_upstream_alias(self):
        context = proxy.ToolContext()
        proxy.responses_tools_to_chat(
            {
                "tools": [
                    {
                        "type": "function",
                        "name": "agents.spawn",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ]
            },
            context,
        )
        result = proxy.responses_tool_choice_to_chat(
            {"type": "function", "name": "agents.spawn"},
            context,
        )
        assert result == {
            "type": "function",
            "function": {"name": "agents__spawn"},
        }


class TestModelReasoning:
    def test_none_thinking_variants(self):
        meta = {"variants": {"none": {}, "thinking": {}}}
        default, levels, mapped = proxy.model_reasoning("test", meta)
        assert default == "high"
        efforts = [l["effort"] for l in levels]
        assert "none" in efforts
        assert "high" in efforts

    def test_standard_variants(self):
        meta = {"variants": {"low": {}, "medium": {}, "high": {}}}
        default, levels, mapped = proxy.model_reasoning("test", meta)
        assert default == "medium"

    def test_max_mapped_to_xhigh(self):
        meta = {"variants": {"medium": {}, "max": {}}}
        default, levels, mapped = proxy.model_reasoning("test", meta)
        efforts = [l["effort"] for l in levels]
        assert "xhigh" in efforts

    def test_no_variants(self):
        meta = {}
        default, levels, mapped = proxy.model_reasoning("test", meta)
        assert default == "medium"
        assert len(levels) == 1


class FakeUpstream:
    def __init__(self, chunks):
        self.chunks = chunks

    def __enter__(self):
        return iter(self.chunks)

    def __exit__(self, *args):
        return False


class TestHandler:
    def make_handler(self):
        handler = object.__new__(proxy.Handler)
        handler.headers = {}
        handler.path = "/v1/responses"
        handler.rfile = io.BytesIO()
        handler.wfile = io.BytesIO()
        handler.close_connection = False
        handler.send_response = lambda *args: None
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None
        return handler

    def test_malformed_json_returns_400(self):
        handler = self.make_handler()
        raw = b"{bad json"
        handler.headers = {"content-length": str(len(raw))}
        handler.rfile = io.BytesIO(raw)
        captured = {}
        handler.send_json = lambda status, payload: captured.update(
            status=status, payload=payload
        )
        handler.do_POST()
        assert captured["status"] == 400
        assert "invalid JSON" in captured["payload"]["error"]

    def test_oversized_request_returns_413(self, monkeypatch):
        handler = self.make_handler()
        monkeypatch.setattr(proxy, "MAX_REQUEST_BYTES", 4)
        handler.headers = {"content-length": "5"}
        captured = {}
        handler.send_json = lambda status, payload: captured.update(
            status=status, payload=payload
        )
        handler.do_POST()
        assert captured["status"] == 413

    def test_proxy_token_also_accepts_opencode_credential(self, monkeypatch):
        handler = self.make_handler()
        monkeypatch.setattr(proxy, "PROXY_TOKEN", "dedicated-token")
        monkeypatch.setattr(proxy, "opencode_key", lambda: "opencode-token")
        handler.headers = {"authorization": "Bearer opencode-token"}
        assert handler._check_auth()

    def test_opencode_key_reads_codexswitch_store_before_legacy(self, tmp_path, monkeypatch):
        switch_auth = tmp_path / "switch-auth.json"
        legacy_auth = tmp_path / "legacy-auth.json"
        switch_auth.write_text(json.dumps({"api_key": "switch-token"}))
        legacy_auth.write_text(json.dumps({"opencode-go": {"key": "legacy-token"}}))
        monkeypatch.setattr(proxy, "AUTH_PATH", switch_auth)
        monkeypatch.setattr(proxy, "LEGACY_AUTH_PATH", legacy_auth)

        assert proxy.opencode_key() == "switch-token"

    def test_opencode_catalog_uses_switch_cache(self, tmp_path, monkeypatch):
        cache = tmp_path / "models.json"
        cache.write_text(json.dumps({"models": {"switch-model": {"name": "Switch"}}}))
        monkeypatch.setattr(proxy, "SWITCH_MODELS_CACHE_PATH", cache)
        monkeypatch.setattr(proxy, "opencode_catalog_from_upstream", lambda base_url: {})
        monkeypatch.setattr(proxy, "opencode_catalog_from_binary", lambda: {})
        monkeypatch.setattr(proxy, "MODELS_CACHE_PATH", tmp_path / "missing.json")

        assert proxy.opencode_catalog() == {"switch-model": {"name": "Switch"}}

    def test_custom_stream_uses_custom_input_events(self, monkeypatch):
        handler = self.make_handler()
        events = []
        handler.sse = lambda event, payload: events.append((event, payload))
        patch_text = "*** Begin Patch\n*** End Patch\n"
        chunks = [
            (
                "data: "
                + json.dumps(
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_patch",
                                            "function": {
                                                "name": "apply_patch",
                                                "arguments": json.dumps(
                                                    {"input": patch_text}
                                                ),
                                            },
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                )
                + "\n"
            ).encode(),
            b"data: [DONE]\n",
        ]
        def fake_upstream(body, context=None):
            proxy.responses_tools_to_chat(body, context)
            return FakeUpstream(chunks)

        monkeypatch.setattr(proxy, "upstream_chat", fake_upstream)
        handler.handle_stream(
            {
                "model": "test",
                "stream": True,
                "tools": [{"type": "custom", "name": "apply_patch"}],
            }
        )
        names = [event for event, _ in events]
        assert "response.custom_tool_call_input.delta" in names
        assert "response.custom_tool_call_input.done" in names
        assert "response.function_call_arguments.delta" not in names
        completed = next(
            payload["response"]
            for event, payload in events
            if event == "response.completed"
        )
        assert completed["output"][0]["input"] == patch_text

    def test_web_search_is_executed_inside_proxy(self, monkeypatch):
        handler = self.make_handler()
        events = []
        handler.sse = lambda event, payload: events.append((event, payload))
        calls = []

        def fake_upstream(body, context=None):
            proxy.responses_tools_to_chat(body, context)
            calls.append(body)
            if len(calls) == 1:
                chunks = [
                    (
                        "data: "
                        + json.dumps(
                            {
                                "choices": [
                                    {
                                        "delta": {
                                            "tool_calls": [
                                                {
                                                    "index": 0,
                                                    "id": "call_search",
                                                    "function": {
                                                        "name": "web_search",
                                                        "arguments": json.dumps(
                                                            {"query": "codexswitch"}
                                                        ),
                                                    },
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        )
                        + "\n"
                    ).encode(),
                    b"data: [DONE]\n",
                ]
            else:
                assert any(
                    item.get("type") == "function_call_output"
                    and "search-result" in item.get("output", "")
                    for item in body["input"]
                )
                chunks = [
                    b'data: {"choices":[{"delta":{"content":"found it"}}]}\n',
                    b"data: [DONE]\n",
                ]
            return FakeUpstream(chunks)

        monkeypatch.setattr(proxy, "upstream_chat", fake_upstream)
        monkeypatch.setattr(
            proxy,
            "execute_internal_tool",
            lambda name, arguments: "search-result",
        )
        handler.handle_stream(
            {
                "model": "test",
                "stream": True,
                "tools": [{"type": "web_search"}],
                "input": "search for codexswitch",
            }
        )
        assert len(calls) == 2
        assert not any(
            payload.get("item", {}).get("name") == "web_search"
            for event, payload in events
            if event == "response.output_item.added"
        )
        completed = next(
            payload["response"]
            for event, payload in events
            if event == "response.completed"
        )
        assert completed["output"][0]["content"][0]["text"] == "found it"
