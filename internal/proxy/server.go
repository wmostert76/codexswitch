package proxy

import (
	"context"
	"fmt"
	"log"
	"net"
	"net/http"
	"strings"
	"time"
)

type server struct {
	config config
	client *http.Client
	log    *log.Logger
}

func Run(logger *log.Logger) error {
	configuration, err := loadConfig()
	if err != nil {
		return err
	}
	s := newServer(configuration, logger)
	httpServer := &http.Server{
		Addr:              configuration.Address,
		Handler:           s,
		ReadHeaderTimeout: 15 * time.Second,
		IdleTimeout:       90 * time.Second,
		BaseContext: func(net.Listener) context.Context {
			return context.Background()
		},
	}
	logger.Printf("listening on http://%s", configuration.Address)
	return httpServer.ListenAndServe()
}

func newServer(configuration config, logger *log.Logger) *server {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.MaxIdleConns = 32
	transport.MaxIdleConnsPerHost = 8
	return &server{
		config: configuration,
		client: &http.Client{Transport: transport, Timeout: 10 * time.Minute},
		log:    logger,
	}
}

func (s *server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet && (r.URL.Path == "/health" || r.URL.Path == "/v1/health") {
		writeJSON(w, http.StatusOK, map[string]any{
			"ok":             true,
			"implementation": "go",
			"providers":      []string{"openai", "opencode-go", "openrouter", "azure"},
			"clients":        []string{"codex", "claude"},
		})
		return
	}
	if r.Method == http.MethodHead && strings.HasPrefix(r.URL.Path, "/claude/") {
		w.WriteHeader(http.StatusOK)
		return
	}
	parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/"), "/")
	if len(parts) == 0 || parts[0] == "" {
		writeJSON(w, http.StatusNotFound, map[string]any{"error": "unknown provider route"})
		return
	}
	if parts[0] == "claude" {
		if len(parts) < 2 || !knownProvider(parts[1]) {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "unknown Claude provider route"})
			return
		}
		s.handleClaude(w, r, parts[1])
		return
	}
	provider := parts[0]
	if !knownProvider(provider) {
		writeJSON(w, http.StatusNotFound, map[string]any{"error": fmt.Sprintf("unknown provider route: %s", r.URL.Path)})
		return
	}
	s.handleResponsesProvider(w, r, provider)
}

func knownProvider(provider string) bool {
	switch provider {
	case "openai", "opencode-go", "openrouter", "azure":
		return true
	default:
		return false
	}
}

func providerSubpath(path, provider string) string {
	prefix := "/" + provider
	if strings.HasPrefix(path, "/claude/") {
		prefix = "/claude/" + provider
	}
	result := strings.TrimPrefix(path, prefix)
	if result == "" {
		return "/"
	}
	return result
}
