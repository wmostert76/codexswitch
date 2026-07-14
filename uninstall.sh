#!/usr/bin/env bash
set -euo pipefail

sudo systemctl disable --now codex-provider-proxy.service 2>/dev/null || true
sudo systemctl disable --now codex-opencode-go-proxy.service 2>/dev/null || true
sudo systemctl disable --now codex-openrouter-proxy.service 2>/dev/null || true
sudo systemctl disable --now codex-azure-proxy.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/codex-provider-proxy.service
sudo rm -f /etc/systemd/system/codex-opencode-go-proxy.service
sudo rm -f /etc/systemd/system/codex-openrouter-proxy.service
sudo rm -f /etc/systemd/system/codex-azure-proxy.service
sudo systemctl daemon-reload

for command in openswitch codexswitch codex-provider-proxy codex-opencode-go-proxy codex-openrouter-proxy codex-azure-proxy opencode-go-token openrouter-token; do
  sudo rm -f "/usr/local/bin/$command"
done

echo "CodexSwitch commands and proxy service removed."
echo "User configuration and credentials were left untouched."
