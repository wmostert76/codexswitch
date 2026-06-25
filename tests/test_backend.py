"""Tests for codexswitch backend pure functions."""
import base64
import importlib.machinery
import importlib.util
import json
import os
import tempfile
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
