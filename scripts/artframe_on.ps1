# Turn the Art Frame back ON: re-enable the autostart tasks and start
# them now (staggered so the N150 isn't slammed), so you don't have to
# reboot. Run via artframe_on.bat (which requests admin), or directly:
#   powershell -ExecutionPolicy Bypass -File scripts\artframe_on.ps1

$admin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Error "Please run this as Administrator (use artframe_on.bat, or right-click PowerShell > Run as Administrator)."
    exit 1
}

Write-Host "Re-enabling Art Frame autostart tasks..." -ForegroundColor Cyan
Get-ScheduledTask "ArtFrame*" -ErrorAction SilentlyContinue |
    Enable-ScheduledTask | Out-Null

# Start in the same staggered order the boot sequence uses.
$order = @(
    @("ArtFrame ComfyUI",      12),
    @("ArtFrame Listener",      3),
    @("ArtFrame Display",       2),
    @("ArtFrame Kiosk",        10),
    @("ArtFrame Orchestrator",  0)
)
foreach ($item in $order) {
    $name, $wait = $item
    Write-Host "  starting $name" -ForegroundColor Green
    Start-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($wait -gt 0) { Start-Sleep -Seconds $wait }
}

Write-Host ""
Write-Host "Art Frame is ON. The kiosk should appear shortly." -ForegroundColor Green
