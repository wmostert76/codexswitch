# Contributing

Contributions are welcome.

1. Create a feature branch.
2. Keep provider and authentication logic in `bin/codexswitch`.
3. Keep the TUI as a client of that backend logic.
4. Run the checks listed in `AGENTS.md`.
5. Do not include real credentials, account names or local absolute paths.

Create the development environment with:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

The CI suite validates Python 3.11 through 3.13 and separately formats,
race-tests, vets and builds the active Go proxy.

Bug reports should include the Codex CLI version, OpenCode version, terminal
type and the output of `codexswitch status` with personal details removed.
