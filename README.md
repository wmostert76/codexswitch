# CodexSwitch Commander

```text
   ___          _            __          _ _       _
  / __\___   __| | _____  __/ _\_      _(_) |_ ___| |__
 / /  / _ \ / _` |/ _ \ \/ /\ \\ \ /\ / / | __/ __| '_ \
/ /__| (_) | (_| |  __/>  < _\ \\ V  V /| | || (__| | | |
\____/\___/ \__,_|\___/_/\_\\__/ \_/\_/ |_|\__\___|_| |_|
                    C O M M A N D E R
```

Switch Codex CLI between native OpenAI accounts, Azure OpenAI, OpenCode Go
models and OpenRouter models from one polished terminal control center.

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
| Azure OpenAI | Endpoint/API-key storage and fixed `gpt-5.5` model selection |
| OpenCode Go | Own API-key store, local Responses-compatible proxy and model catalog |
| OpenRouter | API-key storage, model catalog refresh and Codex provider config |

## Highlights

- Commander-style TUI with Providers, Models and Reasoning panes
- OpenAI multi-account management without losing rotated refresh tokens
- Azure OpenAI selection for a single configured `gpt-5.5` deployment
- OpenRouter and OpenCode Go API-key flows that never write keys to `config.toml`
- OpenCode Go compatibility proxy with tool-call translation
- Provider/model isolation so OpenAI accounts never mix with OpenCode/OpenRouter
- Reproducible local install with dependency detection and a systemd proxy service
- GitHub releases generated from `CHANGELOG.md`

## Install

Requirements:

- Linux with `sudo` and one of `apt`, `dnf`, `yum`, `pacman`, `zypper` or `apk`
- OpenRouter API key for OpenRouter support
- OpenCode Go API key for OpenCode Go support
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

The installer detects missing Python/venv/npm dependencies on common Linux
distros, installs or updates the Codex CLI when needed, creates `.venv`,
installs Textual, links commands into `/usr/local/bin`, installs the OpenCode
Go proxy service and restarts it on every install so updated proxy code is
active immediately. On an existing git checkout, re-running `./install.sh`
first fetches tags and performs a safe `git pull --ff-only`, so it can be used
as the normal update command:

```bash
cd ~/codexswitch
./install.sh
codexswitch version
```

`codexswitch`, `codexswitch tui` and `codexswitch status` automatically check
for a newer GitHub release or newer `origin/main` revision and immediately run
the same upgrade path as `codexswitch update` when the checkout is clean. Set
`CODEXSWITCH_NO_AUTO_UPDATE=1` to suppress this startup check.

## Native launcher binaries

GitHub releases include a small native Go `codexswitch` launcher for Windows,
Linux and macOS. The launcher starts the Python Commander backend from a local
checkout. Put the binary in the repository root or set `CODEXSWITCH_HOME` to
the checkout path.

Release assets:

```text
codexswitch-windows-amd64.exe
codexswitch-linux-amd64
codexswitch-linux-arm64
codexswitch-darwin-amd64
codexswitch-darwin-arm64
SHA256SUMS
```

## Keyboard workflow

The Commander TUI follows a left-to-right `Providers → Models → Reasoning`
workflow, with full-width model details below the three selection panes. The
cyan cursor shows the item being inspected, `●` marks the active Codex
configuration and `◆` marks a pending selection. Moving through choices only
updates the pending selection; Codex configuration is not changed until you
apply or launch it. The responsive layout supports terminals from `80x24`
upward and shows a resize message below that minimum.

| Key | Action |
| --- | --- |
| `↑` / `↓` | Move through choices in the focused pane |
| `Home` / `End` | Jump to the first or last choice |
| `PageUp` / `PageDown` | Move one page through a long list |
| `←` / `→` | Move to the previous or next pane |
| `Tab` / `Shift+Tab` | Cycle forward or backward through the panes |
| `Enter` | Confirm and move right; from Reasoning, apply and launch Codex |
| `/` | Search models by display name or full model ID |
| `F1` or `?` | Help |
| `F2` or `p` | Providers/accounts pane |
| `F3` or `m` | Models pane |
| `F4` or `t` | Reasoning pane |
| `F5` or `r` | Refresh the selected provider catalog, including native OpenAI Codex models |
| `F6` or `a` | Apply the pending selection without starting Codex |
| `F7` or `l` | Authenticate the pending provider |
| `F8` or `s` | Reload active status |
| `F9` or `c` | Apply and resume Codex with sandbox bypass and search |
| `F10` or `q` | Quit; pending changes require confirmation |
| `Esc` | Close a dialog/search, or reset the pending selection to active |

Model search is case-insensitive. Use `↑`/`↓` inside the filtered results,
`Enter` to accept a model and continue to Reasoning, or `Esc` to clear the
filter. Single-letter aliases apply only on the main screen, so they do not
interfere with typing in search or credential dialogs.

Catalogs load and refresh in the background, keeping navigation responsive.
The last usable catalog remains visible if a refresh fails, and Apply/Launch
stays unavailable while the selected provider is still busy. The Commander
splash appears once per installed version and remains available from Help.

## CLI reference

```bash
codexswitch                         # show help
codexswitch tui                     # start Commander TUI
codexswitch use PROVIDER MODEL [REASONING]
codexswitch auth [openai|azure|opencode-go|openrouter]
codexswitch account add             # OpenAI device sign-in
codexswitch account save [EMAIL]
codexswitch account use user@example.com
codexswitch refresh                 # OpenCode Go + OpenRouter catalogs
codexswitch update [--check]        # update from latest GitHub release
codexswitch list
codexswitch status
codexswitch run [PROMPT...]
codexswitch version
```

From the TUI, `F9` applies the current selection and then starts Codex as:

```bash
codex resume --dangerously-bypass-approvals-and-sandbox --search
```

In the normal keyboard flow, choose a model, press `Enter` to move to
reasoning, choose the reasoning mode, then press `Enter` again to apply and
start Codex the same way as `F9`.

Examples:

```bash
codexswitch tui
codexswitch account add
codexswitch auth openrouter
codexswitch auth azure
codexswitch use azure gpt-5.5
codexswitch use openai gpt-5.5
codexswitch use opencode-go glm-5.2 high
codexswitch use opencode-go minimax-m3 thinking
codexswitch use openrouter anthropic/claude-sonnet-4.5
```

## Authentication and storage

CodexSwitch reuses provider-native auth stores where possible and keeps secrets
out of the repository.

| Secret | Nu opgeslagen in | Hoe het werkt |
| --- | --- | --- |
| Actieve OpenAI login | `~/.codex/auth.json` | `codex login` blijft eigenaar van de actieve login |
| Opgeslagen OpenAI accounts | `~/.config/codexswitch/vault.enc` | CodexSwitch bewaart en herstelt accounts uit de vault |
| Azure OpenAI credentials | `~/.config/codexswitch/vault.enc` | Endpoint, API key en API version zitten versleuteld in de vault |
| OpenCode Go API key | `~/.config/codexswitch/vault.enc` | De token helper leest de key uit de vault |
| OpenRouter API key | `~/.config/codexswitch/vault.enc` | De token helper leest de key uit de vault |

Vault flow:

| Stap | Wat gebeurt er |
| --- | --- |
| 1 | CodexSwitch schrijft secrets naar `~/.config/codexswitch/vault.enc` |
| 2 | De vault master key komt uit de OS keyring als die beschikbaar is |
| 3 | Zonder keyring valt CodexSwitch terug op `~/.config/codexswitch/vault.key` |
| 4 | Active Codex config blijft apart in `~/.codex/auth.json` en `~/.codex/config.toml` |

Run this after upgrading an existing install:

```bash
codexswitch vault migrate
```

Codex itself still owns the active `~/.codex/auth.json` file, and Azure
activation still writes the active provider settings required by Codex into
`~/.codex/config.toml`.

OpenAI account add uses Codex device authentication:

```bash
codexswitch account add
```

Azure, OpenRouter and OpenCode Go auth read API keys without terminal echo, or
through a paste/renew popup in the TUI. Codex receives keys via
installed token command helpers, not via plain text in `~/.codex/config.toml`.

```bash
codexswitch auth azure
codexswitch auth openrouter
codexswitch auth opencode-go
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

Manage the Linux systemd service independently from the main installer:

```bash
codexswitch proxy install
codexswitch proxy status
codexswitch proxy restart
codexswitch proxy uninstall
```

To require a dedicated proxy token for manual clients:

```bash
sudo systemctl edit codex-opencode-go-proxy.service
# Add: Environment=CODEX_OPENCODE_PROXY_TOKEN=your-secret
sudo systemctl restart codex-opencode-go-proxy.service
```

CodexSwitch itself authenticates with
`~/.config/codexswitch/opencode-go/auth.json`. Existing OpenCode auth is still
accepted as a migration fallback, but OpenCode CLI is no longer required for a
new installation.

## Releases

Current version is shown in all app surfaces:

```bash
codexswitch version
codexswitch --help
```

Release notes are maintained in [CHANGELOG.md](CHANGELOG.md). Tags named `v*`
trigger the GitHub Release workflow.

## Uninstall

Remove only the OpenCode Go proxy service:

```bash
codexswitch proxy uninstall
```

Remove installed CodexSwitch commands and the proxy service:

```bash
./uninstall.sh
```

The uninstaller removes installed commands and the proxy service. It leaves
Codex and CodexSwitch user configuration untouched.

## Credits

Idea, product direction and maintenance: by WAM-Software since (c) 1988

AI-assisted implementation: OpenAI Codex

## License

MIT
