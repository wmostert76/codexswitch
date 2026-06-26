# Changelog

All notable CodexSwitch changes are documented here.

Versioning follows pragmatic semantic versioning:

- Patch (`0.0.x`) for fixes and low-risk compatibility improvements.
- Minor (`0.x.0`) for new user-visible features or provider support.
- Major (`x.0.0`) for breaking command/config/auth behavior.

## [0.5.4] - 2026-06-26

### Changed

- TUI `F9` now launches Codex as
  `codex resume --dangerously-bypass-approvals-and-sandbox --search`.

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
