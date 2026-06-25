# CodexSwitch Commander

A Midnight Commander-inspired terminal control center for Codex CLI.

![CodexSwitch Commander](docs/codexswitch-commander.svg)

CodexSwitch provides a mouse-aware dual-pane TUI for switching between native
OpenAI accounts/models and OpenCode Go models. It discovers model-specific
reasoning modes, refreshes the OpenCode catalog and keeps normal `codex` usage
unchanged after a selection is applied.

## Features

- Commander-style interface using Midnight Commander's `classic-dark` palette
- OpenAI account switching without repeatedly overwriting `~/.codex/auth.json`
- OpenAI and OpenCode Go model selection
- Model-aware reasoning modes, including effort levels and thinking toggles
- Live OpenCode Go model refresh
- Function-key workflow and mouse support
- Secure account storage with `0700` directories and `0600` files
- Automatic synchronization of rotated OpenAI refresh tokens when switching
- Classic numbered fallback menu for minimal terminals

## Requirements

- Linux with Python 3.11 or newer
- Codex CLI
- OpenCode CLI for OpenCode Go support
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
symlinks under `/usr/local/bin` and installs the proxy as a user-scoped system
service running under the account that invoked the installer.

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
codexswitch accounts
codexswitch account save
codexswitch account use user@example.com
codexswitch use openai gpt-5.5
codexswitch use opencode-go deepseek-v4-pro max
codexswitch use opencode-go glm-5.2 high
codexswitch use opencode-go minimax-m3 thinking
codexswitch run [PROMPT...]
codexswitch --version
```

## Authentication

CodexSwitch does not invent a second authentication format:

- Active OpenAI auth: `~/.codex/auth.json`, managed by `codex login`
- Saved OpenAI accounts: `~/.config/codexswitch/openai-accounts/`
- OpenCode Go auth: `~/.local/share/opencode/auth.json`, managed by OpenCode

No credentials are stored in this repository.

## Proxy Authentication

The compatibility proxy listens on `127.0.0.1:14555`. By default it
accepts any local connection. To require a bearer token, set the
`CODEX_OPENCODE_PROXY_TOKEN` environment variable before starting
the service:

```bash
sudo systemctl edit codex-opencode-go-proxy.service
# Add: Environment=CODEX_OPENCODE_PROXY_TOKEN=your-secret
sudo systemctl restart codex-opencode-go-proxy.service
```

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
