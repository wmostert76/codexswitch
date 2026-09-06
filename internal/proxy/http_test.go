package proxy

import (
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestDecodeObjectRejectsInvalidBodies(t *testing.T) {
	for _, body := range []string{"null", "[]", "{} {}", "{} trailing", ""} {
		t.Run(body, func(t *testing.T) {
			w := httptest.NewRecorder()
			_, ok := decodeObject(w, httptest.NewRequest("POST", "/", strings.NewReader(body)))
			if ok || w.Code != http.StatusBadRequest {
				t.Fatalf("ok=%v status=%d", ok, w.Code)
			}
		})
	}
}

func TestDecodeObjectOversize(t *testing.T) {
	w := httptest.NewRecorder()
	body := `{"input":"` + strings.Repeat("x", int(maxRequestBytes)) + `"}`
	_, ok := decodeObject(w, httptest.NewRequest("POST", "/", strings.NewReader(body)))
	if ok || w.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("ok=%v status=%d", ok, w.Code)
	}
}

type interruptedBody struct{}

func (interruptedBody) Read([]byte) (int, error) { return 0, io.ErrUnexpectedEOF }

func TestCopyResponseAbortsOnTruncation(t *testing.T) {
	defer func() {
		if recovered := recover(); recovered != http.ErrAbortHandler {
			t.Fatalf("expected HTTP abort, got %v", recovered)
		}
	}()
	copyResponse(httptest.NewRecorder(), &http.Response{StatusCode: 200,
		Header: http.Header{}, Body: io.NopCloser(interruptedBody{})})
}

type flushCheckingBody struct {
	recorder *httptest.ResponseRecorder
	sent     bool
}

func (b *flushCheckingBody) Read(p []byte) (int, error) {
	if b.sent {
		if !b.recorder.Flushed {
			return 0, errors.New("stream was buffered")
		}
		return 0, io.EOF
	}
	b.sent = true
	b.recorder.Flushed = false
	return copy(p, "data: hello\n\n"), nil
}

func TestCopyResponseFlushesStreamAndPreservesRetryAfter(t *testing.T) {
	w := httptest.NewRecorder()
	copyResponse(w, &http.Response{StatusCode: 200,
		Header: http.Header{"Content-Type": {"text/event-stream"}, "Retry-After": {"10"}},
		Body:   io.NopCloser(&flushCheckingBody{recorder: w})})
	if !w.Flushed || w.Header().Get("Retry-After") != "10" {
		t.Fatal("missing flush or retry metadata")
	}
}
