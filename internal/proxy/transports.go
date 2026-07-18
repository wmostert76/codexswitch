package proxy

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
)

func (s *server) handleResponsesProvider(w http.ResponseWriter, r *http.Request, provider string) {
	subpath := providerSubpath(r.URL.Path, provider)
	if provider == "azure" && r.Method == http.MethodGet && (subpath == "/models" || subpath == "/v1/models") {
		writeJSON(w, http.StatusOK, map[string]any{"models": azureModels()})
		return
	}
	if (provider == "opencode-go" || provider == "openrouter") && r.Method == http.MethodGet && (subpath == "/models" || subpath == "/v1/models") {
		s.handleModels(w, provider)
		return
	}
	if r.Method != http.MethodPost || (subpath != "/responses" && subpath != "/v1/responses") {
		writeJSON(w, http.StatusNotFound, map[string]any{"error": "not found: " + subpath})
		return
	}
	body, ok := decodeObject(w, r)
	if !ok {
		return
	}
	switch provider {
	case "openai":
		s.handleOpenAI(w, r, body)
	case "azure":
		s.handleAzure(w, r, body)
	case "opencode-go", "openrouter":
		s.handleChatProvider(w, r, provider, body)
	}
}

func (s *server) request(method, target string, body any, headers map[string]string) (*http.Response, error) {
	var reader io.Reader
	if body != nil {
		raw, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		reader = bytes.NewReader(raw)
	}
	request, err := http.NewRequest(method, target, reader)
	if err != nil {
		return nil, err
	}
	request.Header.Set("Content-Type", "application/json")
	for key, value := range headers {
		if value != "" {
			request.Header.Set(key, value)
		}
	}
	return s.client.Do(request)
}

func (s *server) handleAzure(w http.ResponseWriter, _ *http.Request, body map[string]any) {
	endpoint, key, err := s.config.azureCredentials()
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]any{"error": err.Error()})
		return
	}
	response, err := s.request(http.MethodPost, endpoint+"/responses", body, map[string]string{
		"api-key": key,
		"Accept":  acceptFor(body),
	})
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"error": "Azure upstream request failed: " + err.Error()})
		return
	}
	copyResponse(w, response)
}

func (s *server) handleOpenAI(w http.ResponseWriter, _ *http.Request, body map[string]any) {
	token, account, err := s.config.openAIAccount()
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]any{"error": err.Error()})
		return
	}
	downstreamStream, _ := body["stream"].(bool)
	prepared := cloneMap(body)
	prepared["stream"] = true
	prepared["store"] = false
	delete(prepared, "max_output_tokens")
	delete(prepared, "instructions")
	prepared["input"] = withoutSystemInput(prepared["input"])
	openAIUpstream := envOr("CODEXSWITCH_OPENAI_UPSTREAM", "https://chatgpt.com/backend-api/codex/responses")
	response, err := s.request(http.MethodPost, openAIUpstream, prepared, map[string]string{
		"Authorization":      "Bearer " + token,
		"Accept":             "text/event-stream",
		"Originator":         "codex_cli_rs",
		"chatgpt-account-id": account,
	})
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"error": "OpenAI OAuth request failed: " + err.Error()})
		return
	}
	if response.StatusCode >= 400 {
		copyResponse(w, response)
		return
	}
	s.log.Printf("openai downstream_stream=%t upstream_status=%d content_type=%q", downstreamStream, response.StatusCode, response.Header.Get("Content-Type"))
	if downstreamStream {
		response.Header.Set("Content-Type", "text/event-stream")
		copyResponse(w, response)
		return
	}
	defer response.Body.Close()
	completed, err := collectCompletedResponse(response.Body)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, completed)
}

func collectCompletedResponse(body io.Reader) (map[string]any, error) {
	var completed map[string]any
	items := map[int]any{}
	err := scanSSE(body, func(event map[string]any) error {
		typeName, _ := event["type"].(string)
		switch typeName {
		case "response.output_item.done":
			index := intNumber(event["output_index"])
			items[index] = event["item"]
		case "response.completed", "response.incomplete":
			completed, _ = event["response"].(map[string]any)
		case "error", "response.failed":
			return fmt.Errorf("OpenAI stream failed: %v", event["error"])
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	if completed == nil {
		return nil, fmt.Errorf("OpenAI stream ended without completed response")
	}
	if output, ok := completed["output"].([]any); !ok || len(output) == 0 {
		ordered := make([]any, 0, len(items))
		for index := 0; index < len(items); index++ {
			if item, exists := items[index]; exists {
				ordered = append(ordered, item)
			}
		}
		completed["output"] = ordered
	}
	return completed, nil
}

func withoutSystemInput(value any) any {
	items, ok := value.([]any)
	if !ok {
		return value
	}
	result := make([]any, 0, len(items))
	for _, item := range items {
		object, ok := item.(map[string]any)
		if ok && object["type"] == "message" && (object["role"] == "system" || object["role"] == "developer") {
			continue
		}
		result = append(result, item)
	}
	return result
}

func acceptFor(body map[string]any) string {
	if stream, _ := body["stream"].(bool); stream {
		return "text/event-stream"
	}
	return "application/json"
}

func intNumber(value any) int {
	switch number := value.(type) {
	case float64:
		return int(number)
	case json.Number:
		result, _ := number.Int64()
		return int(result)
	case int:
		return number
	default:
		return 0
	}
}

func (s *server) handleModels(w http.ResponseWriter, provider string) {
	if provider == "openrouter" {
		key, err := s.config.openRouterKey()
		if err != nil {
			writeJSON(w, http.StatusServiceUnavailable, map[string]any{"error": err.Error()})
			return
		}
		response, err := s.request(http.MethodGet, "https://openrouter.ai/api/v1/models", nil, map[string]string{"Authorization": "Bearer " + key})
		if err != nil {
			writeJSON(w, http.StatusBadGateway, map[string]any{"error": err.Error()})
			return
		}
		defer response.Body.Close()
		if response.StatusCode >= 400 {
			copyResponse(w, response)
			return
		}
		var catalog map[string]any
		if json.NewDecoder(response.Body).Decode(&catalog) != nil {
			writeJSON(w, http.StatusBadGateway, map[string]any{"error": "invalid OpenRouter model catalog"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"models": codexModelsFromOpenRouter(asSlice(catalog["data"]))})
		return
	}
	cachePath := filepath.Join(s.config.Home, ".config/codexswitch/opencode-go/models.json")
	raw, err := osReadFile(cachePath)
	if err != nil {
		writeJSON(w, http.StatusOK, map[string]any{"models": []any{}})
		return
	}
	var cached any
	if json.Unmarshal(raw, &cached) != nil {
		writeJSON(w, http.StatusOK, map[string]any{"models": []any{}})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"models": codexModelsFromCache(cached)})
}

func codexModelsFromOpenRouter(items []any) []any {
	result := make([]any, 0, len(items))
	for _, raw := range items {
		meta, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		id := text(meta["id"])
		if id == "" {
			continue
		}
		name := text(meta["name"])
		if name == "" {
			name = id
		}
		context := intNumber(meta["context_length"])
		if context == 0 {
			context = 128000
		}
		reasoningLevels := []any{map[string]any{"effort": "medium", "description": "medium reasoning"}}
		if reasoning, ok := meta["reasoning"].(map[string]any); ok {
			levels := []any{}
			for _, effort := range asSlice(reasoning["supported_efforts"]) {
				levels = append(levels, map[string]any{"effort": effort, "description": text(effort) + " reasoning"})
			}
			if len(levels) > 0 {
				reasoningLevels = levels
			}
		}
		result = append(result, codexModel(id, name, text(meta["description"]), context, "medium", reasoningLevels))
	}
	return result
}

var osReadFile = func(path string) ([]byte, error) { return os.ReadFile(path) }

func codexModelsFromCache(value any) []any {
	result := []any{}
	object, _ := value.(map[string]any)
	if models, ok := object["models"].(map[string]any); ok {
		object = models
	}
	for id, raw := range object {
		meta, _ := raw.(map[string]any)
		name, _ := meta["name"].(string)
		if name == "" {
			name = id
		}
		result = append(result, codexModel(id, name, "OpenCode Go model", 128000, "medium", []any{map[string]any{"effort": "medium", "description": "Model default reasoning"}}))
	}
	return result
}

func azureModels() []any {
	return []any{codexModel("gpt-5.6-sol", "GPT-5.6-Sol", "Azure OpenAI deployment", 272000, "medium", []any{
		map[string]any{"effort": "low", "description": "low reasoning"}, map[string]any{"effort": "medium", "description": "medium reasoning"},
		map[string]any{"effort": "high", "description": "high reasoning"}, map[string]any{"effort": "xhigh", "description": "xhigh reasoning"},
	})}
}

func codexModel(id, name, description string, context int, defaultReasoning string, reasoningLevels []any) map[string]any {
	return map[string]any{
		"slug": id, "id": id, "display_name": name, "description": description,
		"default_reasoning_level": defaultReasoning, "supported_reasoning_levels": reasoningLevels,
		"shell_type": "shell_command", "visibility": "list", "supported_in_api": true, "priority": 1,
		"additional_speed_tiers": []any{}, "service_tiers": []any{}, "availability_nux": nil, "upgrade": nil,
		"base_instructions": "", "model_messages": map[string]any{}, "supports_reasoning_summaries": true,
		"default_reasoning_summary": "none", "support_verbosity": false, "default_verbosity": "low",
		"apply_patch_tool_type": "freeform", "web_search_tool_type": "text_and_image",
		"truncation_policy": map[string]any{"mode": "tokens", "limit": 10000}, "supports_parallel_tool_calls": true,
		"supports_image_detail_original": false, "context_window": context, "max_context_window": context,
		"effective_context_window_percent": 95, "experimental_supported_tools": []any{},
		"input_modalities": []string{"text", "image"}, "use_responses_lite": false,
	}
}
