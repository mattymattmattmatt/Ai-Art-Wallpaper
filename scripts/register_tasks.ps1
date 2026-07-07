# Registers all Art Frame components as Windows Scheduled Tasks that
# start automatically at logon. Run ONCE from an elevated PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\register_tasks.ps1
#
# Remove everything later with:
#   Get-ScheduledTask "ArtFrame*" | Unregister-ScheduledTask -Confirm:$false

$root = Split-Path -Parent $PSScriptRoot

function Register-ArtFrameTask {
    param([string]$Name, [string]$Script, [int]$DelaySeconds)
    $action  = New-ScheduledTaskAction -Execute "$root\scripts\$Script" -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $trigger.Delay = "PT$($DelaySeconds)S"
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 2) `
        -ExecutionTimeLimit (New-TimeSpan -Days 3650)
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger `
        -Settings $settings -Force | Out-Null
    Write-Host "registered $Name" -ForegroundColor Green
}

# Stagger startup so the little N150 isn't slammed at logon.
Register-ArtFrameTask "ArtFrame ComfyUI"      "start_comfyui.bat"      10
Register-ArtFrameTask "ArtFrame Listener"     "start_listener.bat"     20
Register-ArtFrameTask "ArtFrame Display"      "start_display.bat"      25
Register-ArtFrameTask "ArtFrame Orchestrator" "start_orchestrator.bat" 60
Register-ArtFrameTask "ArtFrame Kiosk"        "start_kiosk.bat"        40

Write-Host ""
Write-Host "All tasks registered. They will start at every logon." -ForegroundColor Cyan
Write-Host "Ollama autostarts via its own installer; verify with: ollama list"
