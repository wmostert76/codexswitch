param(
    [string] $ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
)

$ErrorActionPreference = "Stop"
$out = Join-Path $ProjectRoot "dist"
New-Item -ItemType Directory -Force $out | Out-Null

$targets = @(
    @{ GOOS = "windows"; GOARCH = "amd64"; Name = "codexswitch-windows-amd64.exe" },
    @{ GOOS = "linux"; GOARCH = "amd64"; Name = "codexswitch-linux-amd64" },
    @{ GOOS = "linux"; GOARCH = "arm64"; Name = "codexswitch-linux-arm64" },
    @{ GOOS = "darwin"; GOARCH = "amd64"; Name = "codexswitch-darwin-amd64" },
    @{ GOOS = "darwin"; GOARCH = "arm64"; Name = "codexswitch-darwin-arm64" }
)

foreach ($target in $targets) {
    $env:GOOS = $target.GOOS
    $env:GOARCH = $target.GOARCH
    $output = Join-Path $out $target.Name
    go build -trimpath -ldflags "-s -w" -o $output "$ProjectRoot\cmd\codexswitch"
    Write-Host "built $output"
}

Remove-Item Env:\GOOS -ErrorAction SilentlyContinue
Remove-Item Env:\GOARCH -ErrorAction SilentlyContinue
