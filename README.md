# CodexSwitch Commander

Switch Codex CLI between native OpenAI accounts, OpenCode Go models and
OpenRouter models from one polished terminal control center.

![CodexSwitch Commander](docs/codexswitch-commander.svg)

[![CI](https://github.com/wmostert76/codexswitch/actions/workflows/ci.yml/badge.svg)](https://github.com/wmostert76/codexswitch/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/wmostert76/codexswitch?sort=semver)](https://github.com/wmostert76/codexswitch/releases)

## What it does

CodexSwitch keeps normal `codex` usage simple: pick a provider, account, model
and reasoning mode once, then launch Codex normally with that active
configuration.

It is built for three workflows:

| Provider | What CodexSwitch handles |
| --- | --- |
| OpenAI | Native Codex auth, saved account switching and rotated token sync |
| OpenCode Go | Local Responses-compatible proxy, model catalog and reasoning variants |
| OpenRouter | API-key storage, model catalog refresh and Codex provider config |

## Highlights

- Commander-style TUI with provider/account and model panes
- Searchable classic model picker for minimal terminals
- OpenAI multi-account management without losing rotated refresh tokens
- OpenRouter API-key flow that never writes the key to `config.toml`
- OpenCode Go compatibility proxy with tool-call translation
- Provider/model isolation so OpenAI accounts never mix with OpenCode/OpenRouter
- Reproducible local install with a systemd proxy service
- GitHub releases generated from `CHANGELOG.md`

## Install

Requirements:

- Linux with Python 3.11+
- Codex CLI
- OpenCode CLI for OpenCode Go support
- OpenRouter API key for OpenRouter support
- `systemd` and `sudo` for installation into `/usr/local/bin`

```bash
git clone https://github.com/wmostert76/codexswitch.git
cd codexswitch
./install.sh
```

Start the app:

```bash
codexswitch tui
```

The installer creates `.venv`, installs Textual, links commands into
`/usr/local/bin`, installs the OpenCode Go proxy service and restarts it on
every install so updated proxy code is active immediately.

## Keyboard workflow

| Key | Action |
| --- | --- |
| `F1` | Help |
| `F2` | Provider/account panel |
| `F3` | Model panel |
| `F4` | Reasoning selector |
| `F5` | Refresh current catalog |
| `F6` | Apply selected provider/model |
| `F7` | Authenticate selected provider |
| `F8` | Reload active status |
| `F9` | Resume Codex with sandbox bypass and search |
| `F10` | Quit |

## CLI reference

```bash
codexswitch                         # show help
codexswitch tui                     # start Commander TUI
codexswitch classic                 # searchable classic picker
codexswitch use PROVIDER MODEL [REASONING]
codexswitch auth [openai|opencode-go|openrouter]
codexswitch account add             # OpenAI device sign-in
codexswitch account save [EMAIL]
codexswitch account use user@example.com
codexswitch refresh                 # OpenCode Go + OpenRouter catalogs
codexswitch list
codexswitch status
codexswitch run [PROMPT...]
codexswitch --version
```

From the TUI, `F9` applies the current selection and then starts Codex as:

```bash
codex resume --dangerously-bypass-approvals-and-sandbox --search
```

Examples:

```bash
codexswitch tui
codexswitch account add
codexswitch auth openrouter
codexswitch use openai gpt-5.5
codexswitch use opencode-go glm-5.2 high
codexswitch use opencode-go minimax-m3 thinking
codexswitch use openrouter anthropic/claude-sonnet-4.5
```

## Authentication and storage

CodexSwitch reuses provider-native auth stores where possible and keeps secrets
out of the repository.

| Secret | Location | Managed by |
| --- | --- | --- |
| Active OpenAI auth | `~/.codex/auth.json` | `codex login` |
| Saved OpenAI accounts | `~/.config/codexswitch/openai-accounts/` | CodexSwitch |
| OpenCode Go auth | `~/.local/share/opencode/auth.json` | OpenCode |
| OpenRouter key | `~/.config/codexswitch/openrouter/auth.json` | CodexSwitch |

Secret directories are written as `0700`; secret files are written as `0600`.

OpenAI account add uses Codex device authentication:

```bash
codexswitch account add
```

OpenRouter auth reads the API key without terminal echo. Codex receives it via
the installed `openrouter-token` command helper, not via plain text in
`~/.codex/config.toml`.

```bash
codexswitch auth openrouter
```

## OpenCode Go proxy

OpenCode Go exposes a chat-completions style API. Codex expects the Responses
API. The local proxy bridges that gap on `127.0.0.1:14555` and handles:

- Responses input/output conversion
- custom/function/namespace tool conversion
- `apply_patch` freeform payload wrapping
- reasoning-effort mapping from model metadata
- proxy-local web-search fallback
- optional bearer auth for manual clients

To require a dedicated proxy token for manual clients:

```bash
sudo systemctl edit codex-opencode-go-proxy.service
# Add: Environment=CODEX_OPENCODE_PROXY_TOKEN=your-secret
sudo systemctl restart codex-opencode-go-proxy.service
```

CodexSwitch itself can still authenticate with the existing OpenCode Go
credential.

## Releases

Current version is shown in all app surfaces:

```bash
codexswitch --version
codexswitch --help
codexswitch classic
```

Release notes are maintained in [CHANGELOG.md](CHANGELOG.md). Tags named `v*`
trigger the GitHub Release workflow.

## Uninstall

```bash
./uninstall.sh
```

The uninstaller removes installed commands and the proxy service. It leaves
Codex, OpenCode and CodexSwitch user configuration untouched.

## Credits

Idea, product direction and maintenance: by WAM-Software since (c) 1988

AI-assisted implementation: OpenAI Codex

## License

MIT
