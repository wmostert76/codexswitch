#!/usr/bin/env python3
"""Shared helpers for CodexSwitch components.

This module contains logic that is used by multiple entry points:
  - bin/codexswitch          (CLI backend)
  - bin/codex-opencode-go-proxy (Responses API proxy)
  - bin/opencode-go-token    (credential reader)
  - bin/openrouter-token     (OpenRouter credential reader)

Keeping it here avoids code duplication and ensures that a bugfix only
needs to happen in one place.
"""
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
import pwd


VERSION = "0.6.1"
CREDITS_OWNER = "by WAM-Software since (c) 1988"
CREDITS_AI = "AI-assisted implementation: OpenAI Codex"
ASCII_LOGO = r"""   ___          _            __          _ _       _
  / __\___   __| | _____  __/ _\_      _(_) |_ ___| |__
 / /  / _ \ / _` |/ _ \ \/ /\ \\ \ /\ / / | __/ __| '_ \
/ /__| (_) | (_| |  __/>  < _\ \\ V  V /| | || (__| | | |
\____/\___/ \__,_|\___/_/\_\\__/ \_/\_/ |_|\__\___|_| |_|"""
COMMANDER_SPACED = "C O M M A N D E R"
ASCII_LOGO_WIDTH = max(len(line) for line in ASCII_LOGO.splitlines())
COMMANDER_CENTERED = COMMANDER_SPACED.rjust(
    (ASCII_LOGO_WIDTH + len(COMMANDER_SPACED)) // 2
)
BRAND_BANNER = f"{ASCII_LOGO}\n{COMMANDER_CENTERED}"


def user_home() -> Path:
    """Resolve the real home directory, respecting SUDO_USER."""
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user and sudo_user != "root":
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            pass
    return Path(os.environ.get("HOME", str(Path.home()))).expanduser()


def opencode_bin() -> str | None:
    """Return the opencode binary path or None if not found."""
    found = shutil.which("opencode")
    if found:
        return found
    fallback = user_home() / ".local/share/npm-global/bin/opencode"
    if fallback.exists():
        return str(fallback)
    return None


def parse_opencode_catalog(output: str) -> dict[str, dict]:
    """Parse verbose opencode model listing into a catalog dict.

    Each model line starts with ``opencode-go/<id>`` followed by a JSON
    metadata blob on the remaining text.  Deprecated models are excluded.
    """
    catalog: dict[str, dict] = {}
    decoder = json.JSONDecoder()
    pattern = re.compile(r"^opencode-go/([^\n]+)\n", re.MULTILINE)
    for match in pattern.finditer(output):
        try:
            metadata, _ = decoder.raw_decode(output, match.end())
        except json.JSONDecodeError:
            continue
        if isinstance(metadata, dict) and metadata.get("status", "active") != "deprecated":
            catalog[match.group(1)] = metadata
    return catalog


def opencode_catalog_from_binary() -> dict[str, dict]:
    """Query the opencode binary for the model catalog.

    Returns an empty dict if the binary is missing or the command fails.
    """
    binary = opencode_bin()
    if not binary:
        return {}
    try:
        proc = subprocess.run(
            [binary, "models", "opencode-go", "--verbose"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    except Exception:
        return {}
    if proc.returncode != 0:
        return {}
    return parse_opencode_catalog(proc.stdout)


def opencode_catalog_from_cache(cache_path: Path) -> dict[str, dict]:
    """Read models from the opencode models cache file."""
    try:
        data = json.loads(cache_path.read_text())
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    models = data.get("models")
    if not isinstance(models, dict):
        models = data.get("opencode-go", {}).get("models", {})
    if not isinstance(models, dict):
        return {}
    return {
        model_id: meta
        for model_id, meta in models.items()
        if not isinstance(meta, dict) or meta.get("status") != "deprecated"
    }


OPENCODE_GO_BASE_URL = "https://opencode.ai/zen/go/v1"
OPENCODE_GO_FALLBACK_CATALOG: dict[str, dict] = {
    "kimi-k2.6": {
        "name": "Kimi K2.6",
        "family": "Moonshot",
        "status": "active",
        "limit": {"context": 128000, "output": 16000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"medium": {}},
    },
    "kimi-k2.7-code": {
        "name": "Kimi K2.7 Code",
        "family": "Moonshot",
        "status": "active",
        "limit": {"context": 128000, "output": 16000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"medium": {}},
    },
    "minimax-m3": {
        "name": "MiniMax M3",
        "family": "MiniMax",
        "status": "active",
        "limit": {"context": 128000, "output": 16000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"medium": {}},
    },
    "qwen3-coder": {
        "name": "Qwen3 Coder",
        "family": "Qwen",
        "status": "active",
        "limit": {"context": 128000, "output": 16000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"medium": {}},
    },
    "glm-4.6": {
        "name": "GLM 4.6",
        "family": "Z.ai",
        "status": "active",
        "limit": {"context": 128000, "output": 16000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"medium": {}},
    },
}


def normalize_opencode_model(model_id: str, item: dict | None = None) -> dict:
    """Return CodexSwitch metadata for an OpenCode Go /v1/models item."""
    item = item or {}
    fallback = OPENCODE_GO_FALLBACK_CATALOG.get(model_id, {})
    name = item.get("name") if isinstance(item, dict) else None
    return {
        "name": name or fallback.get("name") or model_id,
        "family": fallback.get("family", "OpenCode Go"),
        "status": "active",
        "limit": fallback.get("limit", {"context": 128000, "output": 16000}),
        "capabilities": fallback.get(
            "capabilities", {"input": {"text": True}, "toolcall": True}
        ),
        "variants": fallback.get("variants", {"medium": {}}),
    }


def opencode_catalog_from_upstream(
    base_url: str = OPENCODE_GO_BASE_URL,
) -> dict[str, dict]:
    """Fetch OpenCode Go models from its OpenAI-compatible /models endpoint."""
    try:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/models",
            headers={
                "accept": "application/json",
                "user-agent": "codexswitch/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return {}
    output: dict[str, dict] = {}
    data = payload.get("data", []) if isinstance(payload, dict) else []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        model_id = item["id"]
        output[model_id] = normalize_opencode_model(model_id, item)
    return output
