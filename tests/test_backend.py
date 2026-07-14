"""Tests for codexswitch backend pure functions."""
import base64
import json
import os
import tempfile
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"

import codexswitch_backend as cs


def test_version_constant_is_release_version():
    # Verify VERSION is a valid semver and matches CLI output
    import re
    assert re.match(r"^\d+\.\d+\.\d+$", cs.VERSION), f"Invalid version: {cs.VERSION}"
    proc = subprocess.run(
        [sys.executable, str(BIN_DIR / "codexswitch"), "version"],
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
        [sys.executable, str(BIN_DIR / "codexswitch"), "version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout.strip() == f"codexswitch {cs.VERSION}"


def test_cli_dash_version_still_works_as_compatibility_alias():
    proc = subprocess.run(
        [sys.executable, str(BIN_DIR / "codexswitch"), "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert proc.stdout.strip() == f"codexswitch {cs.VERSION}"


def test_openrouter_codex_compatibility_matrix_covers_all_tested_free_models():
    statuses = cs.OPENROUTER_CODEX_COMPATIBILITY
    assert cs.OPENROUTER_CODEX_COMPATIBILITY_TESTED_AT == "2026-07-14"
    assert len(statuses) == 23
    assert set(statuses.values()) == {
        "limited",
        "tool-failed",
        "rate-limited",
        "unsupported",
    }
    assert sum(status == "limited" for status in statuses.values()) == 11
    assert sum(status == "tool-failed" for status in statuses.values()) == 2
    assert sum(status == "rate-limited" for status in statuses.values()) == 4
    assert sum(status == "unsupported" for status in statuses.values()) == 6
    assert set(statuses.values()) == set(
        cs.OPENROUTER_CODEX_COMPATIBILITY_DESCRIPTIONS
    )
    assert cs.openrouter_codex_compatibility("qwen/qwen3-coder:free") == (
        "~",
        "rate-limited",
        "free endpoint was rate-limited in both test runs",
    )
    assert cs.openrouter_codex_compatibility("vendor/untested") == ("", "", "")


def test_cli_model_list_marks_measured_openrouter_compatibility(monkeypatch, capsys):
    monkeypatch.setattr(cs, "openai_models", lambda: [])
    monkeypatch.setattr(cs, "azure_models", lambda: [])
    monkeypatch.setattr(cs, "opencode_models", lambda: [])
    monkeypatch.setattr(
        cs,
        "openrouter_models",
        lambda: ["qwen/qwen3-coder:free", "vendor/untested"],
    )

    cs.list_models()

    output = capsys.readouterr().out
    assert "~ qwen/qwen3-coder:free — free endpoint was rate-limited" in output
    assert "    vendor/untested" in output
    assert "C: ! basic shell only · x failed/unavailable tooling" in output


def test_cli_help_contains_credits_and_tui_command():
    proc = subprocess.run(
        [sys.executable, str(BIN_DIR / "codexswitch"), "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert "by WAM-Software since (c) 1988" in proc.stdout
    assert "AI-assisted implementation: OpenAI Codex" in proc.stdout
    assert cs.BRAND_BANNER in proc.stdout
    assert "codexswitch tui" in proc.stdout
    assert "codexswitch proxy install" in proc.stdout
    assert "codexswitch proxy uninstall" in proc.stdout
    assert "codexswitch update [--check]" in proc.stdout
    assert "codexswitch version" in proc.stdout
    assert "codexswitch --version" not in proc.stdout
    assert "codexswitch commander" not in proc.stdout


def test_azure_model_and_reasoning_levels_are_current():
    assert cs.AZURE_MODEL == "gpt-5.6-sol"
    assert cs.azure_models() == ["gpt-5.6-sol"]
    assert cs.AZURE_DEFAULT_REASONING_EFFORT == "low"
    assert cs.azure_reasoning_choices(cs.AZURE_MODEL) == [
        ("Low (default)", "low"),
        ("Medium", "medium"),
        ("High", "high"),
        ("Extra high", "xhigh"),
        ("Max", "max"),
        ("Ultra", "ultra"),
    ]


def test_azure_rejects_retired_gpt_5_5():
    import pytest

    with pytest.raises(SystemExit):
        cs.validate_provider_model("azure", "gpt-5.5")


def test_azure_endpoint_is_normalized_to_responses_v1():
    assert cs.normalize_azure_endpoint("https://example.invalid") == (
        "https://example.invalid/openai/v1"
    )
    assert cs.normalize_azure_endpoint("https://example.invalid/openai/") == (
        "https://example.invalid/openai/v1"
    )
    assert cs.normalize_azure_endpoint(
        "https://example.invalid/openai/v1/"
    ) == "https://example.invalid/openai/v1"
    assert cs.normalize_azure_endpoint(
        "https://example.invalid/openai/v1/responses"
    ) == "https://example.invalid/openai/v1"


def test_cli_without_args_shows_help_not_tui():
    proc = subprocess.run(
        [sys.executable, str(BIN_DIR / "codexswitch")],
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


def test_remote_vault_configure_wizard_uploads_then_removes_local_material(
    tmp_path, monkeypatch, capsys
):
    calls = []
    answers = iter(["", ""])
    secrets = iter(
        [
            "fixture-access",
            "fixture-s3-secret",
            "fixture-shared-passphrase-long",
            "fixture-shared-passphrase-long",
        ]
    )
    monkeypatch.setattr(cs, "SWITCH_HOME", tmp_path)
    monkeypatch.setattr(cs, "remote_vault_enabled", lambda home: False)
    monkeypatch.setattr(cs, "migrate_vault", lambda: calls.append(("migrate",)))
    monkeypatch.setattr(cs, "vault_load", lambda home: {"saved": {"value": 1}})
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(cs.getpass, "getpass", lambda prompt="": next(secrets))
    monkeypatch.setattr(
        cs,
        "store_remote_credentials",
        lambda access, secret, passphrase: calls.append(
            ("credentials", access, secret, passphrase)
        ),
    )
    monkeypatch.setattr(
        cs,
        "write_remote_vault_config",
        lambda config, home: calls.append(("config", config, home)),
    )
    monkeypatch.setattr(cs, "remote_vault_request", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cs, "vault_save", lambda data, home: calls.append(("upload", data, home))
    )
    monkeypatch.setattr(
        cs,
        "vault_status",
        lambda: {"mode": "remote", "online": True, "label": "ONLINE"},
    )
    monkeypatch.setattr(
        cs,
        "remove_local_vault_material",
        lambda home: calls.append(("remove-local", home)),
    )

    cs.configure_remote_vault()

    assert any(call[0] == "upload" for call in calls)
    assert ("remove-local", tmp_path) in calls
    assert "ONLINE" in capsys.readouterr().out


def test_status_shows_reasoning_effort(tmp_path, monkeypatch, capsys):
    codex_home = tmp_path / ".codex"
    switch_home = tmp_path / ".config" / "codexswitch"
    codex_home.mkdir(parents=True)
    switch_home.mkdir(parents=True)
    switch_config = switch_home / "config.json"
    switch_config.write_text(
        json.dumps(
            {
                "provider": "openrouter",
                "model": "z-ai/glm-5.2",
                "reasoning_effort": "high",
            }
        )
    )

    monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
    monkeypatch.setattr(cs, "CODEX_CONFIG", codex_home / "config.toml")
    monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
    monkeypatch.setattr(cs, "SWITCH_CONFIG", switch_config)
    cache_calls = []
    monkeypatch.setattr(
        cs, "enable_vault_session_cache", lambda home: cache_calls.append(home)
    )
    monkeypatch.setattr(cs, "codex_bin", lambda: "/tmp/codex")
    monkeypatch.setattr(cs, "_common_opencode_bin", lambda: None)
    monkeypatch.setattr(cs, "opencode_go_key_present", lambda: True)
    monkeypatch.setattr(cs, "azure_credentials_present", lambda: True)
    monkeypatch.setattr(cs, "openrouter_key_present", lambda: True)
    monkeypatch.setattr(cs, "codex_usage_summary", lambda data: [])

    cs.status()

    assert cache_calls == [switch_home]
    assert "huidig:       openrouter / z-ai/glm-5.2 / denken=high" in capsys.readouterr().out


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


def test_auto_update_is_quiet_when_current(monkeypatch, capsys):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(cs, "latest_github_release", lambda: (f"v{cs.VERSION}", ""))
    monkeypatch.setattr(cs, "main_branch_update_available", lambda: (False, "", ""))

    assert cs.auto_update_from_github() is False

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_auto_update_skips_dirty_checkout(monkeypatch, capsys):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(cs, "latest_github_release", lambda: ("v9.9.9", ""))
    monkeypatch.setattr(cs, "main_branch_update_available", lambda: (False, "", ""))
    monkeypatch.setattr(cs, "local_repo_is_dirty", lambda: True)

    assert cs.auto_update_from_github() is False

    assert "upgrade overgeslagen" in capsys.readouterr().err


def test_auto_update_main_branch_runs_install_without_self_update(monkeypatch):
    calls = []
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(cs, "latest_github_release", lambda: (f"v{cs.VERSION}", ""))
    monkeypatch.setattr(
        cs,
        "main_branch_update_available",
        lambda: (True, "1111111local", "2222222remote"),
    )
    monkeypatch.setattr(cs, "local_repo_is_dirty", lambda: False)
    monkeypatch.setattr(cs, "run", lambda cmd, check=True: calls.append((cmd, check)))
    monkeypatch.setattr(
        cs,
        "run_post_update_install",
        lambda skip_self_update=False: calls.append(
            (["post-update-install", skip_self_update], True)
        ),
    )

    assert cs.auto_update_from_github() is True

    assert (
        [
            "git",
            "-C",
            str(cs.PROJECT_ROOT),
            "pull",
            "--no-tags",
            "--ff-only",
            "origin",
            "main",
        ],
        True,
    ) in calls
    assert (["post-update-install", True], True) in calls


def test_release_update_fetches_only_latest_tag(monkeypatch):
    calls = []
    monkeypatch.setattr(cs, "latest_github_release", lambda: ("v9.9.9", ""))
    monkeypatch.setattr(cs, "local_repo_is_dirty", lambda: False)
    monkeypatch.setattr(cs, "current_git_branch", lambda: "release-checkout")
    monkeypatch.setattr(cs, "run", lambda cmd, check=True: calls.append(cmd))
    monkeypatch.setattr(cs, "run_post_update_install", lambda: calls.append(["install"]))

    assert cs.update_from_github() is True

    assert [
        "git",
        "-C",
        str(cs.PROJECT_ROOT),
        "fetch",
        "--no-tags",
        "origin",
        "refs/tags/v9.9.9:refs/tags/v9.9.9",
    ] in calls
    assert ["git", "-C", str(cs.PROJECT_ROOT), "checkout", "v9.9.9"] in calls
    assert not any("--tags" in call for call in calls)


def test_post_update_install_uses_native_python_on_windows(monkeypatch):
    calls = []
    monkeypatch.setattr(cs.os, "name", "nt")
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(cs, "run", lambda cmd, check=True: calls.append(cmd))

    cs.run_post_update_install(skip_self_update=True)

    assert calls == [
        [
            cs.sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(cs.PROJECT_ROOT / "requirements.txt"),
        ]
    ]


def test_post_update_install_uses_shell_installer_off_windows(monkeypatch):
    calls = []
    monkeypatch.setattr(cs.os, "name", "posix")
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(cs, "run", lambda cmd, check=True: calls.append(cmd))

    cs.run_post_update_install(skip_self_update=True)

    assert calls == [
        [
            "bash",
            str(cs.PROJECT_ROOT / "install.sh"),
            "--no-self-update",
        ]
    ]


def test_proxy_service_unit_uses_proxy_binary_and_current_user(tmp_path, monkeypatch):
    proxy_bin = tmp_path / "codex-provider-proxy"
    proxy_bin.write_text("")
    monkeypatch.setattr(cs, "PROXY_BIN", str(proxy_bin))
    monkeypatch.setattr(cs.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(cs, "command_output", lambda cmd: {
        ("id", "-un"): "tester",
        ("id", "-gn", "tester"): "testers",
        ("getent", "passwd", "tester"): "tester:x:1000:1000::/home/tester:/bin/bash",
    }[tuple(cmd)])

    unit = cs.proxy_service_unit()

    assert "User=tester" in unit
    assert "Group=testers" in unit
    assert "Environment=HOME=/home/tester" in unit
    assert f"ExecStart={proxy_bin.resolve()}" in unit


def test_install_proxy_service_installs_and_restarts_unit(monkeypatch):
    calls = []
    monkeypatch.setattr(cs, "require_proxy_service_support", lambda: None)
    monkeypatch.setattr(cs, "proxy_service_unit", lambda: "[Unit]\n")
    monkeypatch.setattr(cs, "privileged_cmd", lambda cmd: ["sudo", *cmd])
    monkeypatch.setattr(cs, "run", lambda cmd, check=True: calls.append((cmd, check)))

    cs.install_proxy_service()

    assert calls[0][0][:4] == ["sudo", "install", "-m", "644"]
    assert calls[0][0][-1] == "/etc/systemd/system/codex-provider-proxy.service"
    assert (["sudo", "systemctl", "daemon-reload"], True) in calls
    assert (["sudo", "systemctl", "enable", "--now", cs.PROXY_SERVICE], True) in calls
    assert (["sudo", "systemctl", "restart", cs.PROXY_SERVICE], True) in calls


def test_ensure_provider_proxy_starts_unified_proxy_only_when_required(
    tmp_path, monkeypatch
):
    proxy_bin = tmp_path / "codex-provider-proxy"
    proxy_bin.write_text("")
    health = iter([False, True])
    calls = []
    monkeypatch.setattr(cs, "PROXY_BIN", str(proxy_bin))
    monkeypatch.setattr(cs, "SWITCH_HOME", tmp_path / "switch")
    monkeypatch.setattr(cs, "CODEX_CONFIG", tmp_path / "missing-config.toml")
    monkeypatch.setattr(cs, "proxy_healthy", lambda: next(health))
    monkeypatch.setattr(cs.shutil, "which", lambda command: None)
    monkeypatch.setattr(cs.subprocess, "Popen", lambda argv, **kwargs: calls.append(argv))
    monkeypatch.setattr(cs.time, "sleep", lambda _seconds: None)

    cs.ensure_provider_proxy("openai")
    cs.ensure_provider_proxy("azure")

    expected = (
        [cs.sys.executable, str(proxy_bin)]
        if cs.os.name == "nt"
        else [str(proxy_bin)]
    )
    assert calls == [expected]


def test_ensure_provider_proxy_migrates_legacy_active_base_url(
    tmp_path, monkeypatch
):
    config = tmp_path / "config.toml"
    config.write_text(
        'model = "gpt-5.6-sol"\n'
        'model_provider = "azure"\n'
        'model_reasoning_effort = "medium"\n'
        '[model_providers.azure]\n'
        'base_url = "http://127.0.0.1:14557/v1"\n'
    )
    calls = []
    monkeypatch.setattr(cs, "CODEX_CONFIG", config)
    monkeypatch.setattr(cs, "update_codex_config", lambda *args: calls.append(args))
    monkeypatch.setattr(cs, "proxy_healthy", lambda: True)

    cs.ensure_provider_proxy("azure")

    assert calls == [("azure", "gpt-5.6-sol", "medium")]


def test_proxy_statuses_reports_unified_health(monkeypatch):
    monkeypatch.setattr(cs, "proxy_healthy", lambda: True)
    assert cs.proxy_statuses() == {"unified": True}


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


class TestCodexConfigState:
    def test_reads_top_level_model_provider_and_reasoning(self, tmp_path, monkeypatch):
        config = tmp_path / "config.toml"
        config.write_text(
            'model = "deepseek-v4-pro"\n'
            'model_provider = "opencode-go"\n'
            'model_reasoning_effort = "medium"\n'
            '\n[model_providers.opencode-go]\n'
            'name = "OpenCode Go"\n'
        )
        monkeypatch.setattr(cs, "CODEX_CONFIG", config)

        assert cs.codex_config_state() == {
            "model": "deepseek-v4-pro",
            "model_provider": "opencode-go",
            "model_reasoning_effort": "medium",
        }


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
    def test_azure_uses_low_reasoning_by_default(self, tmp_path, monkeypatch):
        codex_home = tmp_path / ".codex"
        switch_home = tmp_path / ".config" / "codexswitch"
        codex_home.mkdir(parents=True)
        switch_home.mkdir(parents=True)
        config = codex_home / "config.toml"
        state_path = switch_home / "config.json"

        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "CODEX_CONFIG", config)
        monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
        monkeypatch.setattr(cs, "SWITCH_CONFIG", state_path)
        monkeypatch.setattr(cs, "azure_credentials_present", lambda: True)
        monkeypatch.setattr(
            cs,
            "azure_credentials",
            lambda: {
                "endpoint": "https://example.invalid/openai/v1",
                "api_key": "fixture-value",
            },
        )

        cs.update_codex_config("azure", cs.AZURE_MODEL)

        text = config.read_text()
        state = json.loads(state_path.read_text())
        assert 'model = "gpt-5.6-sol"' in text
        assert 'model_reasoning_effort = "low"' in text
        assert f'base_url = "{cs.AZURE_PROXY_URL}"' in text
        assert "env_http_headers" not in text
        assert "[model_providers.azure.auth]" not in text
        assert "fixture-value" not in text
        assert "api-version" not in text
        assert state["reasoning_effort"] == "low"

    def test_openrouter_launch_environment_reads_key_from_vault(
        self, tmp_path, monkeypatch
    ):
        config = tmp_path / "config.toml"
        config.write_text('model_provider = "openrouter"\n')
        monkeypatch.setattr(cs, "CODEX_CONFIG", config)
        monkeypatch.setattr(
            cs, "openrouter_credentials", lambda: {"api_key": "fixture-value"}
        )
        monkeypatch.delenv(cs.OPENROUTER_API_KEY_ENV, raising=False)

        environment = cs.codex_launch_environment()

        assert environment[cs.OPENROUTER_API_KEY_ENV] == "fixture-value"
        assert cs.OPENROUTER_API_KEY_ENV not in cs.os.environ

    def test_openai_records_the_current_authenticated_account(
        self, tmp_path, monkeypatch
    ):
        codex_home = tmp_path / ".codex"
        switch_home = tmp_path / ".config" / "codexswitch"
        codex_home.mkdir(parents=True)
        switch_home.mkdir(parents=True)
        config = codex_home / "config.toml"
        state_path = switch_home / "config.json"
        config.write_text('model = "old"\nmodel_provider = "openai"\n')
        state_path.write_text(
            json.dumps({"openai_account": "stale@example.com"})
        )
        (codex_home / "auth.json").write_text(
            json.dumps(
                {
                    "tokens": {
                        "id_token": make_jwt({"email": "current@example.com"})
                    }
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
        assert state["openai_account"] == "current@example.com"

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

    def test_openrouter_config_uses_loopback_proxy_and_clears_openai_state(self, tmp_path, monkeypatch):
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
        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "CODEX_CONFIG", config)
        monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
        monkeypatch.setattr(cs, "SWITCH_CONFIG", state_path)
        monkeypatch.setattr(
            cs,
            "OPENROUTER_CODEX_MODELS",
            switch_home / "openrouter/codex-models.json",
        )
        monkeypatch.setattr(cs, "openrouter_key_present", lambda: True)
        monkeypatch.setattr(
            cs,
            "openrouter_model_catalog",
            lambda refresh=False: {
                "anthropic/claude-test": {
                    "id": "anthropic/claude-test",
                    "name": "Claude Test",
                    "context_length": 200000,
                }
            },
        )
        monkeypatch.setattr(cs, "warm_codex_model_catalog", lambda: True)

        cs.update_codex_config("openrouter", "anthropic/claude-test", "medium")
        text = config.read_text()
        state = json.loads(state_path.read_text())
        assert 'model_provider = "openrouter"' in text
        assert (
            f"model_catalog_json = {cs.toml_string(str(cs.OPENROUTER_CODEX_MODELS))}"
            in text
        )
        assert 'base_url = "http://127.0.0.1:14555/openrouter/v1"' in text
        assert "env_key" not in text
        assert "[model_providers.openrouter.auth]" not in text
        assert "command =" not in text
        assert "model_reasoning_effort" not in text
        assert "api_key" not in text
        assert "openai_account" not in state
        assert "reasoning_effort" not in state
        codex_catalog = json.loads(
            (switch_home / "openrouter/codex-models.json").read_text()
        )
        assert codex_catalog["models"][0]["slug"] == "anthropic/claude-test"
        assert "api_key" not in json.dumps(codex_catalog)

    def test_openrouter_all_catalog_models_can_apply_without_secret_or_provider_leak(self, tmp_path, monkeypatch):
        codex_home = tmp_path / ".codex"
        switch_home = tmp_path / ".config" / "codexswitch"
        codex_home.mkdir(parents=True)
        switch_home.mkdir(parents=True)
        config = codex_home / "config.toml"
        state_path = switch_home / "config.json"
        catalog = {
            "vendor/model-a": {"id": "vendor/model-a"},
            "vendor/model-b:free": {"id": "vendor/model-b:free"},
            "~vendor/latest": {"id": "~vendor/latest"},
        }

        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "CODEX_CONFIG", config)
        monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
        monkeypatch.setattr(cs, "SWITCH_CONFIG", state_path)
        monkeypatch.setattr(
            cs,
            "OPENROUTER_CODEX_MODELS",
            switch_home / "openrouter/codex-models.json",
        )
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

    def test_openrouter_short_model_alias_resolves_to_full_id(self, tmp_path, monkeypatch):
        codex_home = tmp_path / ".codex"
        switch_home = tmp_path / ".config" / "codexswitch"
        codex_home.mkdir(parents=True)
        switch_home.mkdir(parents=True)
        catalog = {
            "z-ai/glm-5.2": {
                "id": "z-ai/glm-5.2",
                "reasoning": {"supported_efforts": ["xhigh", "high"]},
            }
        }

        monkeypatch.setattr(cs, "CODEX_HOME", codex_home)
        monkeypatch.setattr(cs, "CODEX_CONFIG", codex_home / "config.toml")
        monkeypatch.setattr(cs, "SWITCH_HOME", switch_home)
        monkeypatch.setattr(cs, "SWITCH_CONFIG", switch_home / "config.json")
        monkeypatch.setattr(
            cs,
            "OPENROUTER_CODEX_MODELS",
            switch_home / "openrouter/codex-models.json",
        )
        monkeypatch.setattr(cs, "openrouter_key_present", lambda: True)
        monkeypatch.setattr(cs, "openrouter_model_catalog", lambda refresh=False: catalog)
        monkeypatch.setattr(cs, "warm_codex_model_catalog", lambda: True)

        cs.validate_provider_model("openrouter", "glm-5.2")
        cs.update_codex_config("openrouter", "glm-5.2", "high")

        assert 'model = "z-ai/glm-5.2"' in (codex_home / "config.toml").read_text()
        state = json.loads((switch_home / "config.json").read_text())
        assert state["model"] == "z-ai/glm-5.2"
        assert state["reasoning_effort"] == "high"

    def test_openrouter_models_fallback(self, monkeypatch):
        monkeypatch.setattr(cs, "openrouter_model_catalog", lambda refresh=False: {})
        assert cs.openrouter_models() == cs.OPENROUTER_FALLBACK_MODELS

    def test_openrouter_codex_model_entry_contains_metadata(self, monkeypatch):
        catalog = {
            "qwen/qwen3.7-max": {
                "id": "qwen/qwen3.7-max",
                "name": "Qwen: Qwen3.7 Max",
                "description": "test model",
                "context_length": 1000000,
                "architecture": {"input_modalities": ["text"]},
                "reasoning": {"supported_efforts": ["max", "high", "medium"]},
            }
        }
        monkeypatch.setattr(cs, "openrouter_model_catalog", lambda refresh=False: catalog)

        entry = cs.openrouter_codex_model_entry(
            "qwen/qwen3.7-max", catalog["qwen/qwen3.7-max"]
        )

        assert entry["slug"] == "qwen/qwen3.7-max"
        assert entry["display_name"] == "Qwen: Qwen3.7 Max"
        assert entry["max_context_window"] == 1000000
        assert entry["context_window"] == 1000000
        assert entry["auto_compact_token_limit"] == 800000
        assert entry["default_reasoning_level"] == "medium"
        assert {"effort": "xhigh", "description": "xhigh reasoning"} in entry[
            "supported_reasoning_levels"
        ]

    def test_save_openrouter_key_is_secret_file(self, tmp_path, monkeypatch):
        auth_path = tmp_path / "openrouter" / "auth.json"
        monkeypatch.setattr(cs, "SWITCH_HOME", tmp_path)
        monkeypatch.setattr(cs, "OPENROUTER_AUTH", auth_path)
        cs.save_openrouter_key(" test-openrouter-key-not-secret ")
        assert cs.openrouter_key_present() is True
        assert not auth_path.exists()
        vault_text = (tmp_path / "vault.enc").read_text()
        assert "test-openrouter-key-not-secret" not in vault_text


class TestOpenCodeGoStore:
    def test_save_opencode_go_key_is_secret_file(self, tmp_path, monkeypatch):
        auth_path = tmp_path / "opencode-go" / "auth.json"
        monkeypatch.setattr(cs, "SWITCH_HOME", tmp_path)
        monkeypatch.setattr(cs, "OPENCODE_GO_AUTH", auth_path)

        cs.save_opencode_go_key(" test-opencode-go-key-not-secret ")

        assert cs.opencode_go_key_present() is True
        assert not auth_path.exists()
        vault_text = (tmp_path / "vault.enc").read_text()
        assert "test-opencode-go-key-not-secret" not in vault_text

    def test_opencode_key_present_prefers_switch_store_and_falls_back_to_legacy(
        self, tmp_path, monkeypatch
    ):
        switch_auth = tmp_path / "switch" / "auth.json"
        legacy_auth = tmp_path / "legacy" / "auth.json"
        monkeypatch.setattr(cs, "SWITCH_HOME", tmp_path / "switch-home")
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
