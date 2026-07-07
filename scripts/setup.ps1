# One-time Python environment setup for the Art Frame.
# Run from PowerShell in the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Prefer Python 3.11 via the "py" launcher: several dependencies here
# (webrtcvad-wheels in particular) only ship prebuilt wheels up through
# 3.11/3.12, so a newer default "python" (e.g. 3.13/3.14) forces pip to
# compile from source and fail without Visual C++ Build Tools installed.
$pyArgs = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.11 --version *> $null
    if ($LASTEXITCODE -eq 0) { $pyArgs = @("py", "-3.11") }
}
if (-not $pyArgs -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $pyArgs = @("python")
}
if (-not $pyArgs) {
    Write-Error "Python not found. Install Python 3.11 (64-bit) from https://www.python.org/downloads/release/python-3119/ and check 'Add python.exe to PATH', then reopen PowerShell."
    exit 1
}
Write-Host "Using interpreter: $($pyArgs -join ' ')" -ForegroundColor Cyan

Write-Host "Creating virtual environment in .venv ..." -ForegroundColor Cyan
if ($pyArgs.Length -eq 2) { & $pyArgs[0] $pyArgs[1] -m venv .venv }
else { & $pyArgs[0] -m venv .venv }
if ($LASTEXITCODE -ne 0) { Write-Error "venv creation failed - is Python 3.11 (64-bit) installed?"; exit 1 }

Write-Host "Installing dependencies ..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed"; exit 1 }

Write-Host ""
Write-Host "Setup complete. Next steps:" -ForegroundColor Green
Write-Host "  1. List your microphones:  .venv\Scripts\python -m artframe.audio_listener --list-devices"
Write-Host "  2. Put your headset's name fragment into config.yaml -> audio.device_name"
Write-Host "  3. Follow docs\STAGE1_COMFYUI.md onward."
