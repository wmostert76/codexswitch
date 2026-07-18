package proxy

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestHealthIdentifiesGoImplementation(t *testing.T) {
	s := newServer(config{Home: t.TempDir(), Address: "127.0.0.1:0"}, log.New(io.Discard, "", 0))
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/health", nil)
	s.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", recorder.Code, recorder.Body.String())
	}
	var body map[string]any
	if json.Unmarshal(recorder.Body.Bytes(), &body) != nil {
		t.Fatal("invalid JSON")
	}
	if body["implementation"] != "go" {
		t.Fatalf("implementation=%v", body["implementation"])
	}
}

func TestClaudeRequestPreservesImagesToolsChoiceAndLongIdentifiers(t *testing.T) {
	longName := "mcp__server__" + strings.Repeat("tool_", 20)
	longID := "toolu_" + strings.Repeat("x", 100)
	body := map[string]any{"model": "gpt-test", "stream": true, "messages": []any{
		map[string]any{"role": "assistant", "content": []any{map[string]any{"type": "text", "text": "before"}, map[string]any{"type": "tool_use", "id": longID, "name": longName, "input": map[string]any{"x": 1}}}},
		map[string]any{"role": "user", "content": []any{map[string]any{"type": "tool_result", "tool_use_id": longID, "content": []any{map[string]any{"type": "image", "source": map[string]any{"type": "base64", "media_type": "image/png", "data": "aW1hZ2U="}}}}}},
	}, "tools": []any{map[string]any{"name": longName, "input_schema": map[string]any{"type": "object"}}}, "tool_choice": map[string]any{"type": "tool", "name": longName, "disable_parallel_tool_use": true}}
	request, err := claudeToResponses(body)
	if err != nil {
		t.Fatal(err)
	}
	input := asSlice(request["input"])
	call := input[1].(map[string]any)
	result := input[2].(map[string]any)
	if len(text(call["call_id"])) != 64 || call["call_id"] != result["call_id"] {
		t.Fatalf("call ids differ: %v %v", call["call_id"], result["call_id"])
	}
	if len(text(call["name"])) != 64 {
		t.Fatalf("tool name len=%d", len(text(call["name"])))
	}
	if request["parallel_tool_calls"] != false {
		t.Fatalf("parallel=%v", request["parallel_tool_calls"])
	}
	output := asSlice(result["output"])
	if text(output[0].(map[string]any)["type"]) != "input_image" {
		t.Fatalf("output=%#v", output)
	}
}

func TestResponsesToClaudeRestoresThinkingUsageAndToolName(t *testing.T) {
	message := responsesToClaude(map[string]any{"id": "resp-1", "model": "gpt-test", "output": []any{
		map[string]any{"type": "reasoning", "summary": []any{map[string]any{"text": "summary"}}, "encrypted_content": "state"},
		map[string]any{"type": "function_call", "call_id": "call-1", "name": "short", "arguments": "{}"},
	}, "usage": map[string]any{"input_tokens": 12, "output_tokens": 4, "input_tokens_details": map[string]any{"cached_tokens": 9}}}, "", map[string]string{"short": "mcp__server__long"})
	content := asSlice(message["content"])
	if text(content[0].(map[string]any)["signature"]) != "state" {
		t.Fatalf("content=%#v", content)
	}
	if text(content[1].(map[string]any)["name"]) != "mcp__server__long" {
		t.Fatalf("name=%v", content[1])
	}
	usage := message["usage"].(map[string]any)
	if intNumber(usage["cache_read_input_tokens"]) != 9 {
		t.Fatalf("usage=%#v", usage)
	}
}

func TestResponsesChatTranslationFlattensNamespaceAndCustomImageOutput(t *testing.T) {
	context := newToolContext()
	body := map[string]any{"model": "router/model", "stream": false, "input": []any{map[string]any{"type": "function_call_output", "call_id": "c1", "output": []any{map[string]any{"type": "input_image", "image_url": "data:image/png;base64,abc", "detail": "high"}}}}, "tools": []any{
		map[string]any{"type": "custom", "name": "apply_patch"}, map[string]any{"type": "namespace", "name": "agents", "tools": []any{map[string]any{"type": "function", "name": "spawn", "parameters": map[string]any{"type": "object"}}}},
	}}
	payload, err := responsesToChat(body, context)
	if err != nil {
		t.Fatal(err)
	}
	tools := asSlice(payload["tools"])
	if len(tools) != 2 {
		t.Fatalf("tools=%#v", tools)
	}
	messages := asSlice(payload["messages"])
	content := asSlice(messages[0].(map[string]any)["content"])
	if text(content[0].(map[string]any)["type"]) != "image_url" {
		t.Fatalf("content=%#v", content)
	}
}

func TestCollectCompletedResponseUsesDoneItems(t *testing.T) {
	stream := "data: {\"type\":\"response.output_item.done\",\"output_index\":0,\"item\":{\"type\":\"message\"}}\n\n" +
		"data: {\"type\":\"response.completed\",\"response\":{\"id\":\"resp\",\"output\":[]}}\n\n"
	result, err := collectCompletedResponse(strings.NewReader(stream))
	if err != nil {
		t.Fatal(err)
	}
	if len(asSlice(result["output"])) != 1 {
		t.Fatalf("result=%#v", result)
	}
}

func TestOpenRouterCatalogProducesCompleteCodexMetadata(t *testing.T) {
	models := codexModelsFromOpenRouter([]any{map[string]any{"id": "vendor/model", "name": "Model", "context_length": 200000}})
	model := models[0].(map[string]any)
	for _, field := range []string{"shell_type", "visibility", "apply_patch_tool_type", "truncation_policy", "input_modalities"} {
		if _, ok := model[field]; !ok {
			t.Fatalf("missing %s: %#v", field, model)
		}
	}
}

func TestAzureClaudeEndToEndThroughUnifiedGoServer(t *testing.T) {
	var received map[string]any
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("api-key") != "fixture-secret" {
			t.Errorf("missing api-key")
		}
		_ = json.NewDecoder(r.Body).Decode(&received)
		writeJSON(w, http.StatusOK, map[string]any{
			"id": "resp-live", "model": "gpt-test",
			"output": []any{map[string]any{
				"type":    "message",
				"content": []any{map[string]any{"type": "output_text", "text": "GO_OK"}},
			}},
			"usage": map[string]any{"input_tokens": 3, "output_tokens": 2},
		})
	}))
	defer upstream.Close()
	home := t.TempDir()
	auth := filepath.Join(home, ".config/codexswitch/azure/auth.json")
	if err := os.MkdirAll(filepath.Dir(auth), 0o700); err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(map[string]any{"endpoint": upstream.URL, "api_key": "fixture-secret"})
	if err := os.WriteFile(auth, raw, 0o600); err != nil {
		t.Fatal(err)
	}
	configuration := config{Home: home}
	handler := newServer(configuration, log.New(io.Discard, "", 0))
	unified := httptest.NewServer(handler)
	defer unified.Close()
	configuration.Address = strings.TrimPrefix(unified.URL, "http://")
	handler.config = configuration
	body, _ := json.Marshal(map[string]any{"model": "gpt-test", "stream": false, "messages": []any{map[string]any{"role": "user", "content": "hello"}}})
	response, err := http.Post(unified.URL+"/claude/azure/v1/messages", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	resultRaw, _ := io.ReadAll(response.Body)
	if response.StatusCode != 200 {
		t.Fatalf("status=%d body=%s", response.StatusCode, resultRaw)
	}
	var result map[string]any
	_ = json.Unmarshal(resultRaw, &result)
	content := asSlice(result["content"])
	if text(content[0].(map[string]any)["text"]) != "GO_OK" {
		t.Fatalf("result=%s", resultRaw)
	}
	if received["model"] != "gpt-test" {
		t.Fatalf("upstream=%#v", received)
	}
}

func TestOpenAIStreamingForcesSSEContentTypeWhenUpstreamOmitsIt(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, "event: response.created\ndata: {\"type\":\"response.created\"}\n\n")
	}))
	defer upstream.Close()
	t.Setenv("CODEXSWITCH_OPENAI_UPSTREAM", upstream.URL)

	home := t.TempDir()
	auth := filepath.Join(home, ".codex/auth.json")
	if err := os.MkdirAll(filepath.Dir(auth), 0o700); err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(map[string]any{"tokens": map[string]any{"access_token": "fixture-token", "account_id": "fixture-account"}})
	if err := os.WriteFile(auth, raw, 0o600); err != nil {
		t.Fatal(err)
	}

	s := newServer(config{Home: home, Address: "127.0.0.1:0"}, log.New(io.Discard, "", 0))
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, "/openai/v1/responses", bytes.NewBufferString(`{"model":"gpt-test","stream":true,"input":"hello"}`))
	request.Header.Set("content-type", "application/json")
	s.ServeHTTP(recorder, request)
	if got := recorder.Header().Get("Content-Type"); got != "text/event-stream" {
		t.Fatalf("content-type=%q body=%s", got, recorder.Body.String())
	}
}
