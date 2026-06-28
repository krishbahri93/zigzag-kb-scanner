<#
setup_schedule.ps1 — register the 3 daily Windows tasks for the always-on forward-tester.

Run ONCE from the repo root:
    powershell -ExecutionPolicy Bypass -File scripts\setup_schedule.ps1

It registers three daily Scheduled Tasks (as the current user, LogonType S4U so they run whether or
not you are logged in, no stored password; StartWhenAvailable so a sleeping PC catches up on wake):

  1. "ZZ Forward - Dhan token"  scripts\refresh_dhan_token.py        pre-market   (NSE token refresh)
  2. "ZZ Forward - India run"   scripts\forward_run.py --market india after NSE close (15:30 IST)
  3. "ZZ Forward - US run"      scripts\forward_run.py --market us    after US close (16:00 ET)

TRIGGER TIMES ARE YOUR MACHINE'S LOCAL CLOCK. Convert the market intent to local time and pass it:
    powershell -ExecutionPolicy Bypass -File scripts\setup_schedule.ps1 -TokenTime 08:30 -IndiaTime 15:45 -UsTime 16:30
The defaults assume the machine clock is IST. If your clock is US/Eastern, use the ET-local
equivalents (e.g. NSE close 15:30 IST = ~06:00 ET; US close 16:00 ET stays 16:00 ET → 16:30 run).

Each task appends stdout+stderr to data\forward\logs\<task>.log. Re-running this script updates the
tasks (it unregisters the same-named tasks first). Remove them with:
    Get-ScheduledTask -TaskName 'ZZ Forward*' | Unregister-ScheduledTask -Confirm:$false
#>
param(
    [string]$TokenTime = "08:30",   # local time to refresh the Dhan token (pre-market IST)
    [string]$IndiaTime = "15:45",   # local time to run the India forward test (after 15:30 IST)
    [string]$UsTime    = "16:30",   # local time to run the US forward test (after 16:00 ET)
    [string]$Python    = "python",  # python executable (full path if not on PATH)
    [string]$RepoDir   = (Resolve-Path "$PSScriptRoot\..").Path
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $RepoDir "data\forward\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Register-ForwardTask {
    param([string]$Name, [string]$Time, [string]$Script, [string]$ExtraArgs, [string]$Log)
    $scriptPath = Join-Path $RepoDir $Script
    $logPath = Join-Path $logDir $Log
    # cmd /c so we can append stdout+stderr to a log (Task Scheduler has no native redirection).
    $inner = "`"$Python`" `"$scriptPath`" $ExtraArgs >> `"$logPath`" 2>&1"
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $inner" -WorkingDirectory $RepoDir
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal | Out-Null
    Write-Host "  registered '$Name' daily at $Time  ->  $logPath"
}

Write-Host "Registering forward-tester tasks (repo: $RepoDir, python: $Python)"
Register-ForwardTask -Name "ZZ Forward - Dhan token" -Time $TokenTime `
    -Script "scripts\refresh_dhan_token.py" -ExtraArgs "" -Log "token.log"
Register-ForwardTask -Name "ZZ Forward - India run" -Time $IndiaTime `
    -Script "scripts\forward_run.py" -ExtraArgs "--market india" -Log "india.log"
Register-ForwardTask -Name "ZZ Forward - US run" -Time $UsTime `
    -Script "scripts\forward_run.py" -ExtraArgs "--market us" -Log "us.log"
Write-Host "Done. Verify: Get-ScheduledTask -TaskName 'ZZ Forward*'"
Write-Host "First India run needs a valid Dhan token + TOTP set up (see refresh_dhan_token.py)."
