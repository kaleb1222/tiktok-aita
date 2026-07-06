# Sets up Windows Task Scheduler to auto-download new TikTok videos every hour.
# Run once as Administrator: Right-click PowerShell -> "Run as administrator" -> .\setup_scheduler.ps1

$TaskName = "TikTok AITA Video Downloader"
$ScriptPath = "$PSScriptRoot\download_videos.py"
$PythonPath = (Get-Command python -ErrorAction Stop).Source

$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $PSScriptRoot

# Run every hour (videos are generated 3x/day, this ensures quick pickup)
$Trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -Once -At (Get-Date)

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Register (or update if already exists)
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Limited `
    -Description "Downloads new TikTok AITA videos from GitHub Actions artifacts" | Out-Null

Write-Host "Scheduled task '$TaskName' created — runs every hour." -ForegroundColor Green
Write-Host "Videos will auto-download to: C:\Users\Kaleb\Downloads\tiktok aiti" -ForegroundColor Cyan
