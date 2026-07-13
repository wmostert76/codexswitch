"""Tests for codexswitch_common shared helpers."""
import json
import os
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest
import codexswitch_common as common


class FakeResponse:
    def __init__(self, payload: bytes = b"") -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self.payload


def enable_remote(home: Path) -> None:
    common.write_remote_vault_config(
        {
            "enabled": True,
            "endpoint": "https://fsn1.your-objectstorage.com",
            "bucket": "test-bucket",
            "object": "codexswitch/vault.enc",
            "region": "fsn1",
        },
        home,
    )


def remote_environment(monkeypatch) -> None:
    monkeypatch.setenv("CODEXSWITCH_S3_ACCESS_KEY_ID", "fixture-access")
    monkeypatch.setenv("CODEXSWITCH_S3_SECRET_ACCESS_KEY", "fixture-secret")
    monkeypatch.setenv(
        "CODEXSWITCH_REMOTE_VAULT_PASSPHRASE",
        "fixture-shared-passphrase-long-enough",
    )


class TestRemoteVault:
    def test_shared_passphrase_derives_same_key_on_new_machine(
        self, tmp_path, monkeypatch
    ):
        first = tmp_path / "first"
        second = tmp_path / "second"
        enable_remote(first)
        enable_remote(second)
        remote_environment(monkeypatch)
        assert common.remote_vault_key(first) == common.remote_vault_key(second)

    def test_remote_load_fetches_every_time_without_using_local_cache(
        self, tmp_path, monkeypatch
    ):
        enable_remote(tmp_path)
        remote_environment(monkeypatch)
        Fernet = common._fernet()
        remote_token = Fernet(common.remote_vault_key(tmp_path)).encrypt(
            json.dumps({"remote": {"api_key": "remote-value"}}).encode()
        )
        common.vault_path(tmp_path).write_bytes(
            Fernet(common.vault_key(tmp_path)).encrypt(b'{"local": true}')
        )
        calls = []

        def fake_urlopen(request, timeout=0):
            calls.append(request.full_url)
            return FakeResponse(remote_token)

        monkeypatch.setattr(common.urllib.request, "urlopen", fake_urlopen)
        assert common.vault_load(tmp_path)["remote"]["api_key"] == "remote-value"
        assert common.vault_load(tmp_path)["remote"]["api_key"] == "remote-value"
        assert len(calls) == 2

    def test_remote_offline_never_falls_back_to_local_vault(
        self, tmp_path, monkeypatch
    ):
        enable_remote(tmp_path)
        remote_environment(monkeypatch)
        common.vault_path(tmp_path).write_bytes(b"local-cache-must-not-be-read")
        monkeypatch.setattr(
            common.urllib.request,
            "urlopen",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                urllib.error.URLError("offline")
            ),
        )
        with pytest.raises(RuntimeError, match="niet bereikbaar"):
            common.vault_load(tmp_path)
        assert common.vault_status(tmp_path)["label"] == "OFFLINE"

    def test_remote_save_uploads_encrypted_object_without_local_vault(
        self, tmp_path, monkeypatch
    ):
        enable_remote(tmp_path)
        remote_environment(monkeypatch)
        uploads = []

        def fake_urlopen(request, timeout=0):
            uploads.append(request)
            return FakeResponse()

        monkeypatch.setattr(common.urllib.request, "urlopen", fake_urlopen)
        common.vault_save({"secret": "fixture-provider-key"}, tmp_path)
        assert len(uploads) == 1
        request = uploads[0]
        assert request.get_method() == "PUT"
        assert request.full_url.endswith("/test-bucket/codexswitch/vault.enc")
        assert b"fixture-provider-key" not in request.data
        assert not common.vault_path(tmp_path).exists()


class TestUserHome:
    def test_basic_home(self, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", "/tmp/test-home-xyz")
        assert common.user_home() == Path("/tmp/test-home-xyz")

    def test_expanduser(self, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", "/tmp/test-home-xyz")
        result = common.user_home()
        assert result == Path("/tmp/test-home-xyz")

    def test_sudo_user_respected(self, monkeypatch):
        monkeypatch.setenv("SUDO_USER", "root")
        monkeypatch.setenv("HOME", "/tmp/test-home-xyz")
        # SUDO_USER=root should fall through to HOME
        assert common.user_home() == Path("/tmp/test-home-xyz")


class TestParseOpencodeCatalog:
    def test_empty_output(self):
        assert common.parse_opencode_catalog("") == {}

    def test_single_model(self):
        output = 'opencode-go/test-model\n{"name": "Test", "status": "active"}\n'
        result = common.parse_opencode_catalog(output)
        assert "test-model" in result
        assert result["test-model"]["name"] == "Test"

    def test_deprecated_excluded(self):
        output = 'opencode-go/old-model\n{"name": "Old", "status": "deprecated"}\n'
        result = common.parse_opencode_catalog(output)
        assert "old-model" not in result

    def test_multiple_models(self):
        output = (
            'opencode-go/model-a\n{"name": "A"}\n'
            'opencode-go/model-b\n{"name": "B"}\n'
        )
        result = common.parse_opencode_catalog(output)
        assert set(result.keys()) == {"model-a", "model-b"}

    def test_malformed_json_skipped(self):
        output = 'opencode-go/bad-model\n{not valid json}\n'
        result = common.parse_opencode_catalog(output)
        assert "bad-model" not in result

    def test_default_status_active(self):
        """Models without a status field should be treated as active."""
        output = 'opencode-go/no-status\n{"name": "NoStatus"}\n'
        result = common.parse_opencode_catalog(output)
        assert "no-status" in result


class TestOpencodeCatalogFromCache:
    def test_missing_file(self, tmp_path):
        assert common.opencode_catalog_from_cache(tmp_path / "nonexistent.json") == {}

    def test_valid_cache(self, tmp_path):
        cache = tmp_path / "models.json"
        cache.write_text(json.dumps({
            "opencode-go": {
                "models": {
                    "model-a": {"name": "A", "status": "active"},
                    "model-b": {"name": "B", "status": "deprecated"},
                }
            }
        }))
        result = common.opencode_catalog_from_cache(cache)
        assert "model-a" in result
        assert "model-b" not in result

    def test_invalid_json(self, tmp_path):
        cache = tmp_path / "models.json"
        cache.write_text("not json at all")
        assert common.opencode_catalog_from_cache(cache) == {}


class TestReasoningOptionsConversion:
    """Tests for converting opencode cache reasoning_options to variants."""

    def test_effort_values_converted(self):
        meta = {
            "reasoning_options": [{"type": "effort", "values": ["high", "max"]}],
        }
        result = common._reasoning_options_to_variants(meta)
        assert "high" in result
        assert "max" in result
        assert result["high"] == {"reasoningEffort": "high"}

    def test_empty_options(self):
        assert common._reasoning_options_to_variants({}) == {}
        assert common._reasoning_options_to_variants({"reasoning_options": []}) == {}

    def test_non_effort_type_ignored(self):
        meta = {"reasoning_options": [{"type": "other", "values": ["x"]}]}
        assert common._reasoning_options_to_variants(meta) == {}


class TestNormalizeCacheModel:
    def test_variants_filled_from_reasoning_options(self):
        meta = {
            "name": "Test",
            "limit": {"context": 1000000, "output": 65536},
            "reasoning_options": [{"type": "effort", "values": ["high"]}],
        }
        result = common._normalize_cache_model("test", meta)
        assert result["variants"] == {"high": {"reasoningEffort": "high"}}
        assert result["limit"]["context"] == 1000000

    def test_existing_variants_preserved(self):
        meta = {
            "name": "Test",
            "variants": {"low": {}, "high": {}},
            "reasoning_options": [{"type": "effort", "values": ["max"]}],
        }
        result = common._normalize_cache_model("test", meta)
        assert result["variants"] == {"low": {}, "high": {}}

    def test_no_variants_no_options(self):
        meta = {"name": "Test", "limit": {"context": 128000, "output": 16000}}
        result = common._normalize_cache_model("test", meta)
        assert "variants" not in result or result["variants"] == {}


class TestFallbackCatalog:
    def test_fallback_has_real_context_limits(self):
        # kimi-k2.6 should have 262144 context, not the old default 128000
        meta = common.OPENCODE_GO_FALLBACK_CATALOG["kimi-k2.6"]
        assert meta["limit"]["context"] == 262144

    def test_fallback_minimax_m3_has_thinking_variants(self):
        meta = common.OPENCODE_GO_FALLBACK_CATALOG["minimax-m3"]
        assert "thinking" in meta["variants"]

    def test_fallback_models_without_reasoning_have_empty_variants(self):
        # Models that have no reasoning variants at all (like kimi, qwen,
        # glm-5, minimax-m2.x) should have empty variants rather than the old
        # forced {"medium": {}} default.
        no_reasoning = [
            mid for mid, meta in common.OPENCODE_GO_FALLBACK_CATALOG.items()
            if not meta.get("variants")
        ]
        assert "kimi-k2.6" in no_reasoning
        assert "glm-5" in no_reasoning
        # Models WITH reasoning should not be empty
        assert "deepseek-v4-flash" not in no_reasoning
        assert "minimax-m3" not in no_reasoning


class TestUpstreamMerge:
    def test_upstream_merges_with_fallback(self, monkeypatch):
        """opencode_catalog_from_upstream should include fallback models."""
        import urllib.request
        captured = {}

        class FakeResponse:
            def __init__(self, data):
                self._data = data
            def read(self):
                return self._data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        def fake_urlopen(req, timeout):
            import json as _json
            payload = _json.dumps({"data": [{"id": "new-model"}]}).encode()
            return FakeResponse(payload)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        result = common.opencode_catalog_from_upstream()
        assert "new-model" in result
        # Fallback models should also be present
        assert "kimi-k2.6" in result
        assert result["kimi-k2.6"]["limit"]["context"] == 262144
