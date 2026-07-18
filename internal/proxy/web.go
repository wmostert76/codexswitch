package proxy

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

func webSearch(query string) string {
	client := &http.Client{Timeout: 15 * time.Second}
	endpoint := "https://api.duckduckgo.com/?" + url.Values{"q": {query}, "format": {"json"}, "no_html": {"1"}, "skip_disambig": {"1"}}.Encode()
	request, _ := http.NewRequest(http.MethodGet, endpoint, nil)
	request.Header.Set("User-Agent", "codexswitch-proxy-go/1")
	response, err := client.Do(request)
	if err != nil {
		return "Search failed: " + err.Error()
	}
	defer response.Body.Close()
	var data map[string]any
	if json.NewDecoder(response.Body).Decode(&data) != nil {
		return "Search returned an invalid response"
	}
	lines := []string{}
	heading, abstract, abstractURL := text(data["Heading"]), text(data["AbstractText"]), text(data["AbstractURL"])
	if heading != "" || abstract != "" {
		lines = append(lines, fmt.Sprintf("- %s: %s %s", firstString(heading, query), abstract, abstractURL))
	}
	appendTopics(&lines, asSlice(data["RelatedTopics"]), 8)
	if len(lines) == 0 {
		lines = append(lines, "- Search URL: https://duckduckgo.com/?q="+url.QueryEscape(query))
	}
	return strings.Join(lines, "\n")
}

func appendTopics(lines *[]string, topics []any, limit int) {
	for _, raw := range topics {
		if len(*lines) >= limit {
			return
		}
		topic, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		if nested := asSlice(topic["Topics"]); len(nested) > 0 {
			appendTopics(lines, nested, limit)
			continue
		}
		label, link := text(topic["Text"]), text(topic["FirstURL"])
		if label != "" && link != "" {
			*lines = append(*lines, "- "+label+": "+link)
		}
	}
}
func firstString(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}
