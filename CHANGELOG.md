# Changelog

All notable CodexSwitch changes are documented here.

## [0.5.12] - 2026-06-26

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
