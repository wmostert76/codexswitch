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
try:
    import pwd
except ImportError:  # Windows
    pwd = None


VERSION = "0.8.0"
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
    if pwd and sudo_user and sudo_user != "root":
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
        model_id: _normalize_cache_model(model_id, meta)
        for model_id, meta in models.items()
        if not isinstance(meta, dict) or meta.get("status") != "deprecated"
    }


def _reasoning_options_to_variants(meta: dict) -> dict[str, dict]:
    """Convert the opencode cache ``reasoning_options`` list to a ``variants`` dict.

    The ``~/.cache/opencode/models.json`` file stores reasoning metadata as
    ``reasoning_options: [{type: "effort", values: ["high", "max"]}]`` rather
    than the ``variants`` dict emitted by ``opencode --verbose``.  This
    helper bridges the two schemas so reasoning choices work regardless of
    which source populated the cache.
    """
    reasoning_options = meta.get("reasoning_options")
    if not isinstance(reasoning_options, list):
        return {}
    variants: dict[str, dict] = {}
    for option in reasoning_options:
        if not isinstance(option, dict):
            continue
        if option.get("type") != "effort":
            continue
        values = option.get("values", [])
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str):
                variants[value] = {"reasoningEffort": value}
    return variants


def _normalize_cache_model(model_id: str, meta: dict) -> dict:
    """Normalize a cached model entry to the catalog schema.

    Fills in ``variants`` from ``reasoning_options`` when the cache uses the
    newer schema and preserves real context/output limits from the cache.
    """
    if not isinstance(meta, dict):
        return meta
    normalized = dict(meta)
    # If variants are missing but reasoning_options exist, convert them.
    if not normalized.get("variants") and normalized.get("reasoning_options"):
        converted = _reasoning_options_to_variants(normalized)
        if converted:
            normalized["variants"] = converted
    return normalized


OPENCODE_GO_BASE_URL = "https://opencode.ai/zen/go/v1"
OPENCODE_GO_FALLBACK_CATALOG: dict[str, dict] = {
    "deepseek-v4-flash": {
        "name": "DeepSeek V4 Flash",
        "family": "deepseek-flash",
        "status": "active",
        "limit": {"context": 1000000, "output": 384000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"low": {}, "medium": {}, "high": {}, "max": {}},
    },
    "deepseek-v4-pro": {
        "name": "DeepSeek V4 Pro",
        "family": "deepseek-thinking",
        "status": "active",
        "limit": {"context": 1000000, "output": 384000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"low": {}, "medium": {}, "high": {}, "max": {}},
    },
    "glm-5": {
        "name": "GLM 5",
        "family": "glm",
        "status": "active",
        "limit": {"context": 202752, "output": 32768},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "glm-5.1": {
        "name": "GLM 5.1",
        "family": "glm",
        "status": "active",
        "limit": {"context": 202752, "output": 32768},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "glm-5.2": {
        "name": "GLM-5.2",
        "family": "glm",
        "status": "active",
        "limit": {"context": 1000000, "output": 131072},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"high": {}, "max": {}},
    },
    "hy3-preview": {
        "name": "HY3 Preview",
        "family": "hy3",
        "status": "active",
        "limit": {"context": 128000, "output": 65536},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "kimi-k2.5": {
        "name": "Kimi K2.5",
        "family": "kimi-k2",
        "status": "active",
        "limit": {"context": 262144, "output": 65536},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "kimi-k2.6": {
        "name": "Kimi K2.6",
        "family": "kimi-k2",
        "status": "active",
        "limit": {"context": 262144, "output": 65536},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "kimi-k2.7-code": {
        "name": "Kimi K2.7 Code",
        "family": "kimi-k2",
        "status": "active",
        "limit": {"context": 262144, "output": 262144},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "mimo-v2-omni": {
        "name": "Mimo V2 Omni",
        "family": "mimo-v2",
        "status": "active",
        "limit": {"context": 262144, "output": 128000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "mimo-v2-pro": {
        "name": "Mimo V2 Pro",
        "family": "mimo-v2",
        "status": "active",
        "limit": {"context": 1048576, "output": 128000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "mimo-v2.5": {
        "name": "Mimo V2.5",
        "family": "mimo-v2.5",
        "status": "active",
        "limit": {"context": 1000000, "output": 128000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"low": {}, "medium": {}, "high": {}},
    },
    "mimo-v2.5-pro": {
        "name": "Mimo V2.5 Pro",
        "family": "mimo-v2.5-pro",
        "status": "active",
        "limit": {"context": 1048576, "output": 128000},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"low": {}, "medium": {}, "high": {}},
    },
    "minimax-m2.5": {
        "name": "MiniMax M2.5",
        "family": "minimax-m2",
        "status": "active",
        "limit": {"context": 204800, "output": 65536},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "minimax-m2.7": {
        "name": "MiniMax M2.7",
        "family": "minimax-m2.7",
        "status": "active",
        "limit": {"context": 204800, "output": 131072},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "minimax-m3": {
        "name": "MiniMax M3",
        "family": "minimax-m3",
        "status": "active",
        "limit": {"context": 1000000, "output": 131072},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {"none": {}, "thinking": {}},
    },
    "qwen3.5-plus": {
        "name": "Qwen3.5 Plus",
        "family": "qwen3.5",
        "status": "active",
        "limit": {"context": 262144, "output": 65536},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "qwen3.6-plus": {
        "name": "Qwen3.6 Plus",
        "family": "qwen3.6",
        "status": "active",
        "limit": {"context": 1000000, "output": 65536},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "qwen3.7-max": {
        "name": "Qwen 3.7 Max",
        "family": "qwen3.7-max",
        "status": "active",
        "limit": {"context": 1000000, "output": 65536},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
    },
    "qwen3.7-plus": {
        "name": "Qwen3.7 Plus",
        "family": "qwen3.7-plus",
        "status": "active",
        "limit": {"context": 1000000, "output": 65536},
        "capabilities": {"input": {"text": True}, "toolcall": True},
        "variants": {},
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
        "limit": fallback.get("limit", {"context": 128000, "output": 65536}),
        "capabilities": fallback.get(
            "capabilities", {"input": {"text": True}, "toolcall": True}
        ),
        "variants": fallback.get("variants", {}),
    }


def opencode_catalog_from_upstream(
    base_url: str = OPENCODE_GO_BASE_URL,
) -> dict[str, dict]:
    """Fetch OpenCode Go model IDs from the upstream /models endpoint and
    merge them with the built-in fallback catalog.

    The upstream endpoint only returns bare model IDs (no metadata), so every
    model is enriched with ``normalize_opencode_model`` which fills in name,
    context limits, reasoning variants and capabilities from the fallback
    catalog when the upstream provides none.  All fallback models are included
    even when they are absent from the upstream list, ensuring a usable
    catalog on a fresh host without the opencode binary installed.
    """
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
        # Network failure: return the full fallback catalog so the caller
        # still has a usable model list.
        return {mid: normalize_opencode_model(mid) for mid in OPENCODE_GO_FALLBACK_CATALOG}
    output: dict[str, dict] = {}
    data = payload.get("data", []) if isinstance(payload, dict) else []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        model_id = item["id"]
        output[model_id] = normalize_opencode_model(model_id, item)
    # Ensure all fallback models are present even if the upstream omitted them.
    for model_id in OPENCODE_GO_FALLBACK_CATALOG:
        if model_id not in output:
            output[model_id] = normalize_opencode_model(model_id)
    return output
