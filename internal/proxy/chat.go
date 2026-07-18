package proxy

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strings"
	"time"
)

type toolContext struct {
	custom   map[string]bool
	internal map[string]bool
	forward  map[string]string
	reverse  map[string]string
}

func newToolContext() *toolContext {
	return &toolContext{custom: map[string]bool{}, internal: map[string]bool{}, forward: map[string]string{}, reverse: map[string]string{}}
}

var invalidToolName = regexp.MustCompile(`[^A-Za-z0-9_-]`)

func (c *toolContext) alias(name string) string {
	if existing := c.forward[name]; existing != "" {
		return existing
	}
	alias := invalidToolName.ReplaceAllString(name, "__")
	if len(alias) > 64 {
		sum := sha256.Sum256([]byte(name))
		alias = alias[:53] + "_" + hex.EncodeToString(sum[:5])
	}
	if original := c.reverse[alias]; original != "" && original != name {
		sum := sha256.Sum256([]byte(name))
		alias = alias[:min(53, len(alias))] + "_" + hex.EncodeToString(sum[:5])
	}
	c.forward[name] = alias
	c.reverse[alias] = name
	return alias
}

func (s *server) handleChatProvider(w http.ResponseWriter, r *http.Request, provider string, body map[string]any) {
	context := newToolContext()
	payload, err := responsesToChat(body, context)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": err.Error()})
		return
	}
	key := ""
	upstream := ""
	if provider == "openrouter" {
		key, err = s.config.openRouterKey()
		upstream = envOr("CODEXSWITCH_OPENROUTER_UPSTREAM", "https://openrouter.ai/api/v1")
	} else {
		key, err = s.config.openCodeKey()
		upstream = envOr("CODEXSWITCH_OPENCODE_UPSTREAM", "https://opencode.ai/zen/go/v1")
	}
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]any{"error": err.Error()})
		return
	}
	stream, _ := body["stream"].(bool)
	if stream {
		s.handleChatProviderStream(w, r, provider, upstream+"/chat/completions", key, body, payload, context)
		return
	}
	response, err := s.chatRequest(r, upstream+"/chat/completions", key, provider, payload)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"error": err.Error()})
		return
	}
	if response.StatusCode >= 400 {
		copyResponse(w, response)
		return
	}
	defer response.Body.Close()
	var result map[string]any
	if err := json.NewDecoder(response.Body).Decode(&result); err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, chatResultToResponse(body, result, context))
}

func (s *server) chatRequest(r *http.Request, target, key, provider string, payload map[string]any) (*http.Response, error) {
	headers := map[string]string{
		"Authorization": "Bearer " + key,
		"Accept":        acceptFor(payload),
		"User-Agent":    "opencode/1.17.9",
	}
	if provider == "openrouter" {
		headers["User-Agent"] = "codexswitch-openrouter-proxy-go/1"
	}
	var last error
	for attempt := 0; attempt < 3; attempt++ {
		response, err := s.request(http.MethodPost, target, payload, headers)
		if err == nil && (response.StatusCode < 500 || attempt == 2) {
			return response, nil
		}
		if response != nil {
			response.Body.Close()
			last = fmt.Errorf("upstream HTTP %d", response.StatusCode)
		} else {
			last = err
		}
		select {
		case <-r.Context().Done():
			return nil, r.Context().Err()
		case <-time.After(time.Duration(1<<attempt) * 500 * time.Millisecond):
		}
	}
	return nil, last
}

func responsesToChat(body map[string]any, context *toolContext) (map[string]any, error) {
	payload := map[string]any{
		"model":  body["model"],
		"stream": body["stream"],
	}
	tools := responsesToolsToChat(asSlice(body["tools"]), context)
	if len(tools) > 0 {
		payload["tools"] = tools
		payload["tool_choice"] = responsesToolChoiceToChat(body["tool_choice"], context)
		if parallel, ok := body["parallel_tool_calls"].(bool); ok {
			payload["parallel_tool_calls"] = parallel
		}
	}
	messages, err := responsesInputToChat(body, context)
	if err != nil {
		return nil, err
	}
	payload["messages"] = messages
	if value := body["temperature"]; value != nil {
		payload["temperature"] = value
	}
	if value := body["max_output_tokens"]; value != nil {
		payload["max_tokens"] = value
	}
	if reasoning, ok := body["reasoning"].(map[string]any); ok {
		payload["reasoning"] = reasoning
	}
	return payload, nil
}

func responsesInputToChat(body map[string]any, context *toolContext) ([]any, error) {
	messages := []any{}
	if instructions := text(body["instructions"]); instructions != "" {
		messages = append(messages, map[string]any{"role": "system", "content": instructions})
	}
	input := body["input"]
	if value, ok := input.(string); ok {
		return append(messages, map[string]any{"role": "user", "content": value}), nil
	}
	for _, raw := range asSlice(input) {
		item, ok := raw.(map[string]any)
		if !ok {
			messages = append(messages, map[string]any{"role": "user", "content": fmt.Sprint(raw)})
			continue
		}
		switch text(item["type"]) {
		case "function_call", "custom_tool_call":
			name := text(item["name"])
			arguments := text(first(item["arguments"], item["input"]))
			if context.custom[name] && !json.Valid([]byte(arguments)) {
				raw, _ := json.Marshal(map[string]any{"input": arguments})
				arguments = string(raw)
			}
			call := map[string]any{"id": first(item["call_id"], item["id"]), "type": "function", "function": map[string]any{"name": context.alias(name), "arguments": arguments}}
			if len(messages) > 0 {
				if previous, ok := messages[len(messages)-1].(map[string]any); ok && previous["role"] == "assistant" {
					previous["tool_calls"] = append(asSlice(previous["tool_calls"]), call)
					continue
				}
			}
			messages = append(messages, map[string]any{"role": "assistant", "content": nil, "tool_calls": []any{call}})
		case "function_call_output", "custom_tool_call_output":
			messages = append(messages, map[string]any{"role": "tool", "tool_call_id": item["call_id"], "content": chatContent(item["output"])})
		case "reasoning":
			continue
		default:
			role := text(item["role"])
			if role == "" {
				role = "user"
			}
			if role == "developer" {
				role = "system"
			}
			messages = append(messages, map[string]any{"role": role, "content": chatContent(item["content"])})
		}
	}
	if len(messages) == 0 {
		messages = append(messages, map[string]any{"role": "user", "content": ""})
	}
	return messages, nil
}

func chatContent(value any) any {
	if textValue, ok := value.(string); ok {
		return textValue
	}
	parts := []any{}
	allText := true
	for _, raw := range asSlice(value) {
		item, ok := raw.(map[string]any)
		if !ok {
			parts = append(parts, map[string]any{"type": "text", "text": fmt.Sprint(raw)})
			continue
		}
		kind := text(item["type"])
		if kind == "input_image" || kind == "image" {
			allText = false
			url := item["image_url"]
			if object, ok := url.(map[string]any); ok {
				url = object["url"]
			}
			image := map[string]any{"url": fmt.Sprint(url)}
			if detail := text(item["detail"]); detail != "" {
				image["detail"] = detail
			}
			parts = append(parts, map[string]any{"type": "image_url", "image_url": image})
		} else {
			parts = append(parts, map[string]any{"type": "text", "text": text(first(item["text"], item["content"]))})
		}
	}
	if allText {
		lines := []string{}
		for _, raw := range parts {
			lines = append(lines, text(raw.(map[string]any)["text"]))
		}
		return strings.Join(lines, "\n")
	}
	return parts
}

func responsesToolsToChat(tools []any, context *toolContext) []any {
	result := []any{}
	var appendFunction func(map[string]any, string)
	appendFunction = func(tool map[string]any, name string) {
		function := map[string]any{"name": context.alias(name), "description": text(tool["description"]), "parameters": first(tool["parameters"], map[string]any{"type": "object", "properties": map[string]any{}})}
		if strict, exists := tool["strict"]; exists {
			function["strict"] = strict
		}
		result = append(result, map[string]any{"type": "function", "function": function})
	}
	for _, raw := range tools {
		tool, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		kind, name := text(tool["type"]), text(tool["name"])
		switch kind {
		case "function":
			if name != "" {
				appendFunction(tool, name)
			}
		case "custom":
			if name != "" {
				context.custom[name] = true
				appendFunction(map[string]any{"description": tool["description"], "parameters": map[string]any{"type": "object", "properties": map[string]any{"input": map[string]any{"type": "string"}}, "required": []string{"input"}, "additionalProperties": false}}, name)
			}
		case "namespace":
			for _, nestedRaw := range asSlice(tool["tools"]) {
				if nested, ok := nestedRaw.(map[string]any); ok && text(nested["type"]) == "function" {
					appendFunction(nested, name+"."+text(nested["name"]))
				}
			}
		case "web_search":
			context.internal["web_search"] = true
			appendFunction(map[string]any{"description": "Search the web for current public information and links.", "parameters": map[string]any{"type": "object", "properties": map[string]any{"query": map[string]any{"type": "string"}}, "required": []string{"query"}}}, "web_search")
		}
	}
	return result
}

func responsesToolChoiceToChat(value any, context *toolContext) any {
	if value == nil {
		return "auto"
	}
	if choice, ok := value.(string); ok {
		if choice == "required" {
			return "required"
		}
		if choice == "none" {
			return "none"
		}
		return "auto"
	}
	choice, _ := value.(map[string]any)
	if text(choice["type"]) == "function" {
		return map[string]any{"type": "function", "function": map[string]any{"name": context.alias(text(choice["name"]))}}
	}
	return "auto"
}

func chatResultToResponse(body, result map[string]any, context *toolContext) map[string]any {
	choices := asSlice(result["choices"])
	message := map[string]any{}
	if len(choices) > 0 {
		if c, ok := choices[0].(map[string]any); ok {
			message, _ = c["message"].(map[string]any)
		}
	}
	output := []any{}
	if content := text(message["content"]); content != "" {
		output = append(output, map[string]any{"type": "message", "role": "assistant", "content": []any{map[string]any{"type": "output_text", "text": content}}})
	}
	output = append(output, chatToolCalls(message, context)...)
	return map[string]any{"id": fmt.Sprintf("resp_%d", time.Now().UnixMilli()), "object": "response", "created_at": time.Now().Unix(), "status": "completed", "model": body["model"], "output": output, "usage": result["usage"]}
}

func chatToolCalls(message map[string]any, context *toolContext) []any {
	result := []any{}
	for _, raw := range asSlice(message["tool_calls"]) {
		call, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		function, _ := call["function"].(map[string]any)
		upstreamName := text(function["name"])
		name := context.reverse[upstreamName]
		if name == "" {
			name = upstreamName
		}
		arguments := text(function["arguments"])
		kind := "function_call"
		item := map[string]any{"type": kind, "call_id": call["id"], "name": name, "arguments": arguments}
		if context.custom[name] {
			item["type"] = "custom_tool_call"
			var wrapped map[string]any
			if json.Unmarshal([]byte(arguments), &wrapped) == nil {
				item["input"] = text(wrapped["input"])
				delete(item, "arguments")
			}
		}
		result = append(result, item)
	}
	return result
}

type streamedToolCall struct {
	ID, Name  string
	Arguments bytes.Buffer
}

func readChatStream(response *http.Response) (string, map[int]*streamedToolCall, error) {
	defer response.Body.Close()
	var textBuffer strings.Builder
	calls := map[int]*streamedToolCall{}
	scanner := bufio.NewScanner(response.Body)
	scanner.Buffer(make([]byte, 64<<10), 4<<20)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if !strings.HasPrefix(line, "data:") {
			continue
		}
		payload := strings.TrimSpace(strings.TrimPrefix(line, "data:"))
		if payload == "" || payload == "[DONE]" {
			continue
		}
		var chunk map[string]any
		if json.Unmarshal([]byte(payload), &chunk) != nil {
			continue
		}
		choices := asSlice(chunk["choices"])
		if len(choices) == 0 {
			continue
		}
		choice, _ := choices[0].(map[string]any)
		delta, _ := choice["delta"].(map[string]any)
		if content := text(delta["content"]); content != "" {
			textBuffer.WriteString(content)
		}
		for _, raw := range asSlice(delta["tool_calls"]) {
			part, ok := raw.(map[string]any)
			if !ok {
				continue
			}
			index := intNumber(part["index"])
			state := calls[index]
			if state == nil {
				state = &streamedToolCall{}
				calls[index] = state
			}
			if id := text(part["id"]); id != "" {
				state.ID = id
			}
			function, _ := part["function"].(map[string]any)
			state.Name += text(function["name"])
			state.Arguments.WriteString(text(function["arguments"]))
		}
	}
	return strings.TrimLeft(textBuffer.String(), "\n "), calls, scanner.Err()
}

func (s *server) handleChatProviderStream(w http.ResponseWriter, r *http.Request, provider, target, key string, body, payload map[string]any, context *toolContext) {
	requestPayload := cloneMap(payload)
	var content string
	var calls map[int]*streamedToolCall
	for round := 0; round < 5; round++ {
		response, err := s.chatRequest(r, target, key, provider, requestPayload)
		if err != nil {
			writeJSON(w, http.StatusBadGateway, map[string]any{"error": err.Error()})
			return
		}
		if response.StatusCode >= 400 {
			copyResponse(w, response)
			return
		}
		if !strings.Contains(response.Header.Get("Content-Type"), "text/event-stream") {
			copyResponse(w, response)
			return
		}
		content, calls, err = readChatStream(response)
		if err != nil {
			writeJSON(w, http.StatusBadGateway, map[string]any{"error": err.Error()})
			return
		}
		internal, external := splitChatCalls(calls, context)
		if len(internal) == 0 || len(external) > 0 {
			break
		}
		messages := asSlice(requestPayload["messages"])
		assistantCalls := []any{}
		for _, call := range internal {
			assistantCalls = append(assistantCalls, map[string]any{"id": call.ID, "type": "function", "function": map[string]any{"name": call.Name, "arguments": call.Arguments.String()}})
		}
		messages = append(messages, map[string]any{"role": "assistant", "content": nil, "tool_calls": assistantCalls})
		for _, call := range internal {
			name := context.reverse[call.Name]
			if name == "" {
				name = call.Name
			}
			messages = append(messages, map[string]any{"role": "tool", "tool_call_id": call.ID, "content": executeInternalTool(name, call.Arguments.String())})
		}
		requestPayload = cloneMap(requestPayload)
		requestPayload["messages"] = messages
		content = ""
		calls = nil
	}
	s.emitChatResponseStream(w, body, content, calls, context)
}

func splitChatCalls(calls map[int]*streamedToolCall, context *toolContext) (internal, external []*streamedToolCall) {
	for _, call := range calls {
		name := context.reverse[call.Name]
		if name == "" {
			name = call.Name
		}
		if context.internal[name] {
			internal = append(internal, call)
		} else {
			external = append(external, call)
		}
	}
	return
}

func executeInternalTool(name, arguments string) string {
	if name != "web_search" {
		return "Unsupported internal tool: " + name
	}
	var input map[string]any
	if json.Unmarshal([]byte(arguments), &input) != nil {
		return "Invalid web search arguments"
	}
	query := text(first(input["query"], input["q"]))
	if query == "" {
		return "Web search query is empty"
	}
	return webSearch(query)
}

func (s *server) emitChatResponseStream(w http.ResponseWriter, body map[string]any, content string, calls map[int]*streamedToolCall, context *toolContext) {
	stream, err := newSSEWriter(w)
	if err != nil {
		return
	}
	rid := fmt.Sprintf("resp_%d", time.Now().UnixMilli())
	base := map[string]any{"id": rid, "object": "response", "created_at": time.Now().Unix(), "status": "in_progress", "model": body["model"], "output": []any{}}
	_ = stream.Event("response.created", map[string]any{"type": "response.created", "response": base})
	output := []any{}
	if content != "" {
		index := len(output)
		itemID := "msg_0"
		message := map[string]any{"id": itemID, "type": "message", "role": "assistant", "content": []any{map[string]any{"type": "output_text", "text": content}}}
		output = append(output, message)
		_ = stream.Event("response.output_item.added", map[string]any{"type": "response.output_item.added", "output_index": index, "item": map[string]any{"id": itemID, "type": "message", "role": "assistant", "content": []any{}}})
		_ = stream.Event("response.output_text.delta", map[string]any{"type": "response.output_text.delta", "output_index": index, "content_index": 0, "delta": content})
		_ = stream.Event("response.output_item.done", map[string]any{"type": "response.output_item.done", "output_index": index, "item": message})
	}
	indices := make([]int, 0, len(calls))
	for index := range calls {
		indices = append(indices, index)
	}
	sort.Ints(indices)
	for _, index := range indices {
		state := calls[index]
		upstreamName := state.Name
		name := context.reverse[upstreamName]
		if name == "" {
			name = upstreamName
		}
		item := map[string]any{"id": "fc_" + state.ID, "type": "function_call", "call_id": state.ID, "name": name, "arguments": state.Arguments.String()}
		if context.custom[name] {
			item["type"] = "custom_tool_call"
			var wrapped map[string]any
			if json.Unmarshal(state.Arguments.Bytes(), &wrapped) == nil {
				item["input"] = text(wrapped["input"])
				delete(item, "arguments")
			}
		}
		outputIndex := len(output)
		output = append(output, item)
		_ = stream.Event("response.output_item.added", map[string]any{"type": "response.output_item.added", "output_index": outputIndex, "item": item})
		_ = stream.Event("response.output_item.done", map[string]any{"type": "response.output_item.done", "output_index": outputIndex, "item": item})
	}
	completed := cloneMap(base)
	completed["status"] = "completed"
	completed["output"] = output
	_ = stream.Event("response.completed", map[string]any{"type": "response.completed", "response": completed})
	_ = stream.Done()
}

func asSlice(value any) []any {
	if value == nil {
		return nil
	}
	if result, ok := value.([]any); ok {
		return result
	}
	return []any{value}
}
func text(value any) string {
	if value == nil {
		return ""
	}
	if result, ok := value.(string); ok {
		return result
	}
	return fmt.Sprint(value)
}
func first(values ...any) any {
	for _, value := range values {
		if value != nil {
			return value
		}
	}
	return nil
}
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

var _ io.Reader
