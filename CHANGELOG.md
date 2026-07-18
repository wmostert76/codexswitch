# Changelog

All notable CodexSwitch changes are documented here.

## [26.7.18.1816] - 2026-07-18

### Fixed

- Corrected the timestamp release format to include the day. Releases now use
  `JJ.M.DD.HHMM` in local 24-hour time; this release is `26.7.18.1816` for
  18 July 2026 at 18:16 CEST.
- Version comparison remains compatible with historical SemVer tags and the
  superseded three-part `JJ.MM.HHMM` release.

## [26.07.1800] - 2026-07-18

### Added

- Replaced the active Python compatibility-proxy process with an in-repository,
  statically linked Go implementation. It retains the existing port and routes
  for OpenAI OAuth, Azure OpenAI, OpenCode Go, OpenRouter and Claude Messages,
  while Commander, account management and the Textual TUI remain in Python.
- The installer now detects Go, builds `cmd/codexswitch-proxy` reproducibly and
  installs the binary as `codex-provider-proxy`. A narrow credential helper
  preserves access to local and remote encrypted vault entries without placing
  provider secrets in the Go process arguments, logs or configuration.
- Added Go-native coverage for unified health, Claude tool/image translation,
  long identifiers, thinking state, cached usage, namespace/custom tools,
  Responses SSE collection, complete Codex model metadata and an end-to-end
  Claude-to-Azure round trip.

### Fixed

- Claude Code WebSearch through the OpenAI Responses bridge now maps
  Anthropic's server-side search schema to OpenAI's native `web_search` tool
  and converts search calls plus URL citations back into Claude server-tool
  streaming blocks. Live verification with `gpt-5.6-sol` returned real source
  URLs instead of `Did 0 searches`.
- Empty optional `pages` arguments emitted by GPT for Claude's Read tool are
  now removed by the bridge, avoiding a needless validation failure before
  text and image reads.
- Claude Read image results are now retained as high-detail Responses vision
  inputs instead of being discarded while translating the tool result. A live
  six-image matrix with `gpt-5.6-sol` passed a logo, photo, two labeled
  diagrams, an eight-panel orientation chart and exact 8x8 color-cell counts;
  a separate two-image task also identified both files correctly.
- Claude/OpenAI protocol translation now preserves mixed content ordering,
  safely shortens overlong tool names and call IDs with deterministic reverse
  mapping, honors explicit `auto`/`any`/`none`/named tool choices and Claude's
  parallel-tool switch, and forwards web-search location hints.
- OpenAI reasoning summaries and encrypted continuation state are now returned
  as Claude thinking blocks. Cached-token usage, terminal stop reasons and stop
  sequences are retained instead of being flattened to generic defaults.
- Streaming Claude requests now translate OpenAI Responses SSE events directly
  to Claude SSE for thinking, text, function calls and native web search. The
  experimental ChatGPT OAuth transport forwards the upstream event stream
  instead of buffering the complete response first. Live Claude Code checks
  passed Bash, WebSearch and an image Read through the streaming route.
- The Go OpenAI transport forces the downstream SSE content type when the
  ChatGPT Codex endpoint omits it, preventing Claude from treating a valid
  stream as plain text. OpenRouter's catalog is normalized to Codex's complete
  `models` schema instead of forwarding the provider-specific `data` envelope.
- Live Go-proxy verification passed Claude Code tool calls on OpenAI, Azure and
  OpenRouter, image input and OpenAI WebSearch/thinking, plus a normal Codex CLI
  OpenRouter shell call. OpenCode Go returned its current insufficient-balance
  error correctly, so a paid completion could not be re-run in this session.
- Revalidated tool results on Claude Code 2.1.212 rather than counting tool
  invocations: Read, Write, Edit, Bash, NotebookEdit, WebSearch, WebFetch,
  image reads, namespaced MCP and Agent passed. Claude Code 2.1.212 does not
  advertise standalone Glob or Grep tools in these sessions.

### Changed

- This release introduced the superseded `JJ.MM.HHMM` format; it was corrected
  in `26.7.18.1816` to include the day.

## [1.8.0] - 2026-07-17

### Added

- Added Claude Code as an alternative client for the existing provider, model
  and reasoning selection. Commander can now apply and launch either Codex or
  Claude with the same active configuration.
- Added an Anthropic Messages compatibility route to the unified provider
  proxy for Azure OpenAI, OpenCode Go, OpenRouter and an explicitly
  experimental native OpenAI Codex OAuth route.
- Added persistent, merge-safe Claude settings and an API-key helper that
  starts the loopback proxy on demand without storing provider credentials in
  Claude configuration.
- Added Microsoft Foundry as a Claude-only provider using Claude Code's native,
  proxy-free Foundry integration. It supports Entra ID, vault-backed API keys
  and custom deployment names without writing keys to Claude settings.
- Added proxy-free Claude Code routing for OpenRouter-hosted Anthropic models
  through OpenRouter's native Messages endpoint. Non-Anthropic OpenRouter
  models retain the compatibility proxy.

### Fixed

- The experimental OpenAI OAuth transport now conforms to the ChatGPT Codex
  endpoint's required streaming-only, non-stored request format and rebuilds
  complete Responses output from SSE events. Live Claude Code verification
  passed with the Read, Write and Bash tools on the active OpenAI account.
- Extended live OpenAI verification to Edit, Glob, Grep, WebSearch, WebFetch,
  NotebookEdit, image reads, multi-call tool responses and a local MCP echo
  server. Agent subcalls return correct results but can continue scheduling
  calls instead of terminating; TodoWrite is unavailable in Claude Code
  2.1.211 and is not advertised as supported.
- Repeated the instrumented Claude/OpenAI tool matrix for `gpt-5.5`,
  `gpt-5.4`, `gpt-5.4-mini` and `gpt-5.3-codex-spark`. Every model passed
  Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, NotebookEdit,
  image reads, a local MCP echo call and a bounded single Agent subcall.
- Tested the current OpenRouter flagships through Claude Code:
  `deepseek/deepseek-v4-pro`, `z-ai/glm-5.2` and `qwen/qwen3.7-max` passed the
  full built-in tool matrix, MCP and Agent. `moonshotai/kimi-k3` passed text,
  Read, Write, Edit, Glob, Bash, web, image reads and Agent, but Grep,
  NotebookEdit and MCP timed out amid repeated upstream failures.
- Verified `moonshotai/kimi-k2.7-code` as the more reliable Kimi fallback: it
  passed the complete built-in tool matrix, image reads, MCP and Agent in the
  same Claude Code/OpenRouter test setup where Kimi K3 remained partial.
- Retried the complete Kimi K3 matrix from a clean Claude configuration; the
  run reached Read but OpenRouter rate-limited the continuation with HTTP 429
  after roughly 290 seconds. The retry is recorded as inconclusive rather than
  as a new tool-compatibility failure.
- Verified `anthropic/claude-sonnet-5` directly from Claude Code to OpenRouter
  with the local proxy stopped. Read, Write, Edit, Glob, Grep, Bash, web,
  NotebookEdit, image reads, MCP and Agent all passed through OpenRouter's
  Anthropic Messages endpoint.
- Verified Claude Code end to end against Azure OpenAI `gpt-5.6-sol`: text,
  Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, NotebookEdit, image
  reads, multi-tool tasks, a local MCP echo tool and a bounded Agent subcall
  all passed through the unified proxy.
- Codex now connects directly to Azure OpenAI Responses v1 instead of routing
  through the local proxy. A command-backed vault helper supplies auth and a
  local Codex catalog prevents incompatible Azure `/models` refreshes. Live
  direct verification passed shell, file patching, web search and MCP tools.
- Commander no longer starts the compatibility proxy during catalog loading;
  proxy-backed clients start it on demand immediately before launch.
- Claude health probes and disconnected streaming clients are now handled
  without HTTP 501 responses or BrokenPipe tracebacks.
- Claude compatibility routes now use only the configured `apiKeyHelper` for
  loopback authentication, avoiding Claude Code's conflicting-auth warning
  when `ANTHROPIC_AUTH_TOKEN` and `apiKeyHelper` were both configured.
- Installation now stops a detached proxy launched through the installed
  symlink and preserves/replaces a legacy per-user launcher that would shadow
  the current checkout on `PATH`.
- Claude launches now resolve npm's installed platform-native executable when
  the generated `claude` symlink points at the non-executable fallback script.

## [1.7.3] - 2026-07-14

### Fixed

- Release updates on `main` no longer fetch a tag before pulling, fixing
  upgrades through a local or mirrored `origin` that has the release commit
  but not the tag created later by GitHub Actions. Detached checkouts fetch the
  release directly from canonical GitHub into an internal ref, avoiding both
  missing mirror tags and conflicts with local tags.

## [1.7.2] - 2026-07-14

### Changed

- Linux now matches Windows by starting the unified provider proxy as a
  detached background process instead of a systemd service. Upgrades remove
  obsolete service units and the systemd-specific proxy management commands
  have been removed.

## [1.7.1] - 2026-07-14

### Fixed

- Updates now fetch only the requested release tag and ignore unrelated
  historical tag conflicts, preventing a rewritten old tag from blocking both
  manual and automatic upgrades. Installer branch updates also skip tags.

### Changed

- Commander now starts the unified provider proxy when the TUI opens, so its
  health is ready before selecting or launching a non-native provider.

## [1.7.0] - 2026-07-14

### Changed

- OpenRouter's Commander model list now marks all 23 free models tested through
  the native Codex CLI and unified Responses proxy: `!` for basic shell-only
  compatibility, `x` for failed or unavailable Codex tooling and `~` for
  repeatedly rate-limited endpoints. The selected model's measured limitation
  is also shown in Model Details.

## [1.6.0] - 2026-07-14

### Changed

- Split the thin `codexswitch` command from the importable backend module, so
  the TUI uses normal module imports instead of executing the CLI with `runpy`.
- Removed unused per-provider proxy wrappers, dead status helpers and the
  obsolete `openrouter-token` command. Upgrade cleanup for old installations
  remains in place.
- Simplified `status` output by dropping legacy OpenCode file locations.

### Performance

- A status command now downloads and decrypts a remote credential vault only
  once instead of once per provider.

## [1.5.2] - 2026-07-14

### Fixed

- The unified Azure `/models` route now returns complete Codex model metadata,
  preventing a harmless catalog decoding error during Codex startup.

## [1.5.1] - 2026-07-14

### Fixed

- The first post-upgrade F9 start now automatically rewrites an active legacy
  `14555`/`14556`/`14557` provider URL to its unified provider route before
  starting the proxy, including when the TUI selection itself is unchanged.

## [1.5.0] - 2026-07-14

### Changed

- Replaced the three provider proxy processes with one unified loopback proxy
  on port `14555`. Stable `/opencode-go`, `/openrouter` and `/azure` route
  prefixes dispatch to isolated provider engines without relying on model IDs.
- Commander now shows one unified provider-proxy health indicator and starts
  the single proxy on demand for every non-native provider.
- The unified Azure route now serves the fixed model catalog locally instead
  of logging a non-fatal `/models` 404 during Codex startup.
- Linux installs one disabled-by-default `codex-provider-proxy.service` and
  removes the three legacy proxy units and command symlinks during upgrades.

## [1.4.4] - 2026-07-14

### Changed

- Commander now starts only the proxy required by the selected provider after
  the TUI closes and immediately before Codex launches, on both Windows and
  Linux. Linux installs proxy units for on-demand use without enabling them at
  boot, and Windows does not create services or scheduled tasks.
- Commander now shows live OpenCode Go, OpenRouter and Azure proxy health in a
  compact, color-coded status row; startup and F5 refresh the indicators.

### Fixed

- Starting an already-active provider with F9 now still performs the required
  proxy startup check before launching Codex.

## [1.4.3] - 2026-07-14

### Fixed

- Provider, model and reasoning selections now remain usable when Codex is
  started later through plain `codex`. Azure uses a vault-backed loopback
  passthrough and OpenRouter reuses its vault-backed loopback proxy, so neither
  provider depends on launch-only environment variables or stores API keys in
  `config.toml`.
- Windows updates now refresh Python dependencies with the active native
  interpreter instead of passing a `C:\\...` checkout path to the Linux-only
  `install.sh`, which failed when projects were stored in paths such as
  OneDrive folders.

## [1.4.2] - 2026-07-14

### Fixed

- OpenRouter now runs through a dedicated loopback compatibility proxy that
  translates Codex native namespace, custom and function tools into standard
  OpenRouter function calls and maps tool results back to Codex. This fixes
  `No endpoints found that support the native namespace tool type` without
  disabling plugins, MCP tools, shell tools or `apply_patch`.

## [1.4.1] - 2026-07-14

### Changed

- Restyled OpenRouter pricing as clean, aligned `INPUT` and `OUTPUT` columns
  with consistent `$0.00` formatting, clearer active-sort highlighting and a
  less intrusive model search field.

## [1.4.0] - 2026-07-14

### Added

- OpenRouter models now show input/output costs in USD per million tokens and
  can be sorted in either direction by model ID or combined cost through
  clickable column headings.
- OpenRouter now keeps a dedicated model search field visible for fast
  case-insensitive filtering by full model ID or display name.

## [1.3.0] - 2026-07-14

### Fixed

- Commander now passes the vault-backed provider environment when launching
  Codex on Linux and macOS, so Azure and OpenRouter credentials are available
  after Apply/Start just as they are through `codexswitch run` and on Windows.

## [1.2.4] - 2026-07-13

### Changed

- Commander fetches and decrypts the shared vault once per TUI session and
  keeps the decrypted data only in process memory. Navigation no longer causes
  an S3 request per highlighted option; F5 explicitly reloads the RAM cache.

## [1.2.3] - 2026-07-13

### Changed

- The Commander vault badge now renders `VAULT ONLINE` in white on green and
  `VAULT OFFLINE` in white on red for immediate visual recognition.

## [1.2.2] - 2026-07-13

### Fixed

- OpenRouter now uses Codex's native `env_key` provider authentication with a
  launch-time key loaded from the shared vault. This avoids a reproducible
  Windows Codex crash in the custom token-command authentication path.

## [1.2.1] - 2026-07-13

### Added

- Headless Linux installations now persist shared-vault bootstrap secrets in
  machine-bound encrypted systemd user credentials when no OS keyring is
  available. CLI, TUI, token helpers and proxy all use the same storage.

## [1.2.0] - 2026-07-13

### Changed

- Azure authentication now asks only for the resource URL and API key, uses
  the Azure OpenAI Responses v1 endpoint and keeps the key exclusively in the
  encrypted vault instead of copying it into `config.toml`.
- Commander now loads cached model catalogs at startup without refreshing
  OpenCode Go or other remote catalogs; `F5` remains the explicit refresh.
- Provider credentials and saved OpenAI accounts can now live exclusively in
  a client-side encrypted shared Hetzner S3 vault. Every read fetches the
  object again and remote mode never falls back to a local credential cache.

### Added

- Added `codexswitch vault remote configure` as a new-machine/first-machine
  wizard using OS-keyring protected S3 credentials and a shared passphrase.
- Added persistent `VAULT ONLINE`, `VAULT OFFLINE` or `VAULT LOCAL` state at
  the front of the Commander status bar.

### Fixed

- Azure and OpenAI Apply/Start continue to write the selected provider, model
  and reasoning effort to Codex `config.toml` before launch.
- Windows Commander launches the native Codex executable when installed via
  npm, gives it the inherited console streams and provider environment, and
  starts Python-backed proxy/token helpers through the active interpreter.
- Generated Codex TOML now escapes Windows paths and other string values
  correctly, including the OpenRouter model-catalog path.
- Windows-launch coverage no longer makes `pathlib` instantiate Windows paths
  on Linux CI runners.

## [1.1.3] - 2026-07-13

### Fixed

- Fixed Codex sessions closing immediately after launch on Windows by keeping
  the Commander process alive while the Windows Codex subprocess is running.

## [1.1.2] - 2026-07-13

### Changed

- Commander now starts a new Codex session instead of launching with `resume`;
  sandbox bypass and search remain enabled.

## [1.1.1] - 2026-07-13

### Changed

- Removed `gpt-5.5` from the current Azure model selection; Azure now
  exclusively offers `gpt-5.6-sol`.

## [1.1.0] - 2026-07-13

### Changed

- Updated the fixed Azure OpenAI model from `gpt-5.5` to `gpt-5.6-sol`.
- Added Azure reasoning selection for `low` (default), `medium`, `high`,
  `xhigh`, `max` and `ultra`, with matching validation in the CLI and
  Commander TUI.

## [1.0.0] - 2026-07-10

### Changed

- Redesigned the Commander TUI around a responsive three-pane
  `Providers → Models → Reasoning` workflow with full-width model details.
- Added complete arrow, Home/End, PageUp/PageDown, Tab and Shift+Tab navigation,
  plus `?`, `p`, `m`, `t`, `r`, `a`, `l`, `s`, `c` and `q` alternatives for
  the existing `F1`–`F10` actions.
- Separated active and pending selections visually: browsing no longer changes
  Codex until `F6`/`a` applies it or the final `Enter`/`F9`/`c` launches it.
- Catalog startup and refresh now run in the background so the interface stays
  responsive, retains the last usable catalog on failure and reports busy or
  unavailable selections clearly.
- `Esc` now closes the current dialog or search, or resets pending choices to
  the active configuration; `q`/`F10` handles quitting and confirms when
  unapplied changes exist.

### Fixed

- Fixed provider authentication so `F7` always targets the pending provider
  and cancelling a credentials dialog leaves provider/model state untouched.
- Kept the current OpenAI account synchronized with CodexSwitch state and made
  account changes transactional with model-config rollback on activation error.
- Fixed Help and credential dialogs to stay centered and inside the supported
  `80x24` viewport, including visible button focus and keyboard-first Azure
  field validation.
- Fixed external model/account text containing Rich markup characters so it is
  displayed literally instead of being interpreted as styling.

### Added

- Added case-insensitive `/` model search across display names and full model
  IDs, with arrow-key result selection and Enter-to-Reasoning flow.
- Added a once-per-version Commander splash that remains accessible from Help.

## [0.9.0] - 2026-07-09

### Changed

- Updated the README storage section with a current vault flow table so the
  active auth files and encrypted CodexSwitch secrets are easier to scan.

### Fixed

- Fixed TUI `F5` so an OpenAI selection refreshes the native Codex model
  catalog instead of refreshing the OpenRouter catalog.
- Fixed `codexswitch tui` on Windows so it launches the Commander TUI instead
  of opening an interactive Python prompt.
- Fixed the OpenCode Go proxy so chats keep working after importing an API key
  into the encrypted CodexSwitch vault instead of expecting a plaintext
  `~/.config/codexswitch/opencode-go/auth.json`.
- Fixed TUI launch/apply drift detection after Codex `/model` changes the
  underlying `~/.codex/config.toml` without updating CodexSwitch state.
- Fixed repeated Codex reconnects when OpenCode Go rejects `deepseek-v4-pro`
  `xhigh` reasoning by retrying that upstream call with `medium` reasoning
  before emitting a failed response.
- Fixed OpenRouter short model aliases such as `glm-5.2` so they resolve to
  the full provider-qualified model id, for example `z-ai/glm-5.2`, before
  writing Codex config.

### Added

- Added `codexswitch proxy install|uninstall|status|restart` so the OpenCode
  Go proxy systemd service can be installed, inspected, restarted and removed
  independently from the main `install.sh` bootstrap flow.

### Changed

- `codexswitch`, `codexswitch tui` and `codexswitch status` now perform a
  startup update check and immediately run the existing GitHub upgrade flow
  when a newer release or `origin/main` revision is available and the local
  checkout is clean.

## [0.8.1] - 2026-07-01

### Added

- Added an encrypted CodexSwitch credential vault at
  `~/.config/codexswitch/vault.enc`.
- Added OS keyring support for the vault master key when available, with a
  restricted local key-file fallback for systems without a usable keyring.
- Added `codexswitch vault migrate` to encrypt legacy CodexSwitch secret JSON
  files and remove the migrated plaintext secret files.

### Changed

- OpenAI saved accounts, Azure credentials, OpenRouter keys and OpenCode Go
  keys are now stored through the encrypted vault instead of plaintext JSON
  files.
- OpenRouter and OpenCode Go token helpers now read from the encrypted vault.

## [0.8.0] - 2026-07-01

### Added

- Added a native Go `codexswitch` launcher that runs the existing Python
  Commander backend on Windows, Linux and macOS.
- Added GitHub release assets for Windows amd64, Linux amd64/arm64 and macOS
  amd64/arm64 launcher binaries, plus SHA256 checksums.
- Added cross-build helper scripts for local Go launcher builds.

### Changed

- Improved Windows compatibility for CodexSwitch path handling, subprocess
  output decoding and TUI Python discovery.

## [0.7.2] - 2026-07-01

### Added

- Added Azure OpenAI as a selectable provider in the CLI and Commander TUI.
- Added a CodexSwitch-owned Azure credential store at
  `~/.config/codexswitch/azure/auth.json` with `0600` secret file permissions.
- Added the fixed Azure model list with `gpt-5.5` as the only selectable model.

### Changed

- Azure activation now writes the active Codex provider config from the local
  secret store, keeping Azure credentials out of the repository.

## [0.7.1] - 2026-06-26

### Changed

- OpenRouter activation now writes a Codex-compatible model catalog from the
  OpenRouter cache and points Codex at it with `model_catalog_json`, preventing
  known models such as `qwen/qwen3.7-max` from falling back to generic metadata.
- `codexswitch update` now checks `origin/main` when the installed checkout is
  on `main`, so commits published after the latest GitHub release are no
  longer hidden behind an unchanged release tag.

## [0.7.0] - 2026-06-26

### Fixed

- OpenCode Go model metadata (reasoning variants and context limits) is now
  read correctly from the `~/.cache/opencode/models.json` cache.  The cache
  uses a `reasoning_options` schema rather than the `variants` dict emitted
  by `opencode --verbose`; both schemas are now normalized so reasoning
  choices and context windows reflect the real model capabilities instead of
  defaulting every model to `medium` and 128K context.
- The built-in OpenCode Go fallback catalog now carries real context limits
  and reasoning variants for known models, so a fresh host without the
  opencode binary still shows correct metadata.

### Changed

- `codexswitch refresh` and the TUI `F5` refresh now prefer the
  `opencode --verbose` output when the binary is available and fall back to
  the upstream `/models` endpoint merged with the built-in catalog.  This
  works on new hosts where opencode is not installed.
- The TUI now refreshes both OpenCode Go and OpenRouter model catalogs from
  internet sources at startup, so models, context limits and reasoning
  variants are always current.
- The `codexswitch classic` command and the classic interactive picker have
  been removed.  Use `codexswitch tui` for the interactive interface and
  `codexswitch use` / `codexswitch refresh` / `codexswitch auth` for
  non-interactive operations.
- The upstream `/models` endpoint is now merged with the fallback catalog so
  all known models appear even when the upstream omits them.

## [0.6.2] - 2026-06-26

### Changed

- The TUI now verifies Codex runtime directories before launching Codex, so
  root-owned session, log, temp or shell snapshot paths are repaired before
  they can trigger transcript save permission errors.
- TUI model details now show token limits consistently across OpenAI,
  OpenCode Go and OpenRouter catalogs, and no longer invent a `medium`
  reasoning choice for models that only expose provider defaults or
  model-managed reasoning.

## [0.6.1] - 2026-06-26

### Changed

- `install.sh` now checks an existing git checkout for updates before
  installing, runs a safe `git pull --ff-only`, fetches tags and restarts
  itself when the installer changed. This makes re-running `./install.sh` a
  normal update path on existing hosts.

## [0.6.0] - 2026-06-26

### Added

- Added a CodexSwitch-owned OpenCode Go secret store at
  `~/.config/codexswitch/opencode-go/auth.json`, matching the OpenRouter key
  flow and removing the hard dependency on the OpenCode CLI auth store.
- Added TUI paste/renew popups for OpenCode Go and OpenRouter API keys from
  the providers/accounts pane and `F7`.
- Added direct OpenCode Go model discovery through the OpenAI-compatible
  `/models` endpoint, plus CodexSwitch cache and built-in fallback models for
  fresh systems.
- Added installer dependency detection for common Linux package managers and
  automatic Codex CLI install/update handling.

### Changed

- OpenCode Go activation now requires the CodexSwitch OpenCode Go key store or
  a legacy OpenCode key fallback, and no longer starts `opencode auth login`.
- The OpenAI device sign-in popup now shows a clickable activation URL before
  handing over to the official Codex device-login flow.
- README installation/auth documentation now reflects OpenCode Go independence
  from OpenCode CLI.

## [0.5.18] - 2026-06-26

### Added

- Added `codexswitch update [--check]` to compare the local version with the
  latest GitHub release and update the local checkout/install when a newer
  release is available.

## [0.5.17] - 2026-06-26

### Changed

- Restyled TUI modal popups with a cyan Commander dialog, black normal text,
  bold white headings and no darkened screen overlay.
- Removed the separate dangling auth button from the OpenAI device sign-in
  popup; Enter now starts sign-in from inside the dialog flow.

## [0.5.16] - 2026-06-26

### Changed

- TUI status preview, apply result and status refresh now include the active
  Codex/OpenAI account when the OpenAI provider is selected.

## [0.5.15] - 2026-06-26

### Changed

- TUI keyboard flow now finishes from the reasoning pane: `Enter` on a selected
  reasoning mode applies the selection and starts Codex, matching `F9`.
- The TUI status bar previews the provider/model/reasoning that will be started
  before the final `Enter`.

## [0.5.14] - 2026-06-26

### Changed

- Aligned the TUI panes on a consistent Commander grid: the top provider pane
  and lower reasoning pane now share the same right-column width and vertical
  split, while status/function bars keep their intended Commander placement.

## [0.5.13] - 2026-06-26

### Fixed

- TUI OpenRouter apply no longer reports a stale `medium` reasoning suffix when
  the selected model does not persist a reasoning setting.
- Verified that every current OpenRouter catalog model can be applied through
  the config writer in an isolated temporary environment without inference
  calls, provider leakage or secret leakage.

### Changed

- Replaced the README TUI screenshot with a sanitized full-color Commander SVG
  so GitHub shows the intended blue/cyan/yellow interface.

## [0.5.12] - 2026-06-26

### Fixed

- OpenRouter models now show actual reasoning choices (supported_efforts) instead of
  always displaying "model-default". OpenRouter reasoning effort is now written to
  the Codex config when the model supports it.

### Added

- TUI function-key bar now supports mouse clicks (Midnight Commander style).
  Hover a key label to highlight it and click to trigger the action.


Releases through `1.8.0` followed pragmatic semantic versioning:

- Patch (`0.0.x`) for fixes and low-risk compatibility improvements.
- Minor (`0.x.0`) for new user-visible features or provider support.
- Major (`x.0.0`) for breaking command/config/auth behavior.

## [0.5.11] - 2026-06-26

### Changed

- TUI bottom status bar now starts with only `Ready` and no longer duplicates
  function-key hints already shown in the Commander key bar.

## [0.5.10] - 2026-06-26

### Changed

- Reworked the TUI function-key bar into ten equal-width Commander-style
  segments across the full terminal width.

## [0.5.9] - 2026-06-26

### Changed

- TUI startup splash now uses colored centered text below the ASCII logo.
- Removed the WAM-Software credit from the TUI bottom status bar because it is
  already visible in the header/splash/help.

## [0.5.8] - 2026-06-26

### Changed

- Centered the `C O M M A N D E R` subtitle under the CodexSwitch ASCII logo
  consistently in README, CLI help and TUI startup splash.

## [0.5.7] - 2026-06-26

### Changed

- Refined the CodexSwitch ASCII branding to a more compact draw-set logo in
  README, CLI help and TUI startup splash.

## [0.5.6] - 2026-06-26

### Changed

- Added CodexSwitch ASCII branding with `C O M M A N D E R` to the README and
  CLI help shown by plain `codexswitch`.
- TUI startup now shows a Commander-style splash popup with the ASCII branding,
  WAM-Software credit and AI-assisted implementation credit.

## [0.5.5] - 2026-06-26

### Changed

- CLI help and documentation now show `codexswitch version` as the primary
  version command.
- `codexswitch --version` remains available as a compatibility alias.
- Added release hygiene guidance to keep last-minute standalone changes in the
  changelog before tagging.

## [0.5.4] - 2026-06-26

### Changed

- TUI `F9` now launches Codex as
  `codex resume --dangerously-bypass-approvals-and-sandbox --search`.
- README documents the exact TUI Codex launch command.

## [0.5.3] - 2026-06-26

### Changed

- Added WAM-Software and AI-assisted implementation credits to the TUI subtitle,
  TUI status line, TUI help screen and classic startup banner.
- OpenAI authentication in the TUI now opens a device sign-in modal before
  temporarily suspending to `codex login --device-auth`, then verifies and saves
  the account after Codex completes login.
- `codexswitch --help` now shows the project credits.
- Running `codexswitch` without arguments now shows help; the TUI is started
  explicitly with `codexswitch tui`.

## [0.5.2] - 2026-06-26

### Changed

- Restored the product title to **CodexSwitch Commander** while keeping the
  `codexswitch` command lowercase.
- Reworked `--help` into a clearer app-style command overview.
- Polished classic mode with a searchable provider/model picker inspired by
  modern terminal model selectors.
- Rebuilt the README with a clearer quickstart, provider table, auth/storage
  overview and release documentation.

### Fixed

- Installer removes the temporary `openswitch` alias and points users back to
  `codexswitch`.
- `codexswitch refresh` now refreshes both OpenCode Go and OpenRouter catalogs.

## [0.5.1] - 2026-06-26

### Fixed

- OpenRouter models now show actual reasoning choices (supported_efforts) instead of
  always displaying "model-default". OpenRouter reasoning effort is now written to
  the Codex config when the model supports it.

### Added

- OpenRouter provider support with model catalog refresh from the OpenRouter
  models API.
- OpenRouter API-key storage via `codexswitch auth openrouter` and TUI `F7`.
- `openrouter-token` command helper so Codex reads the OpenRouter API key
  through command authentication instead of storing it in `config.toml`.
- OpenAI account add flow via device sign-in:
  - CLI/classic: `codexswitch account add`
  - TUI: `+ add OpenAI account` or `F7` while OpenAI is selected
- GitHub release workflow for tags named `v*`.

### Changed

- `codexswitch auth openai` now uses Codex device authentication.
- TUI provider/model isolation now covers OpenAI, OpenCode Go and OpenRouter.
- Installer now installs `openrouter-token`.
- Version is centralized and shown in CLI help, `--version`, classic mode and
  the TUI subtitle.

### Fixed

- Prevent stale OpenAI account state from leaking into OpenCode Go/OpenRouter
  selections.
- OpenCode Go proxy tool conversion now handles custom, function, namespace and
  proxy-local web-search flows more completely.
