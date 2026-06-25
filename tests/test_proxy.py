"""Tests for the proxy ThinkFilter and response conversion logic."""
import importlib.machinery
import importlib.util
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
