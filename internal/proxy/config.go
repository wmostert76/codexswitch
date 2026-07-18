package proxy

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

const (
	defaultAddress        = "127.0.0.1:14555"
	loopbackToken         = "codexswitch-loopback"
	maxRequestBytes int64 = 32 << 20
)

type config struct {
	Home    string
	Address string
}

func loadConfig() (config, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return config{}, err
	}
	address := os.Getenv("CODEXSWITCH_PROVIDER_PROXY_ADDRESS")
	if address == "" {
		host := envOr("CODEXSWITCH_PROVIDER_PROXY_HOST", "127.0.0.1")
		port := envOr("CODEXSWITCH_PROVIDER_PROXY_PORT", "14555")
		address = host + ":" + port
	}
	return config{Home: home, Address: address}, nil
}

func envOr(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func readJSONObject(path string) (map[string]any, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, err
	}
	if info.Mode().Perm()&0o077 != 0 {
		return nil, fmt.Errorf("secret file permissions are too broad: %s", path)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var value map[string]any
	if err := json.Unmarshal(raw, &value); err != nil {
		return nil, err
	}
	return value, nil
}

func stringField(value map[string]any, path ...string) string {
	var current any = value
	for _, key := range path {
		object, ok := current.(map[string]any)
		if !ok {
			return ""
		}
		current = object[key]
	}
	text, _ := current.(string)
	return strings.TrimSpace(text)
}

func (c config) openRouterKey() (string, error) {
	value, err := readJSONObject(filepath.Join(c.Home, ".config/codexswitch/openrouter/auth.json"))
	if err != nil || stringField(value, "api_key") == "" {
		value, err = c.helperCredential("openrouter")
		if err != nil {
			return "", err
		}
	}
	if key := stringField(value, "api_key"); key != "" {
		return key, nil
	}
	return "", errors.New("OpenRouter API key is missing")
}

func (c config) openCodeKey() (string, error) {
	value, err := readJSONObject(filepath.Join(c.Home, ".config/codexswitch/opencode-go/auth.json"))
	if err == nil {
		if key := stringField(value, "api_key"); key != "" {
			return key, nil
		}
	}
	legacyPath := filepath.Join(c.Home, ".local/share/opencode/auth.json")
	legacyRaw, legacyErr := os.ReadFile(legacyPath)
	if legacyErr == nil {
		var legacy map[string]any
		if json.Unmarshal(legacyRaw, &legacy) == nil {
			if key := stringField(legacy, "opencode-go", "key"); key != "" {
				return key, nil
			}
		}
	}
	if helper, helperErr := c.helperCredential("opencode-go"); helperErr == nil {
		if key := stringField(helper, "api_key"); key != "" {
			return key, nil
		}
	}
	if err != nil {
		return "", err
	}
	return "", errors.New("OpenCode Go API key is missing")
}

func (c config) azureCredentials() (string, string, error) {
	value, err := readJSONObject(filepath.Join(c.Home, ".config/codexswitch/azure/auth.json"))
	if err != nil || stringField(value, "endpoint") == "" || stringField(value, "api_key") == "" {
		value, err = c.helperCredential("azure")
		if err != nil {
			return "", "", err
		}
	}
	endpoint := strings.TrimRight(stringField(value, "endpoint"), "/")
	key := stringField(value, "api_key")
	if endpoint == "" || key == "" {
		return "", "", errors.New("Azure endpoint or API key is missing")
	}
	return endpoint, key, nil
}

func (c config) helperCredential(provider string) (map[string]any, error) {
	helper := strings.TrimSpace(os.Getenv("CODEXSWITCH_CREDENTIAL_HELPER"))
	if helper == "" {
		helper, _ = exec.LookPath("codexswitch-provider-credential")
	}
	if helper == "" {
		return nil, fmt.Errorf("%s credential helper is missing", provider)
	}
	command := exec.Command(helper, provider)
	command.Env = os.Environ()
	raw, err := command.Output()
	if err != nil {
		return nil, fmt.Errorf("%s credential helper failed", provider)
	}
	var value map[string]any
	if json.Unmarshal(raw, &value) != nil {
		return nil, fmt.Errorf("%s credential helper returned invalid JSON", provider)
	}
	return value, nil
}

func (c config) openAIAccount() (string, string, error) {
	value, err := readJSONObject(filepath.Join(c.Home, ".codex/auth.json"))
	if err != nil {
		return "", "", err
	}
	token := stringField(value, "tokens", "access_token")
	account := stringField(value, "tokens", "account_id")
	if token == "" {
		return "", "", errors.New("OpenAI Codex login is missing")
	}
	return token, account, nil
}
