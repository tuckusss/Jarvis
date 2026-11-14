# Windows CI integration check: install the ACTUAL setup EXE, verify installed payload,
# run bundled import check and a small offline inference, then uninstall. No microphone
# or interactive Windows session is assumed. End users do not run this script.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference = 'Stop'
$installerPath = (Resolve-Path $Installer).Path
$exeDir = Join-Path $env:LOCALAPPDATA 'Programs\JARVIS Desktop'
$exe = Join-Path $exeDir 'JarvisDesktop.exe'

function Invoke-Checked([string]$file, [string]$args, [string]$stage, [int]$timeoutSec=480) {
    Write-Host "$stage : $file $args"
    $p = Start-Process -FilePath $file -ArgumentList $args -PassThru -WindowStyle Hidden
    if (-not $p.WaitForExit($timeoutSec * 1000)) {
        try { $p.Kill() } catch {}
        throw "$stage timed out after $timeoutSec seconds"
    }
    if ($p.ExitCode -ne 0) { throw "$stage exited with $($p.ExitCode)" }
}

# Explicitly install without shortcuts/autostart and without running the GUI.
Invoke-Checked $installerPath '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /TASKS=""' 'Setup smoke install' 600
if (-not (Test-Path $exe)) { throw "Installed app executable missing: $exe" }

# Validate dependencies and large binary payload INSIDE the final installed folder.
Invoke-Checked $exe '--package-check' 'Installed import/model integrity check' 120
Invoke-Checked $exe '--offline-inference-check' 'Installed local AI inference check' 240

$localModel = Get-ChildItem $exeDir -Recurse -Filter 'qwen2.5-1.5b-instruct-q4_k_m.gguf' -File -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $localModel -or $localModel.Length -lt 500000000) { throw 'Installed offline AI model is missing/incomplete' }
$voskModel = Get-ChildItem $exeDir -Recurse -Filter 'final.mdl' -File -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $voskModel) { throw 'Installed Vosk speech model is missing' }

$uninstall = Join-Path $exeDir 'unins000.exe'
if (-not (Test-Path $uninstall)) { throw 'Uninstaller missing from installed app' }
Invoke-Checked $uninstall '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' 'Uninstall smoke check' 180
Write-Host 'ACTUAL WINDOWS SETUP SMOKE TEST PASSED' -ForegroundColor Green
