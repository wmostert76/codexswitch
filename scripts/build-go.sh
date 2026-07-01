#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
OUT="$PROJECT_ROOT/dist"
mkdir -p "$OUT"

build() {
  local goos=$1
  local goarch=$2
  local name=$3
  GOOS=$goos GOARCH=$goarch go build \
    -trimpath \
    -ldflags "-s -w" \
    -o "$OUT/$name" \
    "$PROJECT_ROOT/cmd/codexswitch"
  echo "built $OUT/$name"
}

build windows amd64 codexswitch-windows-amd64.exe
build linux amd64 codexswitch-linux-amd64
build linux arm64 codexswitch-linux-arm64
build darwin amd64 codexswitch-darwin-amd64
build darwin arm64 codexswitch-darwin-arm64
