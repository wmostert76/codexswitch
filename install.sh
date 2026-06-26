#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
TARGET_USER=$(id -un)
if [[ -n ${SUDO_USER:-} && "$SUDO_USER" != "root" ]]; then
  TARGET_USER=$SUDO_USER
fi
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
VENV="$PROJECT_ROOT/.venv"

if [[ -z "$TARGET_HOME" ]]; then
  echo "Could not determine home directory for $TARGET_USER" >&2
  exit 1
fi

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
