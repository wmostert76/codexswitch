package proxy

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const identifierLimit = 64

func shortIdentifier(value any) string {
	input := text(value)
	if len(input) <= identifierLimit {
		return input
	}
	sum := sha256.Sum256([]byte(input))
	digest := hex.EncodeToString(sum[:8])
	return input[:identifierLimit-len(digest)-1] + "_" + digest
}

func claudeToolNames(body map[string]any) (map[string]string, map[string]string) {
	forward, reverse := map[string]string{}, map[string]string{}
	for _, raw := range asSlice(body["tools"]) {
		tool, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		if strings.HasPrefix(text(tool["type"]), "web_search_") {
			continue
		}
		name := text(tool["name"])
		if name == "" {
			continue
		}
		short := shortIdentifier(name)
		forward[name] = short
		reverse[short] = name
	}
	return forward, reverse
}

func (s *server) handleClaude(w http.ResponseWriter, r *http.Request, provider string) {
	subpath := providerSubpath(r.URL.Path, provider)
	if r.Method != http.MethodPost || (subpath != "/messages" && subpath != "/v1/messages") {
		writeJSON(w, http.StatusNotFound, map[string]any{"type": "error", "error": map[string]any{"type": "not_found_error", "message": "not found"}})
		return
	}
	body, ok := decodeObject(w, r)
	if !ok {
		return
	}
	requestBody, err := claudeToResponses(body)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"type": "error", "error": map[string]any{"type": "invalid_request_error", "message": err.Error()}})
		return
	}
	target := "http://" + s.config.Address + "/" + provider + "/v1/responses"
	response, err := s.request(http.MethodPost, target, requestBody, map[string]string{"Accept": acceptFor(requestBody)})
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"type": "error", "error": map[string]any{"type": "api_error", "message": err.Error()}})
		return
	}
	if response.StatusCode >= 400 {
		copyResponse(w, response)
		return
	}
	_, reverse := claudeToolNames(body)
	stream, _ := body["stream"].(bool)
	s.log.Printf("claude provider=%s stream=%t upstream_status=%d content_type=%q", provider, stream, response.StatusCode, response.Header.Get("Content-Type"))
	if stream && strings.Contains(response.Header.Get("Content-Type"), "text/event-stream") {
		defer response.Body.Close()
		s.responsesStreamToClaude(w, body, response.Body, reverse)
		return
	}
	defer response.Body.Close()
	var result map[string]any
	if json.NewDecoder(response.Body).Decode(&result) != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"type": "error", "error": map[string]any{"type": "api_error", "message": "invalid upstream response"}})
		return
	}
	message := responsesToClaude(result, text(body["model"]), reverse)
	if stream {
		s.writeClaudeMessageStream(w, message)
	} else {
		writeJSON(w, http.StatusOK, message)
	}
}

func claudeToResponses(body map[string]any) (map[string]any, error) {
	forward, _ := claudeToolNames(body)
	input := []any{}
	instructions := ""
	if system, ok := body["system"].(string); ok {
		instructions = system
	} else {
		parts := []string{}
		for _, raw := range asSlice(body["system"]) {
			if block, ok := raw.(map[string]any); ok && text(block["type"]) == "text" {
				parts = append(parts, text(block["text"]))
			}
		}
		instructions = strings.Join(parts, "\n")
	}
	for _, raw := range asSlice(body["messages"]) {
		message, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		role := text(message["role"])
		if role == "" {
			role = "user"
		}
		blocks := message["content"]
		if value, ok := blocks.(string); ok {
			blocks = []any{map[string]any{"type": "text", "text": value}}
		}
		content := []any{}
		flush := func() {
			if len(content) > 0 {
				copyContent := append([]any(nil), content...)
				input = append(input, map[string]any{"type": "message", "role": role, "content": copyContent})
				content = nil
			}
		}
		for _, blockRaw := range asSlice(blocks) {
			block, ok := blockRaw.(map[string]any)
			if !ok {
				continue
			}
			kind := text(block["type"])
			switch kind {
			case "text":
				partType := "input_text"
				if role == "assistant" {
					partType = "output_text"
				}
				content = append(content, map[string]any{"type": partType, "text": text(block["text"])})
			case "image":
				if role == "user" {
					source, _ := block["source"].(map[string]any)
					if text(source["type"]) == "base64" && text(source["data"]) != "" {
						media := text(source["media_type"])
						if media == "" {
							media = "image/png"
						}
						content = append(content, map[string]any{"type": "input_image", "image_url": "data:" + media + ";base64," + text(source["data"]), "detail": "high"})
					}
				}
			case "tool_use":
				flush()
				name := text(block["name"])
				if mapped := forward[name]; mapped != "" {
					name = mapped
				} else {
					name = shortIdentifier(name)
				}
				arguments, _ := json.Marshal(first(block["input"], map[string]any{}))
				input = append(input, map[string]any{"type": "function_call", "call_id": shortIdentifier(block["id"]), "name": name, "arguments": string(arguments)})
			case "tool_result":
				flush()
				input = append(input, map[string]any{"type": "function_call_output", "call_id": shortIdentifier(block["tool_use_id"]), "output": claudeToolOutput(block["content"])})
			case "thinking":
				if signature := text(block["signature"]); role == "assistant" && signature != "" {
					flush()
					input = append(input, map[string]any{"type": "reasoning", "encrypted_content": signature, "summary": []any{}})
				}
			}
		}
		flush()
	}
	request := map[string]any{"model": body["model"], "input": input, "stream": body["stream"], "store": false, "max_output_tokens": first(body["max_tokens"], 32000)}
	if instructions != "" {
		request["instructions"] = instructions
	}
	tools := []any{}
	hasWeb := false
	for _, raw := range asSlice(body["tools"]) {
		tool, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		kind, name := text(tool["type"]), text(tool["name"])
		if strings.HasPrefix(kind, "web_search_") {
			web := map[string]any{"type": "web_search"}
			if allowed := asSlice(tool["allowed_domains"]); len(allowed) > 0 {
				web["filters"] = map[string]any{"allowed_domains": allowed}
			}
			if location, ok := tool["user_location"].(map[string]any); ok {
				web["user_location"] = location
			}
			tools = append(tools, web)
			hasWeb = true
		} else if name != "" {
			mapped := forward[name]
			if mapped == "" {
				mapped = shortIdentifier(name)
			}
			tools = append(tools, map[string]any{"type": "function", "name": mapped, "description": text(tool["description"]), "parameters": first(tool["input_schema"], map[string]any{"type": "object", "properties": map[string]any{}})})
		}
	}
	if len(tools) > 0 {
		request["tools"] = tools
		choice, _ := body["tool_choice"].(map[string]any)
		choiceType, choiceName := text(choice["type"]), text(choice["name"])
		switch {
		case choiceType == "tool" && hasWeb && choiceName == "web_search":
			request["tool_choice"] = map[string]any{"type": "web_search"}
		case choiceType == "tool" && choiceName != "":
			name := forward[choiceName]
			if name == "" {
				name = shortIdentifier(choiceName)
			}
			request["tool_choice"] = map[string]any{"type": "function", "name": name}
		case choiceType == "any":
			request["tool_choice"] = "required"
		case choiceType == "none":
			request["tool_choice"] = "none"
		default:
			request["tool_choice"] = "auto"
		}
		disable, _ := choice["disable_parallel_tool_use"].(bool)
		request["parallel_tool_calls"] = !disable
	}
	request["reasoning"] = map[string]any{"effort": "medium", "summary": "auto"}
	request["include"] = []string{"reasoning.encrypted_content"}
	return request, nil
}

func claudeToolOutput(value any) any {
	if value == nil {
		return ""
	}
	if result, ok := value.(string); ok {
		return result
	}
	result := []any{}
	for _, raw := range asSlice(value) {
		part, ok := raw.(map[string]any)
		if !ok {
			result = append(result, map[string]any{"type": "input_text", "text": fmt.Sprint(raw)})
			continue
		}
		switch text(part["type"]) {
		case "text":
			result = append(result, map[string]any{"type": "input_text", "text": text(part["text"])})
		case "image":
			source, _ := part["source"].(map[string]any)
			if text(source["type"]) == "base64" && text(source["data"]) != "" {
				media := text(source["media_type"])
				if media == "" {
					media = "image/png"
				}
				result = append(result, map[string]any{"type": "input_image", "image_url": "data:" + media + ";base64," + text(source["data"]), "detail": "high"})
			}
		default:
			rawJSON, _ := json.Marshal(part)
			result = append(result, map[string]any{"type": "input_text", "text": string(rawJSON)})
		}
	}
	if len(result) == 0 {
		return ""
	}
	return result
}

func responsesToClaude(data map[string]any, model string, reverse map[string]string) map[string]any {
	content := []any{}
	webCount := 0
	for _, raw := range asSlice(data["output"]) {
		item, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		switch text(item["type"]) {
		case "reasoning":
			summary := first(item["summary"], item["content"], []any{})
			pieces := []string{}
			for _, rawPart := range asSlice(summary) {
				if part, ok := rawPart.(map[string]any); ok {
					pieces = append(pieces, text(part["text"]))
				} else {
					pieces = append(pieces, text(rawPart))
				}
			}
			signature := text(item["encrypted_content"])
			if len(pieces) > 0 || signature != "" {
				block := map[string]any{"type": "thinking", "thinking": strings.Join(pieces, "")}
				if signature != "" {
					block["signature"] = signature
				}
				content = append(content, block)
			}
		case "message":
			for _, partRaw := range asSlice(item["content"]) {
				if part, ok := partRaw.(map[string]any); ok && (text(part["type"]) == "output_text" || text(part["type"]) == "text") {
					content = append(content, map[string]any{"type": "text", "text": text(part["text"])})
				}
			}
		case "function_call", "custom_tool_call":
			arguments := first(item["arguments"], item["input"], "{}")
			var parsed any
			if value, ok := arguments.(string); ok {
				if json.Unmarshal([]byte(value), &parsed) != nil {
					parsed = map[string]any{"input": value}
				}
			} else {
				parsed = value
			}
			name := text(item["name"])
			if original := reverse[name]; original != "" {
				name = original
			}
			if name == "Read" {
				if input, ok := parsed.(map[string]any); ok && text(input["pages"]) == "" {
					delete(input, "pages")
				}
			}
			content = append(content, map[string]any{"type": "tool_use", "id": first(item["call_id"], item["id"]), "name": name, "input": first(parsed, map[string]any{})})
		case "web_search_call":
			webCount++
			action, _ := item["action"].(map[string]any)
			query := text(action["query"])
			if query == "" {
				queries := asSlice(action["queries"])
				if len(queries) > 0 {
					query = text(queries[0])
				}
			}
			id := text(item["id"])
			if id == "" {
				id = fmt.Sprintf("srvtoolu_%d", time.Now().UnixMilli())
			}
			sources := []any{}
			for _, sourceRaw := range asSlice(action["sources"]) {
				if source, ok := sourceRaw.(map[string]any); ok && text(source["url"]) != "" {
					sources = append(sources, map[string]any{"type": "web_search_result", "title": first(source["title"], source["url"]), "url": source["url"]})
				}
			}
			content = append(content, map[string]any{"type": "server_tool_use", "id": id, "name": "web_search", "input": map[string]any{"query": query}}, map[string]any{"type": "web_search_tool_result", "tool_use_id": id, "content": sources})
		}
	}
	if len(content) == 0 {
		content = append(content, map[string]any{"type": "text", "text": text(data["output_text"])})
	}
	usage, _ := data["usage"].(map[string]any)
	messageUsage := map[string]any{"input_tokens": intNumber(usage["input_tokens"]), "output_tokens": intNumber(usage["output_tokens"])}
	if details, ok := usage["input_tokens_details"].(map[string]any); ok && intNumber(details["cached_tokens"]) > 0 {
		messageUsage["cache_read_input_tokens"] = intNumber(details["cached_tokens"])
	}
	if webCount > 0 {
		messageUsage["server_tool_use"] = map[string]any{"web_search_requests": webCount}
	}
	stop := "end_turn"
	for _, raw := range content {
		if block, ok := raw.(map[string]any); ok && text(block["type"]) == "tool_use" {
			stop = "tool_use"
		}
	}
	return map[string]any{"id": first(data["id"], fmt.Sprintf("msg_%d", time.Now().UnixMilli())), "type": "message", "role": "assistant", "model": first(data["model"], model), "content": content, "stop_reason": stop, "stop_sequence": data["stop_sequence"], "usage": messageUsage}
}

func (s *server) writeClaudeMessageStream(w http.ResponseWriter, message map[string]any) {
	stream, err := newSSEWriter(w)
	if err != nil {
		return
	}
	start := cloneMap(message)
	start["content"] = []any{}
	start["stop_reason"] = nil
	start["stop_sequence"] = nil
	_ = stream.Event("message_start", map[string]any{"type": "message_start", "message": start})
	for index, raw := range asSlice(message["content"]) {
		block, _ := raw.(map[string]any)
		kind := text(block["type"])
		initial := cloneMap(block)
		switch kind {
		case "text":
			initial = map[string]any{"type": "text", "text": ""}
		case "thinking":
			initial = map[string]any{"type": "thinking", "thinking": ""}
		case "tool_use", "server_tool_use":
			initial["input"] = map[string]any{}
		}
		_ = stream.Event("content_block_start", map[string]any{"type": "content_block_start", "index": index, "content_block": initial})
		var delta any
		switch kind {
		case "text":
			delta = map[string]any{"type": "text_delta", "text": block["text"]}
		case "thinking":
			delta = map[string]any{"type": "thinking_delta", "thinking": block["thinking"]}
		case "tool_use", "server_tool_use":
			rawInput, _ := json.Marshal(first(block["input"], map[string]any{}))
			delta = map[string]any{"type": "input_json_delta", "partial_json": string(rawInput)}
		}
		if delta != nil {
			_ = stream.Event("content_block_delta", map[string]any{"type": "content_block_delta", "index": index, "delta": delta})
		}
		if kind == "thinking" && text(block["signature"]) != "" {
			_ = stream.Event("content_block_delta", map[string]any{"type": "content_block_delta", "index": index, "delta": map[string]any{"type": "signature_delta", "signature": block["signature"]}})
		}
		_ = stream.Event("content_block_stop", map[string]any{"type": "content_block_stop", "index": index})
	}
	usage, _ := message["usage"].(map[string]any)
	_ = stream.Event("message_delta", map[string]any{"type": "message_delta", "delta": map[string]any{"stop_reason": message["stop_reason"], "stop_sequence": message["stop_sequence"]}, "usage": usage})
	_ = stream.Event("message_stop", map[string]any{"type": "message_stop"})
}

func (s *server) responsesStreamToClaude(w http.ResponseWriter, body map[string]any, upstream io.Reader, reverse map[string]string) {
	stream, err := newSSEWriter(w)
	if err != nil {
		return
	}
	model := text(body["model"])
	messageID := fmt.Sprintf("msg_%d", time.Now().UnixMilli())
	started := false
	nextBlock := 0
	openKind := ""
	openIndex := -1
	pending := map[int]map[string]any{}
	emittedTools := false
	webCount := 0
	var terminal map[string]any
	start := func(response map[string]any) {
		if started {
			return
		}
		if text(response["id"]) != "" {
			messageID = text(response["id"])
		}
		if text(response["model"]) != "" {
			model = text(response["model"])
		}
		_ = stream.Event("message_start", map[string]any{"type": "message_start", "message": map[string]any{"id": messageID, "type": "message", "role": "assistant", "model": model, "content": []any{}, "stop_reason": nil, "stop_sequence": nil, "usage": map[string]any{"input_tokens": 0, "output_tokens": 0}}})
		started = true
	}
	closeBlock := func() {
		if openIndex >= 0 {
			_ = stream.Event("content_block_stop", map[string]any{"type": "content_block_stop", "index": openIndex})
			openKind = ""
			openIndex = -1
		}
	}
	open := func(kind string) int {
		start(map[string]any{})
		if openKind == kind {
			return openIndex
		}
		closeBlock()
		index := nextBlock
		nextBlock++
		initial := map[string]any{"type": kind}
		if kind == "text" {
			initial["text"] = ""
		} else {
			initial["thinking"] = ""
		}
		_ = stream.Event("content_block_start", map[string]any{"type": "content_block_start", "index": index, "content_block": initial})
		openKind = kind
		openIndex = index
		return index
	}
	emitTool := func(item map[string]any) {
		closeBlock()
		start(map[string]any{})
		index := nextBlock
		nextBlock++
		name := text(item["name"])
		if original := reverse[name]; original != "" {
			name = original
		}
		arguments := text(first(item["arguments"], item["input"], "{}"))
		_ = stream.Event("content_block_start", map[string]any{"type": "content_block_start", "index": index, "content_block": map[string]any{"type": "tool_use", "id": first(item["call_id"], item["id"]), "name": name, "input": map[string]any{}}})
		_ = stream.Event("content_block_delta", map[string]any{"type": "content_block_delta", "index": index, "delta": map[string]any{"type": "input_json_delta", "partial_json": arguments}})
		_ = stream.Event("content_block_stop", map[string]any{"type": "content_block_stop", "index": index})
		emittedTools = true
	}
	scanner := bufio.NewScanner(upstream)
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
		var event map[string]any
		if json.Unmarshal([]byte(payload), &event) != nil {
			continue
		}
		eventType := text(event["type"])
		switch eventType {
		case "response.created":
			response, _ := event["response"].(map[string]any)
			start(response)
		case "response.reasoning_summary_text.delta":
			index := open("thinking")
			_ = stream.Event("content_block_delta", map[string]any{"type": "content_block_delta", "index": index, "delta": map[string]any{"type": "thinking_delta", "thinking": text(event["delta"])}})
		case "response.output_text.delta":
			index := open("text")
			_ = stream.Event("content_block_delta", map[string]any{"type": "content_block_delta", "index": index, "delta": map[string]any{"type": "text_delta", "text": text(event["delta"])}})
		case "response.output_item.added":
			item, _ := event["item"].(map[string]any)
			if text(item["type"]) == "function_call" || text(item["type"]) == "custom_tool_call" {
				pending[intNumber(event["output_index"])] = item
			}
		case "response.function_call_arguments.delta", "response.custom_tool_call_input.delta":
			index := intNumber(event["output_index"])
			item := pending[index]
			if item == nil {
				item = map[string]any{"type": "function_call"}
				pending[index] = item
			}
			key := "arguments"
			if eventType == "response.custom_tool_call_input.delta" {
				key = "input"
			}
			item[key] = text(item[key]) + text(event["delta"])
		case "response.output_item.done":
			item, _ := event["item"].(map[string]any)
			kind := text(item["type"])
			switch kind {
			case "function_call", "custom_tool_call":
				index := intNumber(event["output_index"])
				merged := pending[index]
				if merged == nil {
					merged = map[string]any{}
				}
				for key, value := range item {
					merged[key] = value
				}
				emitTool(merged)
				delete(pending, index)
			case "reasoning":
				if signature := text(item["encrypted_content"]); signature != "" {
					index := open("thinking")
					_ = stream.Event("content_block_delta", map[string]any{"type": "content_block_delta", "index": index, "delta": map[string]any{"type": "signature_delta", "signature": signature}})
					closeBlock()
				}
			case "web_search_call":
				webCount++
				translated := responsesToClaude(map[string]any{"output": []any{item}}, model, nil)
				for _, blockRaw := range asSlice(translated["content"]) {
					block, _ := blockRaw.(map[string]any)
					closeBlock()
					index := nextBlock
					nextBlock++
					initial := cloneMap(block)
					if text(block["type"]) == "server_tool_use" {
						initial["input"] = map[string]any{}
					}
					_ = stream.Event("content_block_start", map[string]any{"type": "content_block_start", "index": index, "content_block": initial})
					if text(block["type"]) == "server_tool_use" {
						rawInput, _ := json.Marshal(block["input"])
						_ = stream.Event("content_block_delta", map[string]any{"type": "content_block_delta", "index": index, "delta": map[string]any{"type": "input_json_delta", "partial_json": string(rawInput)}})
					}
					_ = stream.Event("content_block_stop", map[string]any{"type": "content_block_stop", "index": index})
				}
			}
		case "response.completed", "response.incomplete":
			terminal, _ = event["response"].(map[string]any)
		}
	}
	start(terminal)
	closeBlock()
	usage := map[string]any{"output_tokens": 0}
	if terminalUsage, ok := terminal["usage"].(map[string]any); ok {
		usage["output_tokens"] = intNumber(terminalUsage["output_tokens"])
		if details, ok := terminalUsage["input_tokens_details"].(map[string]any); ok && intNumber(details["cached_tokens"]) > 0 {
			usage["cache_read_input_tokens"] = intNumber(details["cached_tokens"])
		}
	}
	if webCount > 0 {
		usage["server_tool_use"] = map[string]any{"web_search_requests": webCount}
	}
	stop := "end_turn"
	if emittedTools {
		stop = "tool_use"
	}
	_ = stream.Event("message_delta", map[string]any{"type": "message_delta", "delta": map[string]any{"stop_reason": stop, "stop_sequence": nil}, "usage": usage})
	_ = stream.Event("message_stop", map[string]any{"type": "message_stop"})
}
