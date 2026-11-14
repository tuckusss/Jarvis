# Windows CI checks the ACTUAL installer. Logs and progress snapshots are retained
# in Actions output so a failure can be diagnosed rather than hidden by a timeout.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Installer)

$ErrorActionPreference = 'Stop'
$installerPath = (Resolve-Path $Installer).Path
$exeDir = Join-Path $env:LOCALAPPDATA 'Programs\JARVIS Desktop'
$exe = Join-Path $exeDir 'JarvisDesktop.exe'
$logDir = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$installLog = Join-Path $logDir 'jarvis-installer-smoke.log'

function Show-InstallerLog([string]$path, [int]$lines=35) {
    if (Test-Path $path) {
        Write-Host "Recent Inno Setup log lines from $path :"
        Get-Content -LiteralPath $path -Tail $lines -ErrorAction SilentlyContinue |
          ForEach-Object { Write-Host $_ }
    } else {
        Write-Host "Installer has not produced a log at $path"
    }
}

function Invoke-Checked([string]$file, [string[]]$arguments, [string]$stage, [int]$timeoutSec=480, [string]$logPath='') {
    Write-Host "$stage : $file $($arguments -join ' ')"
    $p = Start-Process -FilePath $file -ArgumentList $arguments -PassThru -WindowStyle Hidden
    $elapsed = 0
    try {
        while (-not $p.WaitForExit(10000)) {
            $elapsed += 10
            if ($elapsed % 60 -eq 0) {
                Write-Host "$stage still running after $elapsed seconds; process ID $($p.Id)."
                if ($logPath) {
                    $events = @(Get-Content -LiteralPath $logPath -Tail 4 -ErrorAction SilentlyContinue)
                    foreach ($entry in $events) { Write-Host "[Inno] $entry" }
                }
                if (Test-Path $exeDir) {
                    $count = @(Get-ChildItem $exeDir -File -ErrorAction SilentlyContinue).Count
                    Write-Host "Installed top-level files visible: $count"
                }
            }
            if ($elapsed -ge $timeoutSec) {
                if ($logPath) { Show-InstallerLog $logPath 75 }
                throw "$stage exceeded $timeoutSec seconds; inspect the installer log above."
            }
        }
        if ($p.ExitCode -ne 0) {
            if ($logPath) { Show-InstallerLog $logPath 75 }
            throw "$stage exited with code $($p.ExitCode)"
        }
    } finally {
        if (-not $p.HasExited) {
            try { $p.Kill() } catch { }
        }
    }
}

# The earlier CI run timed out at 600 seconds during silent installation.
# 30 minutes accounts for model extraction and on-access virus scanning on CI.
# /LOG records progress, so this is a monitored timeout, not an infinite wait.
# No credentials, microphone or normal GUI interaction are needed for this test.
Invoke-Checked $installerPath @(
  '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
  "/LOG=$installLog"
) 'Setup smoke install' 1800 $installLog

if (-not (Test-Path $exe)) {
    Show-InstallerLog $installLog 75
    throw "Installed executable missing: $exe"
}
Write-Host "JARVIS Desktop installed successfully."

Invoke-Checked $exe @('--package-check') 'Installed package integrity check' 180
Invoke-Checked $exe @('--offline-voice-check') 'Installed neural TTS synthesis check' 240
Invoke-Checked $exe @('--offline-inference-check') 'Installed offline inference check' 360

$localModel = Get-ChildItem $exeDir -Recurse -Filter 'qwen2.5-1.5b-instruct-q4_k_m.gguf' -File -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $localModel -or $localModel.Length -lt 500000000) {
    throw 'Bundled offline AI model is missing or incomplete'
}
$voskModel = Get-ChildItem $exeDir -Recurse -Filter 'final.mdl' -File -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $voskModel) { throw 'Bundled Vosk speech model is missing' }

$uninstall = Join-Path $exeDir 'unins000.exe'
if (-not (Test-Path $uninstall)) { throw 'Uninstaller not present' }
Invoke-Checked $uninstall @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART') 'Uninstall smoke test' 360
Write-Host 'ACTUAL WINDOWS SETUP SMOKE TEST PASSED' -ForegroundColor Green
