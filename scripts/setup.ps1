# One-time Python environment setup for the Art Frame.
# Run from PowerShell in the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Creating virtual environment in .venv ..." -ForegroundColor Cyan
python -m venv .venv
if ($LASTEXITCODE -ne 0) { Write-Error "python not found — install Python 3.11 x64 first"; exit 1 }

Write-Host "Installing dependencies ..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed"; exit 1 }

Write-Host ""
Write-Host "Setup complete. Next steps:" -ForegroundColor Green
Write-Host "  1. List your microphones:  .venv\Scripts\python -m artframe.audio_listener --list-devices"
Write-Host "  2. Put your headset's name fragment into config.yaml -> audio.device_name"
Write-Host "  3. Follow docs\STAGE1_COMFYUI.md onward."
