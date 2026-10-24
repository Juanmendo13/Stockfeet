# Builds a try-me zip of Stockfeet (app + setup). Does NOT bundle lc0.exe;
# Setup downloads the official GPL lc0 CPU build on first run.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root "pyproject.toml"))) {
  $root = $PSScriptRoot
  if (-not (Test-Path (Join-Path $root "pyproject.toml"))) {
    $root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
  }
}
Set-Location $root

$version = "0.0.0"
$outDir = Join-Path $root "dist"
$stage = Join-Path $outDir "Stockfeet-try"
$zip = Join-Path $outDir "Stockfeet-$version-try-windows.zip"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$copy = @(
  "stockfeet",
  "scripts",
  "tests",
  "assets",
  "pyproject.toml",
  "README.md",
  "TRY.md",
  "LICENSE",
  "NOTICE",
  ".env.example",
  "Setup Stockfeet.bat",
  "Abrir Stockfeet.bat",
  "Stockfeet.bat"
)
foreach ($item in $copy) {
  $src = Join-Path $root $item
  if (Test-Path $src) {
    Copy-Item -Path $src -Destination (Join-Path $stage $item) -Recurse -Force
  }
}

# Drop heavy / local-only data from the try zip
$drop = @(
  (Join-Path $stage "stockfeet\data\puzzles.sqlite"),
  (Join-Path $stage "stockfeet\data\human_book.sqlite"),
  (Join-Path $stage "stockfeet\__pycache__")
)
foreach ($p in $drop) {
  if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}
Get-ChildItem -Path $stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force
$size = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "Created $zip ($size MB)"
Write-Host "People unzip, run Setup Stockfeet.bat - downloads official lc0 CPU build."
