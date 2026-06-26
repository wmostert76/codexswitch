"""Tests for codexswitch backend pure functions."""
import base64
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"

# Load codexswitch as a module. It has no .py extension, so
# spec_from_file_location returns None unless we supply an explicit loader.
_loader = importlib.machinery.SourceFileLoader(
    "codexswitch", str(BIN_DIR / "codexswitch")
)
_spec = importlib.util.spec_from_file_location(
    "codexswitch", BIN_DIR / "codexswitch", loader=_loader
)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)


def test_version_constant_is_release_version():
    # Verify VERSION is a valid semver and matches CLI output
    import re
    assert re.match(r"^\d+\.\d+\.\d+$", cs.VERSION), f"Invalid version: {cs.VERSION}"
    proc = subprocess.run(
        [str(BIN_DIR / "codexswitch"), "version"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    assert proc.stdout.strip() == f"codexswitch {cs.VERSION}"
    assert cs.CREDITS_OWNER == "by WAM-Software since (c) 1988"
    assert cs.CREDITS_AI == "AI-assisted implementation: OpenAI Codex"
    assert r"/ __\___" in cs.ASCII_LOGO
    assert r"\____/\___/" in cs.ASCII_LOGO
    assert cs.COMMANDER_SPACED == "C O M M A N D E R"
    assert cs.COMMANDER_CENTERED == "                    C O M M A N D E R"
    assert cs.BRAND_BANNER == f"{cs.ASCII_LOGO}\n{cs.COMMANDER_CENTERED}"


def test_cli_version_output():
    proc = subprocess.run(
        [str(BIN_DIR / "codexswitch"), "version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout.strip() == f"codexswitch {cs.VERSION}"


def test_cli_dash_version_still_works_as_compatibility_alias():
    proc = subprocess.run(
        [str(BIN_DIR / "codexswitch"), "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout.strip() == f"codexswitch {cs.VERSION}"


def test_cli_help_contains_credits_and_tui_command():
    proc = subprocess.run(
        [str(BIN_DIR / "codexswitch"), "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert "by WAM-Software since (c) 1988" in proc.stdout
    assert "AI-assisted implementation: OpenAI Codex" in proc.stdout
    assert cs.BRAND_BANNER in proc.stdout
    assert "codexswitch tui" in proc.stdout
    assert "codexswitch update [--check]" in proc.stdout
    assert "codexswitch version" in proc.stdout
    assert "codexswitch --version" not in proc.stdout
    assert "codexswitch commander" not in proc.stdout


def test_cli_without_args_shows_help_not_tui():
    proc = subprocess.run(
        [str(BIN_DIR / "codexswitch")],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert "CodexSwitch Commander" in proc.stdout
    assert cs.BRAND_BANNER in proc.stdout
    assert "Usage:" in proc.stdout
    assert "codexswitch tui" in proc.stdout
    assert "codexswitch commander" not in proc.stdout


def test_ensure_codex_runtime_writable_creates_runtime_dirs(tmp_path, monkeypatch):
    home = tmp_path / "home"
    codex_home = home / ".codex"
    home.mkdir()
    monkeypatch.setattr(cs, "HOME", home)
    monkeypatch.setattr(cs, "CODEX_HOME", codex_home)

    cs.ensure_codex_runtime_writable()

    for name in ("sessions", "shell_snapshots", "tmp", "log"):
        path = codex_home / name
        assert path.is_dir()
        assert os.access(path, os.W_OK | os.X_OK)


def test_choose_filters_before_selecting(monkeypatch):
    answers = iter(["router", "1"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert cs.choose("Provider", ["openai", "opencode-go", "openrouter"]) == "openrouter"


def test_banner_contains_credits(capsys):
    cs.banner("Actief: test")
    output = capsys.readouterr().out
    assert "by WAM-Software since (c) 1988" in output
    assert "AI-assisted implementation: OpenAI Codex" in output


def test_parse_version_accepts_release_tags():
    assert cs.parse_version("0.6.0") == (0, 6, 0)
    assert cs.parse_version("v0.6.0") == (0, 6, 0)


def test_update_check_reports_newer_release(monkeypatch, capsys):
    monkeypatch.setattr(cs, "latest_github_release", lambda: ("v9.9.9", "https://example.test/release"))
    monkeypatch.setattr(cs, "main_branch_update_available", lambda: (False, "", ""))

    assert cs.update_from_github(check_only=True) is True

    output = capsys.readouterr().out
    assert f"{cs.VERSION} -> 9.9.9" in output
    assert "https://example.test/release" in output


def test_update_check_reports_up_to_date(monkeypatch, capsys):
    monkeypatch.setattr(cs, "latest_github_release", lambda: (f"v{cs.VERSION}", ""))
    monkeypatch.setattr(cs, "main_branch_update_available", lambda: (False, "", ""))

    assert cs.update_from_github(check_only=True) is False

    assert f"up-to-date: {cs.VERSION}" in capsys.readouterr().out


def test_update_check_reports_main_branch_update(monkeypatch, capsys):
    monkeypatch.setattr(
        cs,
        "latest_github_release",
        lambda: (f"v{cs.VERSION}", "https://example.test/release"),
    )
    monkeypatch.setattr(
        cs,
        "main_branch_update_available",
        lambda: (True, "1111111local", "2222222remote"),
    )

    assert cs.update_from_github(check_only=True) is True

    output = capsys.readouterr().out
    assert "Nieuwe CodexSwitch main-update beschikbaar: 1111111 -> 2222222" in output
    assert "latest release: https://example.test/release" in output


def test_update_refuses_dirty_repository(monkeypatch):
    import pytest

    monkeypatch.setattr(cs, "latest_github_release", lambda: ("v9.9.9", ""))
    monkeypatch.setattr(cs, "main_branch_update_available", lambda: (False, "", ""))
    monkeypatch.setattr(cs, "local_repo_is_dirty", lambda: True)

    with pytest.raises(SystemExit):
       cs.update_from_github(check_only=False)


# ─── JWT / auth helpers ───────────────────────────────────────────

def make_jwt(claims: dict) -> str:
    """Create a fake JWT with the given claims (no signature)."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.sig"


class TestJwtClaims:
    def test_valid_jwt(self):
        token = make_jwt({"email": "user@example.com"})
        claims = cs.jwt_claims(token)
        assert claims["email"] == "user@example.com"

    def test_invalid_token(self):
        assert cs.jwt_claims("not-a-jwt") == {}

    def test_empty_string(self):
        assert cs.jwt_claims("") == {}

    def test_non_string(self):
        assert cs.jwt_claims(None) == {}
        assert cs.jwt_claims(123) == {}

    def test_malformed_base64(self):
        assert cs.jwt_claims("a.b.c") == {}


class TestOpenaiAuthEmail:
    def test_email_from_id_token(self):
        data = {"tokens": {"id_token": make_jwt({"email": "User@Example.COM"})}}
        assert cs.openai_auth_email(data) == "user@example.com"

    def test_email_from_profile(self):
        token = make_jwt({"https://api.openai.com/profile": {"email": "test@example.org"}})
        data = {"tokens": {"id_token": token}}
        assert cs.openai_auth_email(data) == "test@example.org"

    def test_no_email(self):
        data = {"tokens": {"id_token": make_jwt({"sub": "123"})}}
        assert cs.openai_auth_email(data) is None

    def test_no_tokens(self):
        assert cs.openai_auth_email({}) is None

    def test_tokens_not_dict(self):
        assert cs.openai_auth_email({"tokens": "bad"}) is None

    def test_fallback_to_access_token(self):
        data = {
            "tokens": {
                "id_token": make_jwt({"sub": "123"}),
                "access_token": make_jwt({"email": "fallback@example.com"}),
            }
        }
        assert cs.openai_auth_email(data) == "fallback@example.com"


# ─── Account filename ─────────────────────────────────────────────

class TestAccountFilename:
    def test_valid_email(self):
        assert cs.account_filename("user@example.com") == "user@example.com.json"

    def test_uppercase_normalized(self):
        assert cs.account_filename("User@Example.COM") == "user@example.com.json"

    def test_invalid_email_rejected(self):
        import pytest
        with pytest.raises(SystemExit):
            cs.account_filename("not-an-email")

    def test_no_at_sign_rejected(self):
        import pytest
        with pytest.raises(SystemExit):
            cs.account_filename("bademail")


# ─── TOML manipulation ────────────────────────────────────────────

class TestRemoveBlock:
    def test_remove_existing_block(self):
        lines = [
            'key = "value"\n',
            '[section]\n',
            'foo = "bar"\n',
            '[other]\n',
            'baz = "qux"\n',
        ]
        result = cs.remove_block(lines, "section")
        assert not any("[section]" in l for l in result)
        assert any("[other]" in l for l in result)

    def test_remove_nonexistent_block(self):
        lines = ['key = "value"\n', '[other]\n', 'foo = "bar"\n']
        result = cs.remove_block(lines, "nonexistent")
        assert result == lines

    def test_remove_nested_block(self):
        lines = [
            '[model_providers.opencode-go]\n',
            'name = "test"\n',
            '[model_providers.opencode-go.auth]\n',
            'command = "x"\n',
            '[other]\n',
        ]
        result = cs.remove_block(lines, "model_providers.opencode-go.auth")
        assert not any(".auth]" in l for l in result)


class TestSetTopLevel:
    def test_set_new_key(self):
        lines = ['existing = "val"\n']
        result = cs.set_top_level(lines, "model", "gpt-5.5")
        assert any('model = "gpt-5.5"' in l for l in result)

    def test_replace_existing_key(self):
        lines = ['model = "old"\n', '[section]\n', 'foo = "bar"\n']
        result = cs.set_top_level(lines, "model", "new")
        assert any('model = "new"' in l for l in result)
        assert not any('model = "old"' in l for l in result)
        assert any("[section]" in l for l in result)

    def test_set_before_first_section(self):
        lines = ['[section]\n', 'foo = "bar"\n']
        result = cs.set_top_level(lines, "model", "gpt-5.5")
        assert result[0].strip() == 'model = "gpt-5.5"'

    def test_empty_lines(self):
        result = cs.set_top_level([], "model", "gpt-5.5")
        assert any('model = "gpt-5.5"' in l for l in result)


# ─── JSON helpers ─────────────────────────────────────────────────

class TestReadJson:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"key": "value"}')
        assert cs.read_json(f, {}) == {"key": "value"}

    def test_missing_file(self, tmp_path):
        assert cs.read_json(tmp_path / "nonexistent.json", "default") == "default"

    def test_invalid_json(self, tmp_path):
        import pytest
        f = tmp_path / "bad.json"
        f.write_text("not json")
        with pytest.raises(SystemExit):
            cs.read_json(f, {})


# ─── Reasoning choices ────────────────────────────────────────────

class TestReasoningChoices:
    def test_none_thinking_variants(self):
        with patch.object(cs, "opencode_model_catalog") as mock:
            mock.return_value = {
                "model-x": {"variants": {"none": {}, "thinking": {}}}
            }
            choices = cs.reasoning_choices("model-x")
            assert ("thinking", "high") in choices
            assert ("none", "none") in choices

    def test_standard_variants(self):
        with patch.object(cs, "opencode_model_catalog") as mock:
            mock.return_value = {
                "model-y": {"variants": {"low": {}, "medium": {}, "high": {}}}
            }
            choices = cs.reasoning_choices("model-y")
            efforts = [effort for _, effort in choices]
            assert "low" in efforts
            assert "medium" in efforts
            assert "high" in efforts

    def test_max_mapped_to_xhigh(self):
        with patch.object(cs, "opencode_model_catalog") as mock:
            mock.return_value = {
                "model-z": {"variants": {"medium": {}, "max": {}}}
            }
            choices = cs.reasoning_choices("model-z")
            efforts = [effort for _, effort in choices]
            assert "xhigh" in efforts

    def test_no_variants(self):
        with patch.object(cs, "opencode_model_catalog") as mock:
            mock.return_value = {"model-w": {}}
            assert cs.reasoning_choices("model-w") == []


class TestDefaultReasoningEffort:
    def test_prefers_medium(self):
        with patch.object(cs, "reasoning_choices") as mock:
            mock.return_value = [("low", "low"), ("medium", "medium"), ("high", "high")]
            assert cs.default_reasoning_effort("any") == "medium"

    def test_falls_back_to_high(self):
        with patch.object(cs, "reasoning_choices") as mock:
            mock.return_value = [("high", "high"), ("xhigh", "xhigh")]
            assert cs.default_reasoning_effort("any") == "high"

    def test_empty_choices(self):
        with patch.object(cs, "reasoning_choices") as mock:
            mock.return_value = []
            assert cs.default_reasoning_effort("any") == "medium"


# ─── Backup cleanup ───────────────────────────────────────────────

class TestCleanupConfigBackups:
    def test_removes_old_backups(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs, "CODEX_HOME", tmp_path)
        monkeypatch.setattr(cs, "MAX_CONFIG_BACKUPS", 3)
        for i in range(5):
            (tmp_path / f"config.toml.bak-2025010{i}-000000000-000000000{i}").write_text("old")
        cs.cleanup_config_backups()
        remaining = list(tmp_path.glob("config.toml.bak-*"))
        assert len(remaining) == 3

    def test_no_backups(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs, "CODEX_HOME", tmp_path)
        cs.cleanup_config_backups()
        assert len(list(tmp_path.glob("config.toml.bak-*"))) == 0

    def test_keeps_most_recent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs, "CODEX_HOME", tmp_path)
        monkeypatch.setattr(cs, "MAX_CONFIG_BACKUPS", 2)
        names = [
            "config.toml.bak-20250101-000000000-000000001",
            "config.toml.bak-20250102-000000000-000000002",
            "config.toml.bak-20250103-000000000-000000003",
        ]
        for n in names:
            (tmp_path / n).write_text("old")
        cs.cleanup_config_backups()
        remaining = sorted(p.name for p in tmp_path.glob("config.toml.bak-*"))
        assert remaining == [names[1], names[2]]


# ─── Remove top-level key ─────────────────────────────────────────


# ─── Remove top-level key ─────────────────────────────────────────

class TestRemoveTopLevel:
    def test_remove_existing_key(self):
        lines = [
            'model = "old"\n',
            'model_reasoning_effort = "high"\n',
            '[section]\n',
            'foo = "bar"\n',
        ]
        result = cs.remove_top_level(lines, 'model_reasoning_effort')
        assert not any('model_reasoning_effort' in l for l in result)
        assert any('model = "old"' in l for l in result)
        assert any('[section]' in l for l in result)

    def test_remove_nonexistent_key(self):
        lines = ['model = "old"\n', '[section]\n', 'foo = "bar"\n']
        result = cs.remove_top_level(lines, 'nonexistent')
        assert result == lines

    def test_does_not_remove_key_inside_section(self):
        lines = [
            '[section]\n',
            'model_reasoning_effort = "high"\n',
        ]
        result = cs.remove_top_level(lines, 'model_reasoning_effort')
        assert any('model_reasoning_effort' in l for l in result)

    def test_empty_lines(self):
        assert cs.remove_top_level([], 'model') == []


class TestAccountSwitchSafety:
    def test_refuses_to_replace_unidentifiable_active_auth(self, tmp_path, monkeypatch):
        import pytest

        codex_home = tmp_path / ".codex"
        switch_home = tmp_path / ".config" / "codexswitch"
        accounts = switch_home / "openai-accounts"
        codex_home.mkdir(parents=True)
        accounts.mkdir(parents=True)
        (codex_home / "auth.json").write_text(
            json.dumps({"tokens": {"access_token": "opaque-active-token"}})
        )
        saved = {"tokens": {"id_token": make_jwt({"email": "saved@example.com"})}}
        (accounts / "saved@example.com.json").write_text(json.dumps(saved))

        monkeypatch.setattr(cs, "HOME", tmp_path)
        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
        monkeypatch.setattr(cs, "SWITCH_CONFIG", switch_home / "config.json")
        monkeypatch.setattr(cs, "OPENAI_ACCOUNTS_DIR", accounts)

        with pytest.raises(SystemExit):
            cs.use_openai_account("saved@example.com")
        assert json.loads((codex_home / "auth.json").read_text()) != saved

    def test_auth_login_refuses_unidentifiable_active_auth(self, tmp_path, monkeypatch):
        import pytest

        codex_home = tmp_path / ".codex"
        codex_home.mkdir(parents=True)
        (codex_home / "auth.json").write_text(
            json.dumps({"tokens": {"access_token": "opaque-active-token"}})
        )
        monkeypatch.setattr(cs, "HOME", tmp_path)
        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "OPENAI_ACCOUNTS_DIR", tmp_path / "accounts")
        monkeypatch.setattr(cs, "run", lambda *args, **kwargs: pytest.fail("login ran"))

        with pytest.raises(SystemExit):
            cs.auth("openai")


class TestUpdateState:
    def test_openai_without_effort_clears_saved_reasoning(self, tmp_path, monkeypatch):
        codex_home = tmp_path / ".codex"
        switch_home = tmp_path / ".config" / "codexswitch"
        codex_home.mkdir(parents=True)
        switch_home.mkdir(parents=True)
        config = codex_home / "config.toml"
        state_path = switch_home / "config.json"
        config.write_text(
            'model = "old"\n'
            'model_provider = "opencode-go"\n'
            'model_reasoning_effort = "high"\n'
        )
        state_path.write_text(
            json.dumps(
                {
                    "provider": "opencode-go",
                    "model": "old",
                    "reasoning_effort": "high",
                    "openai_account": "saved@example.com",
                }
            )
        )
        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "CODEX_CONFIG", config)
        monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
        monkeypatch.setattr(cs, "SWITCH_CONFIG", state_path)
        monkeypatch.setattr(cs, "openai_reasoning_choices", lambda model: [])

        cs.update_codex_config("openai", "gpt-test")
        state = json.loads(state_path.read_text())
        assert "reasoning_effort" not in state
        assert "model_reasoning_effort" not in config.read_text()

    def test_opencode_clears_saved_openai_account(self, tmp_path, monkeypatch):
        codex_home = tmp_path / ".codex"
        switch_home = tmp_path / ".config" / "codexswitch"
        codex_home.mkdir(parents=True)
        switch_home.mkdir(parents=True)
        config = codex_home / "config.toml"
        state_path = switch_home / "config.json"
        config.write_text("")
        state_path.write_text(json.dumps({"openai_account": "saved@example.com"}))
        token_helper = tmp_path / "token-helper"
        token_helper.write_text("")

        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "CODEX_CONFIG", config)
        monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
        monkeypatch.setattr(cs, "SWITCH_CONFIG", state_path)
        monkeypatch.setattr(cs, "TOKEN_HELPER", str(token_helper))
        monkeypatch.setattr(cs, "ensure_proxy", lambda: None)
        monkeypatch.setattr(cs, "opencode_go_key_present", lambda: True)
        monkeypatch.setattr(cs, "reasoning_choices", lambda model: [("medium", "medium")])
        monkeypatch.setattr(cs, "warm_codex_model_catalog", lambda: True)

        cs.update_codex_config("opencode-go", "model-x", "medium")
        state = json.loads(state_path.read_text())
        assert "openai_account" not in state

    def test_openrouter_requires_api_key(self, tmp_path, monkeypatch):
        import pytest

        codex_home = tmp_path / ".codex"
        switch_home = tmp_path / ".config" / "codexswitch"
        codex_home.mkdir(parents=True)
        switch_home.mkdir(parents=True)
        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "CODEX_CONFIG", codex_home / "config.toml")
        monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
        monkeypatch.setattr(cs, "SWITCH_CONFIG", switch_home / "config.json")
        monkeypatch.setattr(cs, "OPENROUTER_AUTH", switch_home / "openrouter/auth.json")

        with pytest.raises(SystemExit):
            cs.update_codex_config("openrouter", "openrouter/auto")

    def test_openrouter_config_uses_secret_helper_and_clears_openai_state(self, tmp_path, monkeypatch):
        codex_home = tmp_path / ".codex"
        switch_home = tmp_path / ".config" / "codexswitch"
        codex_home.mkdir(parents=True)
        switch_home.mkdir(parents=True)
        config = codex_home / "config.toml"
        state_path = switch_home / "config.json"
        config.write_text(
            'model = "old"\n'
            'model_provider = "openai"\n'
            'model_reasoning_effort = "high"\n'
        )
        state_path.write_text(
            json.dumps(
                {
                    "provider": "openai",
                    "model": "old",
                    "reasoning_effort": "high",
                    "openai_account": "saved@example.com",
                }
            )
        )
        token_helper = tmp_path / "openrouter-token"
        token_helper.write_text("")

        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "CODEX_CONFIG", config)
        monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
        monkeypatch.setattr(cs, "SWITCH_CONFIG", state_path)
        monkeypatch.setattr(cs, "OPENROUTER_TOKEN_HELPER", str(token_helper))
        monkeypatch.setattr(cs, "openrouter_key_present", lambda: True)
        monkeypatch.setattr(cs, "warm_codex_model_catalog", lambda: True)

        cs.update_codex_config("openrouter", "anthropic/claude-test", "medium")
        text = config.read_text()
        state = json.loads(state_path.read_text())
        assert 'model_provider = "openrouter"' in text
        assert 'base_url = "https://openrouter.ai/api/v1"' in text
        assert f'command = "{token_helper}"' in text
        assert "model_reasoning_effort" not in text
        assert "openai_account" not in state
        assert "reasoning_effort" not in state

    def test_openrouter_all_catalog_models_can_apply_without_secret_or_provider_leak(self, tmp_path, monkeypatch):
        codex_home = tmp_path / ".codex"
        switch_home = tmp_path / ".config" / "codexswitch"
        codex_home.mkdir(parents=True)
        switch_home.mkdir(parents=True)
        config = codex_home / "config.toml"
        state_path = switch_home / "config.json"
        token_helper = tmp_path / "openrouter-token"
        token_helper.write_text("")

        catalog = {
            "vendor/model-a": {"id": "vendor/model-a"},
            "vendor/model-b:free": {"id": "vendor/model-b:free"},
            "~vendor/latest": {"id": "~vendor/latest"},
        }

        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "CODEX_CONFIG", config)
        monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
        monkeypatch.setattr(cs, "SWITCH_CONFIG", state_path)
        monkeypatch.setattr(cs, "OPENROUTER_TOKEN_HELPER", str(token_helper))
        monkeypatch.setattr(cs, "openrouter_key_present", lambda: True)
        monkeypatch.setattr(cs, "openrouter_model_catalog", lambda refresh=False: catalog)
        monkeypatch.setattr(cs, "warm_codex_model_catalog", lambda: True)

        for model in cs.openrouter_models():
            cs.validate_provider_model("openrouter", model)
            cs.update_codex_config("openrouter", model, cs.default_reasoning_effort(model))
            text = config.read_text()
            assert f'model = "{model}"' in text
            assert 'model_provider = "openrouter"' in text
            assert "[model_providers.openrouter]" in text
            assert "[model_providers.opencode-go]" not in text
            assert "api_key" not in text


class TestOpenRouterCatalog:
    def test_openrouter_models_from_catalog(self, monkeypatch):
        monkeypatch.setattr(
            cs,
            "openrouter_model_catalog",
            lambda refresh=False: {
                "z/model": {"id": "z/model"},
                "a/model": {"id": "a/model"},
            },
        )
        assert cs.openrouter_models() == ["a/model", "z/model"]

    def test_openrouter_models_fallback(self, monkeypatch):
        monkeypatch.setattr(cs, "openrouter_model_catalog", lambda refresh=False: {})
        assert cs.openrouter_models() == cs.OPENROUTER_FALLBACK_MODELS

    def test_save_openrouter_key_is_secret_file(self, tmp_path, monkeypatch):
        auth_path = tmp_path / "openrouter" / "auth.json"
        monkeypatch.setattr(cs, "OPENROUTER_AUTH", auth_path)
        cs.save_openrouter_key(" test-openrouter-key-not-secret ")
        assert json.loads(auth_path.read_text()) == {"api_key": "test-openrouter-key-not-secret"}
        assert oct(auth_path.stat().st_mode & 0o777) == "0o600"
        assert oct(auth_path.parent.stat().st_mode & 0o777) == "0o700"


class TestOpenCodeGoStore:
    def test_save_opencode_go_key_is_secret_file(self, tmp_path, monkeypatch):
        auth_path = tmp_path / "opencode-go" / "auth.json"
        monkeypatch.setattr(cs, "OPENCODE_GO_AUTH", auth_path)

        cs.save_opencode_go_key(" test-opencode-go-key-not-secret ")

        assert json.loads(auth_path.read_text()) == {
            "api_key": "test-opencode-go-key-not-secret"
        }
        assert oct(auth_path.stat().st_mode & 0o777) == "0o600"
        assert oct(auth_path.parent.stat().st_mode & 0o777) == "0o700"

    def test_opencode_key_present_prefers_switch_store_and_falls_back_to_legacy(
        self, tmp_path, monkeypatch
    ):
        switch_auth = tmp_path / "switch" / "auth.json"
        legacy_auth = tmp_path / "legacy" / "auth.json"
        monkeypatch.setattr(cs, "OPENCODE_GO_AUTH", switch_auth)
        monkeypatch.setattr(cs, "OPENCODE_AUTH", legacy_auth)

        assert cs.opencode_go_key_present() is False
        legacy_auth.parent.mkdir(parents=True)
        legacy_auth.write_text(json.dumps({"opencode-go": {"key": "legacy"}}))
        assert cs.opencode_go_key_present() is True
        cs.save_opencode_go_key("native")
        assert cs.opencode_go_key_present() is True

    def test_opencode_catalog_uses_switch_cache_before_legacy_or_cli(
        self, tmp_path, monkeypatch
    ):
        cache = tmp_path / "opencode-go" / "models.json"
        cache.parent.mkdir(parents=True)
        cache.write_text(
            json.dumps(
                {
                    "models": {
                        "switch-model": {
                            "name": "Switch Model",
                            "variants": {"medium": {}},
                        }
                    }
                }
            )
        )

        monkeypatch.setattr(cs, "OPENCODE_GO_MODELS_CACHE", cache)
        monkeypatch.setattr(cs, "_OPENCODE_CATALOG_CACHE", None)
        monkeypatch.setattr(cs, "_common_catalog_from_upstream", lambda base_url: {})
        monkeypatch.setattr(cs, "_common_catalog_from_binary", lambda: {})
        monkeypatch.setattr(cs, "OPENCODE_MODELS_CACHE", tmp_path / "missing.json")

        assert cs.opencode_models() == ["switch-model"]

    def test_opencode_catalog_has_builtin_fallback_without_opencode_cli(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(cs, "OPENCODE_GO_MODELS_CACHE", tmp_path / "missing.json")
        monkeypatch.setattr(cs, "_OPENCODE_CATALOG_CACHE", None)
        monkeypatch.setattr(cs, "_common_catalog_from_upstream", lambda base_url: {})
        monkeypatch.setattr(cs, "_common_catalog_from_binary", lambda: {})
        monkeypatch.setattr(cs, "_common_catalog_from_cache", lambda path: {})

        assert "kimi-k2.6" in cs.opencode_models()
