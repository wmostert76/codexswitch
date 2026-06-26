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
from pathlib import Path
import pwd


VERSION = "0.5.3"
CREDITS_OWNER = "by WAM-Software since (c) 1988"
CREDITS_AI = "AI-assisted implementation: OpenAI Codex"


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
    models = data.get("opencode-go", {}).get("models", {}) if isinstance(data, dict) else {}
    if not isinstance(models, dict):
        return {}
    return {
        model_id: meta
        for model_id, meta in models.items()
        if not isinstance(meta, dict) or meta.get("status") != "deprecated"
    }
