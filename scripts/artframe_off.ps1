# Turn the Art Frame OFF and use the machine as a normal PC.
# Disables the autostart tasks so they won't come back on reboot, then
# stops everything currently running (kiosk browser, ComfyUI, the
# listener/display/orchestrator). Re-enable later with artframe_on.
#
# Run via artframe_off.bat (which requests admin), or directly from an
# elevated PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\artframe_off.ps1

$admin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Error "Please run this as Administrator (use artframe_off.bat, or right-click PowerShell > Run as Administrator)."
    exit 1
}

Write-Host "Disabling Art Frame autostart tasks..." -ForegroundColor Cyan
Get-ScheduledTask "ArtFrame*" -ErrorAction SilentlyContinue | ForEach-Object {
    Disable-ScheduledTask -TaskName $_.TaskName | Out-Null
    Stop-ScheduledTask    -TaskName $_.TaskName -ErrorAction SilentlyContinue
}

Write-Host "Stopping running components..." -ForegroundColor Cyan
# Kill detached processes the tasks launched: the kiosk browser, ComfyUI,
# and any lingering artframe python workers. Matched on command line so we
# never touch your normal Edge windows or unrelated Python.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and (
        $_.CommandLine -match '--kiosk' -or
        $_.CommandLine -match 'ComfyUI\\main\.py' -or
        $_.CommandLine -match 'artframe\.')
} | ForEach-Object {
    try {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
        Write-Host ("  stopped PID {0}" -f $_.ProcessId)
    } catch { }
}

Write-Host ""
Write-Host "Art Frame is OFF. The machine is yours." -ForegroundColor Green
Write-Host "It will stay off across reboots until you run artframe_on."
