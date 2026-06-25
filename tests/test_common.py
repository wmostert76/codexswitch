"""Tests for codexswitch_common shared helpers."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import codexswitch_common as common


class TestUserHome:
    def test_basic_home(self, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", "/tmp/test-home-xyz")
        assert common.user_home() == Path("/tmp/test-home-xyz")

    def test_expanduser(self, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", "/tmp/test-home-xyz")
        result = common.user_home()
        assert result.is_absolute()

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
