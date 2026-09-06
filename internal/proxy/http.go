package proxy

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
)

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func decodeObject(w http.ResponseWriter, r *http.Request) (map[string]any, bool) {
	r.Body = http.MaxBytesReader(w, r.Body, maxRequestBytes)
	defer r.Body.Close()
	decoder := json.NewDecoder(r.Body)
	decoder.UseNumber()
	var body map[string]any
	err := decoder.Decode(&body)
	if err == nil && body == nil {
		err = fmt.Errorf("expected a JSON object")
	}
	if err == nil {
		var extra any
		if next := decoder.Decode(&extra); next != io.EOF {
			if next == nil {
				err = fmt.Errorf("expected exactly one JSON object")
			} else {
				err = next
			}
		}
	}
	if err != nil {
		status := http.StatusBadRequest
		var oversized *http.MaxBytesError
		if errors.As(err, &oversized) {
			status = http.StatusRequestEntityTooLarge
		}
		writeJSON(w, status, map[string]any{"error": "invalid JSON: " + err.Error()})
		return nil, false
	}
	return body, true
}

func copyResponse(w http.ResponseWriter, response *http.Response) {
	defer response.Body.Close()
	for _, header := range []string{"Content-Type", "Cache-Control", "Retry-After", "X-Request-Id"} {
		if value := response.Header.Get(header); value != "" {
			w.Header().Set(header, value)
		}
	}
	w.WriteHeader(response.StatusCode)
	var destination io.Writer = w
	if strings.Contains(response.Header.Get("Content-Type"), "text/event-stream") {
		if flusher, ok := w.(http.Flusher); ok {
			flusher.Flush()
			destination = flushingWriter{w, flusher}
		}
	}
	if _, err := io.Copy(destination, response.Body); err != nil {
		// Headers are already sent. Abort so clients cannot mistake a truncated
		// upstream response for a successful, complete HTTP response.
		panic(http.ErrAbortHandler)
	}
}

type flushingWriter struct {
	w io.Writer
	f http.Flusher
}

func (w flushingWriter) Write(p []byte) (int, error) {
	n, err := w.w.Write(p)
	if err == nil {
		w.f.Flush()
	}
	return n, err
}

type sseWriter struct {
	w http.ResponseWriter
	f http.Flusher
}

func newSSEWriter(w http.ResponseWriter) (*sseWriter, error) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		return nil, fmt.Errorf("streaming unsupported")
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "close")
	w.WriteHeader(http.StatusOK)
	flusher.Flush()
	return &sseWriter{w: w, f: flusher}, nil
}

func (s *sseWriter) Event(name string, value any) error {
	raw, err := json.Marshal(value)
	if err != nil {
		return err
	}
	if name != "" {
		if _, err = fmt.Fprintf(s.w, "event: %s\n", name); err != nil {
			return err
		}
	}
	if _, err = fmt.Fprintf(s.w, "data: %s\n\n", raw); err != nil {
		return err
	}
	s.f.Flush()
	return nil
}

func (s *sseWriter) Done() error {
	_, err := io.WriteString(s.w, "data: [DONE]\n\n")
	s.f.Flush()
	return err
}

func scanSSE(body io.Reader, fn func(map[string]any) error) error {
	scanner := bufio.NewScanner(body)
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
		if err := json.Unmarshal([]byte(payload), &event); err != nil {
			return fmt.Errorf("invalid SSE JSON: %w", err)
		}
		if err := fn(event); err != nil {
			return err
		}
	}
	return scanner.Err()
}

func cloneMap(value map[string]any) map[string]any {
	result := make(map[string]any, len(value))
	for key, item := range value {
		result[key] = item
	}
	return result
}
