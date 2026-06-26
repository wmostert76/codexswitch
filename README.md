# CodexSwitch Commander

A Midnight Commander-inspired terminal control center for Codex CLI.

![CodexSwitch Commander](docs/codexswitch-commander.svg)

CodexSwitch provides a mouse-aware dual-pane TUI for switching between native
OpenAI accounts/models, OpenCode Go models and OpenRouter models. It discovers
model-specific reasoning modes, refreshes remote catalogs and keeps normal
`codex` usage unchanged after a selection is applied.

## Features

- Commander-style interface using Midnight Commander's `classic-dark` palette
- OpenAI account switching without repeatedly overwriting `~/.codex/auth.json`
- OpenAI, OpenCode Go and OpenRouter model selection
- Model-aware reasoning modes, including effort levels and thinking toggles
- Live OpenCode Go model refresh
- OpenRouter model refresh via the OpenRouter models API
- Function-key workflow and mouse support
- Secure account storage with `0700` directories and `0600` files
- Automatic synchronization of rotated OpenAI refresh tokens when switching
- Classic numbered fallback menu for minimal terminals

## Requirements

- Linux with Python 3.11 or newer
- Codex CLI
- OpenCode CLI for OpenCode Go support
- OpenRouter API key for OpenRouter support
- `systemd` for the background compatibility proxy
- `sudo` for installation into `/usr/local/bin`

## Install

```bash
git clone https://github.com/wmostert76/codexswitch.git
cd codexswitch
./install.sh
```

Then start the interface:

```bash
codexswitch
```

The installer creates an isolated `.venv`, installs Textual, adds command
symlinks under `/usr/local/bin` and installs a system service that runs the
proxy under the account that invoked the installer. Re-running the installer
restarts the proxy so updated code becomes active immediately.

## Keys

| Key | Action |
| --- | --- |
| `F1` | Help |
| `F2` | Provider/account panel |
| `F3` | Model panel |
| `F4` | Reasoning mode |
| `F5` | Refresh OpenCode Go models |
| `F6` | Apply selection |
| `F7` | Authenticate selected provider |
| `F8` | Reload status |
| `F9` | Start Codex |
| `F10` | Quit |

## CLI

The classic menu (`codexswitch classic`) also offers OpenAI account
management (activate saved account, save current login).

```bash
codexswitch classic
codexswitch list
codexswitch refresh
codexswitch status
codexswitch auth openai
codexswitch auth opencode-go
codexswitch auth openrouter
codexswitch accounts
codexswitch account add
codexswitch account save
codexswitch account use user@example.com
codexswitch use openai gpt-5.5
codexswitch use opencode-go deepseek-v4-pro max
codexswitch use opencode-go glm-5.2 high
codexswitch use opencode-go minimax-m3 thinking
codexswitch use openrouter openrouter/auto
codexswitch run [PROMPT...]
codexswitch --version
```

## Authentication

CodexSwitch does not invent a second authentication format:

- Active OpenAI auth: `~/.codex/auth.json`, managed by `codex login`
- Saved OpenAI accounts: `~/.config/codexswitch/openai-accounts/`
- OpenCode Go auth: `~/.local/share/opencode/auth.json`, managed by OpenCode
- OpenRouter auth: `~/.config/codexswitch/openrouter/auth.json`, managed by
  `codexswitch auth openrouter`

`codexswitch auth openai` and `codexswitch account add` use Codex device
authentication, then save the resulting OpenAI account in the CodexSwitch
account store. In the TUI, select `+ add OpenAI account` or press `F7` while
OpenAI is selected.

For OpenRouter, press `F7` while OpenRouter is selected in the TUI, or run
`codexswitch auth openrouter` in classic/CLI mode. The API key is read without
terminal echo and is never written to `~/.codex/config.toml`; Codex receives it
through the installed `openrouter-token` helper.

No credentials are stored in this repository.

## Proxy Authentication

The compatibility proxy listens on `127.0.0.1:14555`. By default it
accepts any local connection. To additionally require authentication for
manual clients, set `CODEX_OPENCODE_PROXY_TOKEN` for the service:

```bash
sudo systemctl edit codex-opencode-go-proxy.service
# Add: Environment=CODEX_OPENCODE_PROXY_TOKEN=your-secret
sudo systemctl restart codex-opencode-go-proxy.service
```

CodexSwitch itself continues to authenticate with the existing OpenCode Go
credential, which the proxy also accepts. Manual clients may use either that
credential or the optional dedicated proxy token.

The proxy retries transient upstream errors (5xx, connection resets) up
to three times with exponential backoff.

## Uninstall

```bash
./uninstall.sh
```

The uninstaller removes installed commands and the proxy service. It leaves
your Codex, OpenCode and saved account configuration untouched.

## License

MIT
