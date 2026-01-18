# Trakheesi Workers Installer for Windows

$ErrorActionPreference = "Stop"

$REPO = "refty-yapi/trakheesi-python-jobs-handler"
$INSTALL_DIR = "$env:USERPROFILE\trakheesi-workers"
$ZIP_URL = "https://github.com/$REPO/archive/refs/heads/main.zip"
$TEMP_ZIP = "$env:TEMP\trakheesi.zip"

Write-Host "=== Trakheesi Workers Installer ===" -ForegroundColor Cyan
Write-Host ""

# Install uv if not present
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
}

# Download and extract
Write-Host "Downloading..."
if (Test-Path $INSTALL_DIR) { Remove-Item -Recurse -Force $INSTALL_DIR }
Invoke-WebRequest -Uri $ZIP_URL -OutFile $TEMP_ZIP
Expand-Archive -Path $TEMP_ZIP -DestinationPath $env:TEMP -Force
Move-Item "$env:TEMP\trakheesi-python-jobs-handler-main" $INSTALL_DIR
Remove-Item $TEMP_ZIP

Set-Location $INSTALL_DIR

# Install dependencies
Write-Host "Installing dependencies..."
uv sync

# Install Playwright browsers
Write-Host "Installing Chromium browser..."
uv run playwright install chromium

Write-Host ""
Write-Host "=== Installation complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "To run:"
Write-Host "  cd $INSTALL_DIR"
Write-Host "  uv run python master.py -n 5 --visible"
Write-Host ""
