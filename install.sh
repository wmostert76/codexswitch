#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
TARGET_USER=$(id -un)
if [[ -n ${SUDO_USER:-} && "$SUDO_USER" != "root" ]]; then
  TARGET_USER=$SUDO_USER
fi
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
VENV="$PROJECT_ROOT/.venv"
SKIP_SELF_UPDATE=0
for arg in "$@"; do
  case "$arg" in
    --no-self-update) SKIP_SELF_UPDATE=1 ;;
    *)
      echo "Unknown install option: $arg" >&2
      echo "Usage: ./install.sh [--no-self-update]" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$TARGET_HOME" ]]; then
  echo "Could not determine home directory for $TARGET_USER" >&2
  exit 1
fi

SUDO=()
if [[ $(id -u) -ne 0 ]]; then
  SUDO=(sudo)
fi

maybe_self_update() {
  if [[ "$SKIP_SELF_UPDATE" -eq 1 ]]; then
    return
  fi
  if ! command -v git >/dev/null 2>&1; then
    return
  fi
  if ! git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return
  fi
  local branch before after
  branch=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD)
  if [[ "$branch" == "HEAD" ]]; then
    echo "Detached git checkout detected; skipping installer self-update"
    return
  fi
  if [[ -n "$(git -C "$PROJECT_ROOT" status --porcelain)" ]]; then
    echo "Local repository has uncommitted changes; skipping installer self-update" >&2
    echo "Commit/stash changes first, then run ./install.sh again." >&2
    return
  fi
  before=$(git -C "$PROJECT_ROOT" rev-parse HEAD)
  echo "Checking CodexSwitch updates for $branch..."
  git -C "$PROJECT_ROOT" fetch --tags origin
  if [[ "$branch" == "main" ]]; then
    git -C "$PROJECT_ROOT" pull --ff-only origin main
  else
    git -C "$PROJECT_ROOT" pull --ff-only
  fi
  after=$(git -C "$PROJECT_ROOT" rev-parse HEAD)
  if [[ "$before" != "$after" ]]; then
    echo "CodexSwitch updated; restarting installer..."
    exec bash "$PROJECT_ROOT/install.sh" --no-self-update
  fi
}

detect_package_manager() {
  for manager in apt-get dnf yum pacman zypper apk; do
    if command -v "$manager" >/dev/null 2>&1; then
      echo "$manager"
      return 0
    fi
  done
  return 1
}

install_packages() {
  local manager=$1
  shift
  if [[ ${#SUDO[@]} -eq 1 ]] && ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required to install missing dependencies" >&2
    exit 1
  fi
  case "$manager" in
    apt-get)
      "${SUDO[@]}" apt-get update
      "${SUDO[@]}" apt-get install -y "$@"
      ;;
    dnf)
      "${SUDO[@]}" dnf install -y "$@"
      ;;
    yum)
      "${SUDO[@]}" yum install -y "$@"
      ;;
    pacman)
      "${SUDO[@]}" pacman -Sy --needed --noconfirm "$@"
      ;;
    zypper)
      "${SUDO[@]}" zypper --non-interactive install "$@"
      ;;
    apk)
      "${SUDO[@]}" apk add --no-cache "$@"
      ;;
  esac
}

ensure_system_dependencies() {
  local manager packages=()
  manager=$(detect_package_manager || true)
  if [[ -z "$manager" ]]; then
    echo "No supported package manager found; install python3, venv, nodejs and npm manually" >&2
    exit 1
  fi

  if ! command -v python3 >/dev/null 2>&1 || ! python3 -m venv --help >/dev/null 2>&1; then
    case "$manager" in
      apt-get) packages+=(python3 python3-venv python3-pip) ;;
      dnf|yum) packages+=(python3 python3-pip) ;;
      pacman) packages+=(python python-pip python-virtualenv) ;;
      zypper) packages+=(python3 python3-pip python3-venv) ;;
      apk) packages+=(python3 py3-pip py3-virtualenv) ;;
    esac
  fi
  if ! command -v npm >/dev/null 2>&1; then
    case "$manager" in
      pacman|apk) packages+=(nodejs npm) ;;
      *) packages+=(nodejs npm) ;;
    esac
  fi
  if ! command -v curl >/dev/null 2>&1; then
    packages+=(curl)
  fi
  if [[ ${#packages[@]} -gt 0 ]]; then
    echo "Installing missing system dependencies: ${packages[*]}"
    install_packages "$manager" "${packages[@]}"
  fi
}

ensure_codex_cli() {
  if command -v codex >/dev/null 2>&1; then
    codex update || true
    return
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required to install Codex CLI" >&2
    exit 1
  fi
  echo "Installing Codex CLI via npm"
  "${SUDO[@]}" npm install -g @openai/codex
}

maybe_self_update
ensure_system_dependencies
ensure_codex_cli

echo "Installing CodexSwitch for $TARGET_USER"
if [[ $(id -u) -eq 0 && "$TARGET_USER" != "root" ]]; then
  sudo -u "$TARGET_USER" python3 -m venv "$VENV"
  sudo -u "$TARGET_USER" "$VENV/bin/pip" install --upgrade pip
  sudo -u "$TARGET_USER" "$VENV/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"
else
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip
  "$VENV/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"
fi

sudo install -d -m 755 /usr/local/bin
for command in codexswitch codex-opencode-go-proxy opencode-go-token openrouter-token; do
  sudo ln -sfn "$PROJECT_ROOT/bin/$command" "/usr/local/bin/$command"
done
sudo rm -f /usr/local/bin/openswitch

service_file=$(mktemp)
trap 'rm -f "$service_file"' EXIT
cat >"$service_file" <<EOF
[Unit]
Description=CodexSwitch OpenCode Go compatibility proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$TARGET_USER
Group=$(id -gn "$TARGET_USER")
Environment=HOME=$TARGET_HOME
ExecStart=/usr/local/bin/codex-opencode-go-proxy
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo install -m 644 "$service_file" /etc/systemd/system/codex-opencode-go-proxy.service
sudo systemctl daemon-reload
sudo systemctl enable --now codex-opencode-go-proxy.service
sudo systemctl restart codex-opencode-go-proxy.service

echo
echo "Installed. Start with: codexswitch"
