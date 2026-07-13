# Changelog

All notable CodexSwitch changes are documented here.

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


Versioning follows pragmatic semantic versioning:

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
