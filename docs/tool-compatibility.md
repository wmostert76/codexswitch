# Tool Compatibility — OpenCode Go Proxy

Test results for all Codex CLI tools when using OpenCode Go models
through the compatibility proxy (`codex-opencode-go-proxy`).

**Test date:** 2026-06-25  
**Codex CLI:** 0.142.2  
**Models tested:** GLM-5.2 (xhigh), DeepSeek V4 Pro (high)

## Results

| # | Tool | API type | GLM-5.2 | DeepSeek | Notes |
|---|------|----------|:-------:|:--------:|-------|
| 1 | `exec_command` | function | ✅ | ✅ | Shell commands |
| 2 | `write_stdin` | function | ✅ | ✅ | Send input to running sessions |
| 3 | `apply_patch` | custom | ❌ | ❌ | "incompatible payload" — see below |
| 4 | `update_plan` | function | ✅ | ✅ | Create/update task plans |
| 5 | `get_goal` | function | ✅ | ✅ | Retrieve active goal |
| 6 | `create_goal` | function | ✅ | ✅ | Create a new goal |
| 7 | `update_goal` | function | ✅ | ✅ | Mark goal complete/blocked |
| 8 | `list_mcp_resources` | function | ✅ | ✅ | List MCP server resources |
| 9 | `list_mcp_resource_templates` | function | ✅ | ✅ | List parameterised MCP resources |
| 10 | `read_mcp_resource` | function | ✅ | ✅ | Read a specific MCP resource |
| 11 | `request_user_input` | function | ✅ | ✅ | Ask the user a question |
| 12 | `list_available_plugins_to_install` | function | ✅ | ✅ | List installable plugins |
| 13 | `request_plugin_install` | function | ✅ | ✅ | Request plugin installation |
| 14 | `view_image` | function | ❌ | ❌ | Blocked by Codex for non-OpenAI providers |
| 15 | `web_search` | web_search | ❌ | ❌ | Not available in this Codex config |
| 16 | `multi_agent_v1` | namespace | — | — | Subagent namespace, not separately tested |
| 17 | `mcp__node_repl` | namespace | — | — | MCP server namespace, not separately tested |

## Legend

- ✅ Works correctly through the proxy
- ❌ Does not work
- — Not separately tested (shares the same code path as a passing tool)

## Known issues

### `apply_patch` (custom tool type)

The proxy correctly converts custom tool calls between the Responses API
format (`custom_tool_call` with a plain-string `input` field) and the
upstream Chat Completions format (`function` with JSON-encoded
`{"input": "..."}` arguments).  The wrapping and unwrapping has been
verified in both directions.

Despite this, Codex CLI rejects `apply_patch` payloads with
"Fatal error: tool apply_patch invoked with incompatible payload"
when using OpenCode Go models.  The proxy delivers a well-formed
freeform patch (`*** Begin Patch … *** End Patch`), but Codex's own
tool router refuses it before the patch is applied.

This appears to be a Codex-side issue with how it validates custom
tool-call responses from non-OpenAI providers.  Further investigation
is needed — see `AGENTS.md` (Known Issues).

**Workaround:** `exec_command` with `sed`, `cat`, or a Python one-liner
achieves the same result.

### `view_image`

Codex CLI blocks image input for non-OpenAI providers with the error
"view_image is not allowed because you do not support image inputs".
This is a Codex-side restriction, not a proxy issue.

### `web_search`

The `web_search` tool is not available in the current Codex configuration.
The model reports "no web_search tool available".  This is a Codex
configuration issue, not a proxy issue.

## Proxy conversion summary

| Direction | What the proxy does |
|-----------|---------------------|
| Request → upstream | Converts `input` array → `messages`; wraps custom tool `input` as `{"input": "..."}` JSON; adds `Authorization: Bearer` header; maps reasoning effort to upstream params |
| Upstream → response | Converts chat `choices[].delta` → Responses SSE events; unwraps `{"input": "..."}` back to plain string for custom tools; uses `custom_tool_call` type for custom tools; filters `<think>` tags via `ThinkFilter` |
