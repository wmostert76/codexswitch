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
  git -C "$PROJECT_ROOT" fetch --no-tags origin
  if [[ "$branch" == "main" ]]; then
    git -C "$PROJECT_ROOT" pull --no-tags --ff-only origin main
  else
    git -C "$PROJECT_ROOT" pull --no-tags --ff-only
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
  if ! command -v go >/dev/null 2>&1; then
    case "$manager" in
      apt-get) packages+=(golang-go) ;;
      dnf|yum) packages+=(golang) ;;
      pacman) packages+=(go) ;;
      zypper) packages+=(go) ;;
      apk) packages+=(go) ;;
    esac
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

ensure_claude_cli() {
  if command -v claude >/dev/null 2>&1; then
    claude update || true
    return
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required to install Claude Code" >&2
    exit 1
  fi
  echo "Installing Claude Code via npm"
  "${SUDO[@]}" npm install -g @anthropic-ai/claude-code
}

maybe_self_update
ensure_system_dependencies
ensure_codex_cli
ensure_claude_cli

# A detached pre-upgrade proxy keeps its old Python modules in memory. Its
# argv may contain either the checkout path or the /usr/local/bin symlink, so
# match the command basename before installing the refreshed symlink.
pkill -f '(^|/)codex-provider-proxy($| )' 2>/dev/null || true

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

BUILD_DIR="$PROJECT_ROOT/.build"
PROXY_BUILD="$BUILD_DIR/codex-provider-proxy"
mkdir -p "$BUILD_DIR"
echo "Building the CodexSwitch Go provider proxy"
if [[ $(id -u) -eq 0 && "$TARGET_USER" != "root" ]]; then
  chown "$TARGET_USER" "$BUILD_DIR"
  sudo -u "$TARGET_USER" bash -c \
    'cd "$1" && CGO_ENABLED=0 GOCACHE="$2/go-cache" go build -trimpath -ldflags="-s -w" -o "$3" ./cmd/codexswitch-proxy' \
    _ "$PROJECT_ROOT" "$BUILD_DIR" "$PROXY_BUILD"
else
  (cd "$PROJECT_ROOT" && env CGO_ENABLED=0 GOCACHE="$BUILD_DIR/go-cache" \
    go build -trimpath -ldflags='-s -w' -o "$PROXY_BUILD" \
    ./cmd/codexswitch-proxy)
fi

sudo install -d -m 755 /usr/local/bin
sudo install -m 755 "$PROXY_BUILD" /usr/local/bin/codex-provider-proxy
for command in codexswitch codexswitch-azure-token codexswitch-claude-token codexswitch-provider-credential opencode-go-token; do
  sudo ln -sfn "$PROJECT_ROOT/bin/$command" "/usr/local/bin/$command"
done

# Replace a legacy per-user CodexSwitch binary that would otherwise shadow the
# canonical /usr/local/bin launcher. Preserve it as a backup for manual recovery.
legacy_user_command="$TARGET_HOME/.local/bin/codexswitch"
if [[ -f "$legacy_user_command" && ! -L "$legacy_user_command" ]]; then
  legacy_backup="$legacy_user_command.legacy-$(date +%Y%m%d-%H%M%S)"
  mv "$legacy_user_command" "$legacy_backup"
  ln -s "$PROJECT_ROOT/bin/codexswitch" "$legacy_user_command"
  echo "Preserved shadowing legacy launcher as: $legacy_backup"
fi
sudo rm -f /usr/local/bin/openswitch \
  /usr/local/bin/codex-opencode-go-proxy \
  /usr/local/bin/codex-openrouter-proxy \
  /usr/local/bin/codex-azure-proxy \
  /usr/local/bin/openrouter-token

for legacy_service in codex-opencode-go-proxy codex-openrouter-proxy codex-azure-proxy; do
  sudo systemctl disable --now "$legacy_service.service" 2>/dev/null || true
  sudo rm -f "/etc/systemd/system/$legacy_service.service"
done
sudo systemctl disable --now codex-provider-proxy.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/codex-provider-proxy.service
sudo systemctl daemon-reload

echo
echo "Installed. Start with: codexswitch"
echo "The provider proxy starts on demand for compatibility-backed launches."
