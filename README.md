# CodexSwitch Commander

```text
   ___          _            __          _ _       _
  / __\___   __| | _____  __/ _\_      _(_) |_ ___| |__
 / /  / _ \ / _` |/ _ \ \/ /\ \\ \ /\ / / | __/ __| '_ \
/ /__| (_) | (_| |  __/>  < _\ \\ V  V /| | || (__| | | |
\____/\___/ \__,_|\___/_/\_\\__/ \_/\_/ |_|\__\___|_| |_|
                    C O M M A N D E R
```

Switch both Codex CLI and Claude Code between native OpenAI accounts, Azure
OpenAI, Microsoft Foundry Claude, OpenCode Go models and OpenRouter models from
one terminal control center.

![CodexSwitch Commander](docs/codexswitch-commander.svg)

[![CI](https://github.com/wmostert76/codexswitch/actions/workflows/ci.yml/badge.svg)](https://github.com/wmostert76/codexswitch/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/wmostert76/codexswitch?sort=semver)](https://github.com/wmostert76/codexswitch/releases)

## What it does

CodexSwitch keeps normal `codex` and `claude` usage simple: pick a client,
provider, account, model and reasoning mode once, then launch the selected
client with that active configuration. Claude is the agent client here, not a
separate model provider.

It is built for three workflows:

| Provider | What CodexSwitch handles |
| --- | --- |
| OpenAI | Native Codex auth, saved account switching and rotated token sync |
| Azure OpenAI | Direct Codex Responses v1 access plus a Claude Messages compatibility bridge for `gpt-5.6-sol` |
| Microsoft Foundry | Direct, proxy-free Claude Code integration using Entra ID or a vault-backed project API key |
| OpenCode Go | Own API-key store, unified Responses-compatible proxy and model catalog |
| OpenRouter | Direct Claude routing for Anthropic models; compatibility proxy routing for other models and Codex |

## Highlights

- Commander-style TUI with Clients, Providers, Models and Reasoning panes
- OpenAI multi-account management without losing rotated refresh tokens
- Azure OpenAI selection for a single configured `gpt-5.6-sol` deployment
- Native Claude Code routing to Claude deployments on Microsoft Foundry
- OpenRouter and OpenCode Go API-key flows that never write keys to `config.toml`
- Persistent provider/model defaults with on-demand proxy startup from Commander
- One statically linked Go compatibility proxy for OpenCode Go, Codex/OpenRouter and non-Anthropic Claude routes
- Provider/model isolation so OpenAI accounts never mix with OpenCode/OpenRouter
- Reproducible local install with dependency detection and on-demand proxy units
- GitHub releases generated from `CHANGELOG.md`

## Install

Requirements:

- Linux with `sudo` and one of `apt`, `dnf`, `yum`, `pacman`, `zypper` or `apk`
- Go 1.22 or newer; the installer installs it when the package manager provides it
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

The installer detects missing Python/venv/npm/Go dependencies on common Linux
distros, installs or updates the Codex CLI when needed, creates `.venv`,
installs Textual, builds a stripped static `codex-provider-proxy` binary, links
commands into `/usr/local/bin`, and removes obsolete proxy systemd units. On
both Linux and Windows, Commander checks proxy health
when the TUI opens and starts the unified proxy only when a compatibility-backed
Codex or Claude Code session is launched. Direct Azure Codex and Microsoft
Foundry Claude sessions do not start it. Once started, it remains active after
the terminal closes but does not start automatically after a reboot.
On an existing
git checkout, re-running `./install.sh` fetches without modifying tags and
performs a safe `git pull --ff-only`, so it can be used
as the normal update command:

```bash
cd ~/codexswitch
./install.sh
codexswitch version
```

Release versions use `JJ.MM.HHMM`: two-digit year, two-digit month and local
24-hour release time. For example, `26.06.1800` denotes a release created in
June 2026 at 18:00.

`codexswitch`, `codexswitch tui` and `codexswitch status` automatically check
for a newer GitHub release or newer `origin/main` revision and immediately run
the same upgrade path as `codexswitch update` when the checkout is clean. Set
`CODEXSWITCH_NO_AUTO_UPDATE=1` to suppress this startup check.

Main-branch upgrades pull only `origin/main` and do not require release tags to
exist on that remote. Detached release checkouts fetch the requested tag
directly from the canonical GitHub repository into an internal ref, leaving
local tags untouched.

On Windows, the updater refreshes `requirements.txt` with the native Python
interpreter that is running CodexSwitch. It does not invoke the Linux-only
`install.sh` through WSL or Git Bash.

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

The Commander TUI follows a left-to-right `Clients → Providers → Models → Reasoning`
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
| `F9` or `c` | Apply and start Codex with sandbox bypass and search |
| `F10` or `q` | Quit; pending changes require confirmation |
| `Esc` | Close a dialog/search, or reset the pending selection to active |

Model search is case-insensitive. Use `↑`/`↓` inside the filtered results,
`Enter` to accept a model and continue to Reasoning, or `Esc` to clear the
filter. Single-letter aliases apply only on the main screen, so they do not
interfere with typing in search or credential dialogs.

OpenRouter keeps its search field visible because its catalog is much larger.
Its model list shows separate `INPUT` and `OUTPUT` prices in USD per million
tokens, consistently formatted with two decimals. Click the `MODEL` or grouped
price heading to sort ascending; click the same heading again to reverse the
order. Cost sorting uses the combined input and output price.

Cached catalogs load in the background without a network refresh at startup.
Use `F5` to refresh only the selected provider. The last usable catalog
remains visible if a refresh fails, and Apply/Launch
stays unavailable while the selected provider is still busy. The Commander
splash appears once per installed version and remains available from Help.

## CLI reference

```bash
codexswitch                         # show help
codexswitch tui                     # start Commander TUI
codexswitch use [codex|claude] PROVIDER MODEL [REASONING]
codexswitch auth [openai|azure|opencode-go|openrouter]
codexswitch account add             # OpenAI device sign-in
codexswitch account save [EMAIL]
codexswitch account use user@example.com
codexswitch refresh                 # OpenCode Go + OpenRouter catalogs
codexswitch update [--check]        # update from latest GitHub release
codexswitch list
codexswitch status
codexswitch run [codex|claude] [ARGS...]
codexswitch version
```

From the TUI, `F9` applies the current selection and then starts Codex as:

```bash
codex --dangerously-bypass-approvals-and-sandbox --search
```

With Claude selected, F9 starts `claude --dangerously-skip-permissions`.
CodexSwitch merges only its endpoint and model values into Claude's user
settings and leaves permissions, MCP configuration and other settings intact.
Its API-key helper starts the loopback proxy on demand when protocol translation
is required, so a later plain `claude` command uses the applied selection too.
OpenRouter-hosted Anthropic models use OpenRouter's native Messages endpoint
directly; the helper returns the vault-backed OpenRouter key without starting
the proxy. Native OpenAI through Claude uses an experimental ChatGPT/Codex
OAuth transport.

Microsoft Foundry is the exception: Claude Code uses its official native
Foundry integration directly, without the loopback proxy. Configure a Foundry
resource or base URL, optional comma-separated deployment names and either an
API key or an existing `az login` session. API keys stay in the CodexSwitch
vault and are injected only into processes launched by CodexSwitch; Entra ID
also permits a later plain `claude` launch without storing a key.

The ChatGPT Codex endpoint rejects external system/developer messages, so the
experimental OpenAI route omits Claude Code's system prompt while retaining
the user conversation and tool schemas. Claude's server-side WebSearch schema
is mapped to OpenAI's native Responses web-search tool and returned URL
citations are streamed back as Claude server-tool results. Responses events are
translated incrementally to Claude SSE, including thinking state, text,
function calls and native web search. Long tool identifiers, explicit tool
choice, parallel-tool settings, cached-token usage and terminal stop reasons
are normalized across both protocols. Read, Write and Bash were verified
end-to-end through the native Claude Code client; behavior may still differ
from native Codex on complex agent workflows.

Live OpenAI compatibility on Claude Code 2.1.212:

| Capability | Result |
| --- | --- |
| Read, Write, Edit and Bash | Passed with verified file/shell markers |
| Glob and Grep | Not exposed by Claude Code 2.1.212; use Read, Bash or an available agent workflow |
| WebSearch and WebFetch | Passed |
| NotebookEdit | Passed with verified notebook content |
| Image reads | Passed: logo, photo, two labeled diagrams, eight-panel orientation chart, exact 8×8 color counts and a two-image comparison |
| MCP stdio tools | Passed with an exact echo marker from the MCP reference server |
| Multiple tool calls in one task | Passed with paired Bash and Write results; concurrent timing was not proven |
| Agent/subagent | Passed with an exact foreground-agent result marker |
| TodoWrite | Not available in this Claude Code release |

Live Azure OpenAI compatibility with `gpt-5.6-sol` on Claude Code 2.1.211:

| Capability | Result |
| --- | --- |
| Text response | Passed |
| Read, Write, Edit, Glob, Grep and Bash | Passed |
| WebSearch and WebFetch | Passed |
| NotebookEdit and image reads | Passed |
| MCP stdio tools | Passed with the MCP reference echo server |
| Agent/subagent | Passed from a Git worktree with a bounded parent run |
| Multiple tool calls in one task | Passed |

Live OpenRouter compatibility on Claude Code 2.1.211, tested 2026-07-17:

| Model | Built-in tool matrix | MCP | Agent |
| --- | --- | --- | --- |
| `deepseek/deepseek-v4-pro` | Passed | Passed | Passed |
| `z-ai/glm-5.2` | Passed; slower multi-tool completion | Passed | Passed |
| `qwen/qwen3.7-max` | Passed | Passed | Passed |
| `moonshotai/kimi-k3` | Partial: Read, Write, Edit, Glob, Bash, web and image reads passed; Grep and NotebookEdit timed out | Timed out | Passed |
| `moonshotai/kimi-k2.7-code` | Passed | Passed | Passed |

The built-in matrix covers Read, Write, Edit, Glob, Grep, Bash, WebSearch,
WebFetch, NotebookEdit and image reads. Kimi K3 answered ordinary prompts and
individual tool calls, but repeated OpenRouter upstream failures made long
tool chains unreliable during this test. A clean full-matrix retry ended after
approximately 290 seconds with OpenRouter HTTP 429 after the initial Read call,
so that retry was rate-limited and is not counted as an additional tool
compatibility failure.
Kimi K2.7 Code completed the same full matrix and is therefore the recommended
Kimi option for tool-heavy Claude Code sessions until K3 is more reliable.

`TodoWrite` remains unavailable in this Claude Code release regardless of the
selected provider.

In the normal keyboard flow, choose a model, press `Enter` to move to
reasoning, choose the reasoning mode, then press `Enter` again to apply and
start Codex the same way as `F9`.

Examples:

```bash
codexswitch tui
codexswitch account add
codexswitch auth openrouter
codexswitch auth azure
codexswitch auth foundry
codexswitch use azure gpt-5.6-sol low
codexswitch use claude foundry claude-sonnet-5
codexswitch use openai gpt-5.5
codexswitch use claude openrouter anthropic/claude-sonnet-4.5 high
codexswitch use opencode-go glm-5.2 high
codexswitch use opencode-go minimax-m3 thinking
codexswitch use openrouter anthropic/claude-sonnet-4.5
```

Codex connects directly to Azure OpenAI Responses v1. A command-backed auth
helper reads the Azure key from the protected vault, and a local fixed model
catalog avoids an incompatible Azure `/models` refresh. Claude Code still uses
the loopback Messages-to-Responses bridge when Azure `gpt-5.6-sol` is selected.

OpenCode Go, Codex/OpenRouter and non-Anthropic Claude routes share one loopback
Go process on port `14555`. It exposes OpenAI Responses routes plus the Claude
Messages compatibility routes, translates streaming events directly and reads
vault-backed provider credentials through a narrow local helper. Microsoft
Foundry Claude and OpenRouter-hosted
Anthropic models bypass it entirely. Dispatch is
never inferred from model names. Commander shows one compact health indicator
and starts the unified proxy after F9 closes the TUI only for a proxy-backed
selection. F5 refreshes the display.
Windows creates no service or Scheduled Task; the Linux unit is disabled at
boot and started on demand.

## Authentication and storage

CodexSwitch reuses provider-native auth stores where possible and keeps secrets
out of the repository.

| Secret | Nu opgeslagen in | Hoe het werkt |
| --- | --- | --- |
| Actieve OpenAI login | `~/.codex/auth.json` | `codex login` blijft eigenaar van de actieve login |
| Opgeslagen OpenAI accounts | Gedeelde versleutelde vault | CodexSwitch haalt accounts bij ieder gebruik opnieuw uit Object Storage |
| Azure OpenAI credentials | Gedeelde versleutelde vault | Endpoint en API-key blijven uit `config.toml` en lokale caches |
| OpenCode Go API key | Gedeelde versleutelde vault | De token helper doet een verse remote vault-read |
| OpenRouter API key | Gedeelde versleutelde vault | De credential helper doet voor de Go-proxy een verse remote vault-read |

Vault flow:

| Stap | Wat gebeurt er |
| --- | --- |
| 1 | De wizard migreert de lokale vault client-side versleuteld naar Hetzner S3 |
| 2 | S3-credentials en de gedeelde passphrase staan alleen in de OS-keyring, encrypted systemd credentials of environment |
| 3 | CLI/proxy-reads halen S3 opnieuw op; Commander gebruikt één RAM-cache per TUI-sessie en F5 ververst die expliciet |
| 4 | Na verificatie verwijdert de wizard lokaal `vault.enc` en `vault.key` |
| 5 | De TUI toont vooraan in de statusbalk `VAULT ONLINE` of `VAULT OFFLINE` |
| 6 | Actieve Codex config blijft apart in `~/.codex/auth.json` en `~/.codex/config.toml` |

Run this after upgrading an existing install:

```bash
codexswitch vault migrate
```

Configure the shared vault on the first or a new machine with the interactive
wizard. The endpoint and bucket defaults are prefilled:

```bash
codexswitch vault remote configure
codexswitch vault status
```

The wizard asks for the S3 Access Key ID, S3 Secret Access Key and the same
shared vault passphrase on every machine. It uses
`https://fsn1.your-objectstorage.com`, bucket `wmostert` and object
`codexswitch/vault.enc` by default. On headless Linux hosts without an OS
keyring, the wizard automatically stores these three bootstrap secrets as
machine-bound encrypted systemd user credentials. CLI, TUI, the OpenCode token helper and
the proxy read that same protected storage after every restart.

Environment injection remains available for ephemeral deployments:

```text
CODEXSWITCH_S3_ACCESS_KEY_ID
CODEXSWITCH_S3_SECRET_ACCESS_KEY
CODEXSWITCH_REMOTE_VAULT_PASSPHRASE
```

`remote-vault.json` contains only endpoint, bucket, region and object name;
it never contains credentials or provider secrets.

Codex itself still owns the active `~/.codex/auth.json` file, and Azure
activation still writes the active provider settings required by Codex into
`~/.codex/config.toml`.

OpenAI account add uses Codex device authentication:

```bash
codexswitch account add
```

Azure, Foundry, OpenRouter and OpenCode Go auth read API keys without terminal echo, or
through a paste/renew popup in the TUI. Azure asks only for the resource URL
and API key and normalizes the URL to `/openai/v1`. Foundry accepts a resource
name or base URL, optional deployment names and an optional API key; an empty
key selects Azure CLI/Entra ID authentication. Azure and OpenCode Go use
installed token helpers for later direct client starts, while proxy-backed
routes read their keys from the protected vault. Provider, model and reasoning remain selected,
while Commander ensures the required proxy is running immediately before
Codex starts. No API key is stored in `~/.codex/config.toml`.

```bash
codexswitch auth azure
codexswitch auth foundry
codexswitch auth openrouter
codexswitch auth opencode-go
```

## Unified provider proxy

OpenCode Go exposes a chat-completions style API. Codex expects the Responses
API. The unified local proxy bridges that gap, routes OpenRouter, and translates
Claude Messages requests for providers that do not natively implement that
protocol. Its OpenCode Go engine handles:

- Responses input/output conversion
- custom/function/namespace tool conversion
- `apply_patch` freeform payload wrapping
- reasoning-effort mapping from model metadata
- proxy-local web-search fallback
- optional bearer auth for manual clients

To require a dedicated proxy token for manual clients:

```bash
export CODEX_OPENCODE_PROXY_TOKEN=your-secret
codexswitch tui
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

Remove installed CodexSwitch commands and any obsolete proxy service units:

```bash
./uninstall.sh
```

The uninstaller leaves Codex and CodexSwitch user configuration untouched.

## Credits

Idea, product direction and maintenance: by WAM-Software since (c) 1988

AI-assisted implementation: OpenAI Codex

## License

MIT
