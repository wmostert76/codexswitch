#!/usr/bin/env python3
"""Shared helpers for CodexSwitch components.

This module contains logic that is used by multiple entry points:
  - bin/codexswitch_backend.py (CLI backend)
  - bin/codex-opencode-go-proxy (Responses API proxy)
  - bin/opencode-go-token    (credential reader)

Keeping it here avoids code duplication and ensures that a bugfix only
needs to happen in one place.
"""
import json
import os
import re
import shutil
import subprocess
import copy
import base64
import hashlib
import hmac
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
try:
    import pwd
except ImportError:  # Windows
    pwd = None


VERSION = "26.07.1800"
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
VAULT_SERVICE = "CodexSwitch"
VAULT_USER = "default"
REMOTE_VAULT_SERVICE = "CodexSwitch Remote Vault"
REMOTE_ACCESS_USER = "s3-access-key-id"
REMOTE_SECRET_USER = "s3-secret-access-key"
REMOTE_PASSPHRASE_USER = "vault-passphrase"
REMOTE_CONFIG_NAME = "remote-vault.json"
REMOTE_CREDENTIAL_DIR_NAME = "remote-credentials"
REMOTE_DEFAULT_ENDPOINT = "https://fsn1.your-objectstorage.com"
REMOTE_DEFAULT_BUCKET = "wmostert"
REMOTE_DEFAULT_OBJECT = "codexswitch/vault.enc"
REMOTE_DEFAULT_REGION = "fsn1"
_VAULT_SESSION_CACHE: dict[str, dict] = {}
_VAULT_SESSION_ERRORS: dict[str, str] = {}
_VAULT_SESSION_HOMES: set[str] = set()
_VAULT_SESSION_LOCK = threading.RLock()


def user_home() -> Path:
    """Resolve the real home directory, respecting SUDO_USER."""
    sudo_user = os.environ.get("SUDO_USER")
    if pwd and sudo_user and sudo_user != "root":
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            pass
    return Path(os.environ.get("HOME", str(Path.home()))).expanduser()


def switch_home() -> Path:
    return user_home() / ".config/codexswitch"


def vault_path(home: Path | None = None) -> Path:
    return (home or switch_home()) / "vault.enc"


def vault_key_path(home: Path | None = None) -> Path:
    return (home or switch_home()) / "vault.key"


def remote_vault_config_path(home: Path | None = None) -> Path:
    return (home or switch_home()) / REMOTE_CONFIG_NAME


def _vault_session_key(home: Path | None = None) -> str:
    return str((home or switch_home()).expanduser().resolve())


def enable_vault_session_cache(home: Path | None = None) -> None:
    """Enable process-local decrypted vault caching for one config home."""
    with _VAULT_SESSION_LOCK:
        _VAULT_SESSION_HOMES.add(_vault_session_key(home))


def refresh_vault_session_cache(home: Path | None = None) -> dict:
    """Discard the process-local entry and fetch the remote vault again."""
    key = _vault_session_key(home)
    with _VAULT_SESSION_LOCK:
        _VAULT_SESSION_HOMES.add(key)
        _VAULT_SESSION_CACHE.pop(key, None)
        _VAULT_SESSION_ERRORS.pop(key, None)
    return vault_load(home)


def disable_vault_session_cache(home: Path | None = None) -> None:
    """Disable and erase the process-local cache entry, primarily for tests."""
    key = _vault_session_key(home)
    with _VAULT_SESSION_LOCK:
        _VAULT_SESSION_HOMES.discard(key)
        _VAULT_SESSION_CACHE.pop(key, None)
        _VAULT_SESSION_ERRORS.pop(key, None)


def _invalidate_vault_session_cache(home: Path | None = None) -> None:
    key = _vault_session_key(home)
    with _VAULT_SESSION_LOCK:
        _VAULT_SESSION_CACHE.pop(key, None)
        _VAULT_SESSION_ERRORS.pop(key, None)


def remote_credential_dir(home: Path | None = None) -> Path:
    return (home or switch_home()) / REMOTE_CREDENTIAL_DIR_NAME


def remote_credential_path(user: str, home: Path | None = None) -> Path:
    return remote_credential_dir(home) / f"{user}.cred"


def remote_vault_config(home: Path | None = None) -> dict:
    path = remote_vault_config_path(home)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ongeldige remote-vaultconfig: {exc}") from exc
    return data if isinstance(data, dict) and data.get("enabled") else {}


def remote_vault_enabled(home: Path | None = None) -> bool:
    return bool(remote_vault_config(home))


def write_remote_vault_config(config: dict, home: Path | None = None) -> None:
    path = remote_vault_config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    _chmod_secret(path.parent, directory=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _chmod_secret(tmp)
        os.replace(tmp, path)
        _chmod_secret(path)
        _invalidate_vault_session_cache(home)
    finally:
        tmp.unlink(missing_ok=True)


def _remote_keyring_value(user: str) -> str | None:
    try:
        import keyring
        return keyring.get_password(REMOTE_VAULT_SERVICE, user)
    except Exception:
        return None


def _systemd_credentials_binary() -> str | None:
    if os.name == "nt":
        return None
    return shutil.which("systemd-creds")


def _remote_systemd_credential_value(
    user: str, home: Path | None = None
) -> str | None:
    path = remote_credential_path(user, home)
    binary = _systemd_credentials_binary()
    if not binary or not path.is_file():
        return None
    try:
        result = subprocess.run(
            [
                binary,
                "--user",
                f"--name={user}",
                "decrypt",
                str(path),
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    value = result.stdout.decode("utf-8", errors="strict").rstrip("\r\n")
    return value or None


def _store_remote_systemd_credentials(
    values: dict[str, str], home: Path | None = None
) -> bool:
    binary = _systemd_credentials_binary()
    if not binary:
        return False
    directory = remote_credential_dir(home)
    directory.mkdir(parents=True, exist_ok=True)
    _chmod_secret(directory, directory=True)
    pending: list[tuple[Path, Path]] = []
    try:
        for user, value in values.items():
            path = remote_credential_path(user, home)
            tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            result = subprocess.run(
                [
                    binary,
                    "--user",
                    f"--name={user}",
                    "encrypt",
                    "-",
                    str(tmp),
                ],
                input=value.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            if result.returncode or not tmp.is_file():
                tmp.unlink(missing_ok=True)
                return False
            _chmod_secret(tmp)
            pending.append((tmp, path))
        for tmp, path in pending:
            os.replace(tmp, path)
            _chmod_secret(path)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        for tmp, _ in pending:
            tmp.unlink(missing_ok=True)


def store_remote_credentials(
    access_key: str, secret_key: str, passphrase: str
) -> None:
    values = {
        REMOTE_ACCESS_USER: access_key,
        REMOTE_SECRET_USER: secret_key,
        REMOTE_PASSPHRASE_USER: passphrase,
    }
    try:
        import keyring
        keyring.set_password(REMOTE_VAULT_SERVICE, REMOTE_ACCESS_USER, access_key)
        keyring.set_password(REMOTE_VAULT_SERVICE, REMOTE_SECRET_USER, secret_key)
        keyring.set_password(
            REMOTE_VAULT_SERVICE, REMOTE_PASSPHRASE_USER, passphrase
        )
        return
    except Exception as exc:
        if _store_remote_systemd_credentials(values):
            return
        environment_matches = (
            os.environ.get("CODEXSWITCH_S3_ACCESS_KEY_ID") == access_key
            and os.environ.get("CODEXSWITCH_S3_SECRET_ACCESS_KEY") == secret_key
            and os.environ.get("CODEXSWITCH_REMOTE_VAULT_PASSPHRASE")
            == passphrase
        )
        if environment_matches:
            return
        raise RuntimeError(
            "remote-vault secrets konden niet in de OS-keyring of versleutelde "
            "systemd credentialopslag worden opgeslagen; zet de drie "
            "CODEXSWITCH remote-vault environmentvariabelen"
        ) from exc


def remote_credentials() -> tuple[str, str]:
    home = switch_home()
    access_key = (
        os.environ.get("CODEXSWITCH_S3_ACCESS_KEY_ID")
        or _remote_keyring_value(REMOTE_ACCESS_USER)
        or _remote_systemd_credential_value(REMOTE_ACCESS_USER, home)
    )
    secret_key = (
        os.environ.get("CODEXSWITCH_S3_SECRET_ACCESS_KEY")
        or _remote_keyring_value(REMOTE_SECRET_USER)
        or _remote_systemd_credential_value(REMOTE_SECRET_USER, home)
    )
    if not access_key or not secret_key:
        raise RuntimeError(
            "remote-vault S3-credentials ontbreken in environment of OS-keyring"
        )
    return access_key, secret_key


def remote_vault_key(home: Path | None = None) -> bytes:
    passphrase = os.environ.get(
        "CODEXSWITCH_REMOTE_VAULT_PASSPHRASE"
    ) or _remote_keyring_value(REMOTE_PASSPHRASE_USER) or _remote_systemd_credential_value(
        REMOTE_PASSPHRASE_USER, home or switch_home()
    )
    if not passphrase:
        raise RuntimeError(
            "remote-vault passphrase ontbreekt in environment of OS-keyring"
        )
    endpoint, bucket, object_name, _ = _remote_settings(home)
    salt = hashlib.sha256(
        f"CodexSwitch Remote Vault\0{endpoint}\0{bucket}\0{object_name}".encode(
            "utf-8"
        )
    ).digest()[:16]
    derived = hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, 600_000, dklen=32
    )
    return base64.urlsafe_b64encode(derived)


def _remote_settings(home: Path | None = None) -> tuple[str, str, str, str]:
    config = remote_vault_config(home)
    if not config:
        raise RuntimeError("remote vault is niet geconfigureerd")
    endpoint = str(config.get("endpoint") or REMOTE_DEFAULT_ENDPOINT).rstrip("/")
    bucket = str(config.get("bucket") or REMOTE_DEFAULT_BUCKET).strip()
    object_name = str(config.get("object") or REMOTE_DEFAULT_OBJECT).strip("/")
    region = str(config.get("region") or REMOTE_DEFAULT_REGION).strip()
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path.rstrip("/"):
        raise RuntimeError("remote-vault endpoint moet een HTTPS host-URL zijn")
    if not bucket or not object_name or not region:
        raise RuntimeError("remote-vault bucket, object en region zijn verplicht")
    return endpoint, bucket, object_name, region


def remote_vault_request(
    method: str, body: bytes | None = None, home: Path | None = None
) -> bytes | None:
    endpoint, bucket, object_name, region = _remote_settings(home)
    access_key, secret_key = remote_credentials()
    parsed = urllib.parse.urlsplit(endpoint)
    canonical_uri = "/" + "/".join(
        urllib.parse.quote(part, safe="-_.~")
        for part in (bucket, *object_name.split("/"))
    )
    payload = body or b""
    payload_hash = hashlib.sha256(payload).hexdigest()
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    canonical_headers = (
        f"host:{parsed.netloc}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(
        [method, canonical_uri, "", canonical_headers, signed_headers, payload_hash]
    )
    scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    def sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    date_key = sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    region_key = sign(date_key, region)
    service_key = sign(region_key, "s3")
    signing_key = sign(service_key, "aws4_request")
    signature = hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    request = urllib.request.Request(
        urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, canonical_uri, "", "")),
        data=payload if method == "PUT" else None,
        method=method,
        headers={
            "Authorization": authorization,
            "Host": parsed.netloc,
            "X-Amz-Content-Sha256": payload_hash,
            "X-Amz-Date": amz_date,
            "Content-Type": "application/octet-stream",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if method == "GET" and exc.code == 404:
            return None
        raise RuntimeError(f"remote vault HTTP {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(f"remote vault niet bereikbaar: {type(exc).__name__}") from exc


def _chmod_secret(path: Path, directory: bool = False) -> None:
    try:
        path.chmod(0o700 if directory else 0o600)
    except OSError:
        pass


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError(
            "cryptography ontbreekt; installeer requirements.txt opnieuw"
        ) from exc
    return Fernet


def _key_from_keyring() -> bytes | None:
    try:
        import keyring
    except Exception:
        return None
    try:
        value = keyring.get_password(VAULT_SERVICE, VAULT_USER)
    except Exception:
        return None
    if not value:
        return None
    try:
        return value.encode("ascii")
    except UnicodeEncodeError:
        return None


def _store_key_in_keyring(key: bytes) -> bool:
    try:
        import keyring
    except Exception:
        return False
    try:
        keyring.set_password(VAULT_SERVICE, VAULT_USER, key.decode("ascii"))
        return True
    except Exception:
        return False


def vault_key(home: Path | None = None) -> bytes:
    """Return the local vault key.

    Preferred storage is the OS keyring. If that is unavailable, CodexSwitch
    falls back to a local key file with restrictive permissions so secrets are
    still encrypted at rest, but without OS-backed protection.
    """
    env_key = os.environ.get("CODEXSWITCH_VAULT_KEY")
    if env_key:
        return env_key.encode("ascii")
    use_keyring = home is None or home == switch_home()
    if use_keyring:
        key = _key_from_keyring()
        if key:
            return key
    key_file = vault_key_path(home)
    if key_file.exists():
        return key_file.read_text().strip().encode("ascii")
    Fernet = _fernet()
    key = Fernet.generate_key()
    if use_keyring and _store_key_in_keyring(key):
        return key
    key_file.parent.mkdir(parents=True, exist_ok=True)
    _chmod_secret(key_file.parent, directory=True)
    key_file.write_text(key.decode("ascii") + "\n")
    _chmod_secret(key_file)
    return key


def remove_local_vault_material(home: Path | None = None) -> None:
    vault_path(home).unlink(missing_ok=True)
    vault_key_path(home).unlink(missing_ok=True)
    use_keyring = home is None or home == switch_home()
    if use_keyring:
        try:
            import keyring

            keyring.delete_password(VAULT_SERVICE, VAULT_USER)
        except Exception:
            pass


def vault_load(home: Path | None = None) -> dict:
    remote = remote_vault_enabled(home)
    cache_key = _vault_session_key(home)
    if remote:
        with _VAULT_SESSION_LOCK:
            if cache_key in _VAULT_SESSION_HOMES:
                if cache_key in _VAULT_SESSION_CACHE:
                    return copy.deepcopy(_VAULT_SESSION_CACHE[cache_key])
                if cache_key in _VAULT_SESSION_ERRORS:
                    raise RuntimeError(_VAULT_SESSION_ERRORS[cache_key])
    path = vault_path(home)
    try:
        token = remote_vault_request("GET", home=home) if remote else (
            path.read_bytes() if path.exists() else None
        )
    except Exception as exc:
        if remote:
            with _VAULT_SESSION_LOCK:
                if cache_key in _VAULT_SESSION_HOMES:
                    _VAULT_SESSION_ERRORS[cache_key] = str(exc)
        raise
    if token is None:
        data = {}
        if remote:
            with _VAULT_SESSION_LOCK:
                if cache_key in _VAULT_SESSION_HOMES:
                    _VAULT_SESSION_CACHE[cache_key] = data
        return {}
    Fernet = _fernet()
    try:
        key = remote_vault_key(home) if remote else vault_key(home)
        plaintext = Fernet(key).decrypt(token)
        data = json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        location = "remote credential vault" if remote else "credential vault"
        error = f"kan {location} niet openen: {type(exc).__name__}"
        if remote:
            with _VAULT_SESSION_LOCK:
                if cache_key in _VAULT_SESSION_HOMES:
                    _VAULT_SESSION_ERRORS[cache_key] = error
        raise RuntimeError(error) from exc
    data = data if isinstance(data, dict) else {}
    if remote:
        with _VAULT_SESSION_LOCK:
            if cache_key in _VAULT_SESSION_HOMES:
                _VAULT_SESSION_CACHE[cache_key] = copy.deepcopy(data)
                _VAULT_SESSION_ERRORS.pop(cache_key, None)
    return data


def vault_save(data: dict, home: Path | None = None) -> None:
    Fernet = _fernet()
    remote = remote_vault_enabled(home)
    key = remote_vault_key(home) if remote else vault_key(home)
    token = Fernet(key).encrypt(
        json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
    )
    if remote:
        remote_vault_request("PUT", token, home)
        cache_key = _vault_session_key(home)
        with _VAULT_SESSION_LOCK:
            if cache_key in _VAULT_SESSION_HOMES:
                _VAULT_SESSION_CACHE[cache_key] = copy.deepcopy(data)
                _VAULT_SESSION_ERRORS.pop(cache_key, None)
        return
    path = vault_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    _chmod_secret(path.parent, directory=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(token)
        _chmod_secret(tmp)
        os.replace(tmp, path)
        _chmod_secret(path)
    finally:
        tmp.unlink(missing_ok=True)


def vault_status(home: Path | None = None) -> dict[str, object]:
    if not remote_vault_enabled(home):
        return {"mode": "local", "online": True, "label": "LOCAL"}
    try:
        vault_load(home)
    except Exception as exc:
        return {
            "mode": "remote",
            "online": False,
            "label": "OFFLINE",
            "error": str(exc),
        }
    return {"mode": "remote", "online": True, "label": "ONLINE"}


def secret_id(path: Path, home: Path | None = None) -> str:
    path = path.expanduser()
    try:
        rel = path.relative_to(home or switch_home())
        return rel.as_posix()
    except ValueError:
        return base64.urlsafe_b64encode(str(path).encode("utf-8")).decode("ascii")


def read_secret_json(path: Path, default, home: Path | None = None):
    sid = secret_id(path, home)
    data = vault_load(home)
    if sid in data:
        return data[sid]
    if remote_vault_enabled(home):
        return default
    try:
        legacy = json.loads(path.read_text())
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        raise
    write_secret_json(path, legacy, home)
    return legacy


def write_secret_json(path: Path, value, home: Path | None = None) -> None:
    data = vault_load(home)
    data[secret_id(path, home)] = value
    vault_save(data, home)


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
