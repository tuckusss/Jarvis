# Windows developer/CI build only. End users run the generated JARVIS-Setup-*.exe.
[CmdletBinding()]
param(
    [switch]$SkipDependencyInstall,
    [string]$Version = "0.8.0"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

function Require-LastExit([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "$step failed with exit code $LASTEXITCODE" }
}

$python = "python"
if (-not $SkipDependencyInstall) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $python = "py"
        $pyPrefix = @("-3.12")
    } else {
        $pyPrefix = @()
    }
    & $python @pyPrefix -m pip install --upgrade pip
    Require-LastExit "pip upgrade"
    & $python @pyPrefix -m pip install -r requirements.txt 'pyinstaller>=6.10,<7'
    Require-LastExit "dependency install"
} else {
    $pyPrefix = @()
}

& $python @pyPrefix -m unittest discover -s tests -v
Require-LastExit "automated tests"

# Obtain the published, SHA-256-pinned offline Vosk wake-word model at BUILD time.
# End-users never download Python, Vosk, or select a model folder.
$voskModel = Join-Path $root 'assets\models\vosk-model-small-en-us-0.15'
& $python @pyPrefix -m jarvis.wake_model --destination $voskModel
Require-LastExit "verified Vosk model acquisition"
if (-not (Test-Path (Join-Path $voskModel 'am\final.mdl'))) {
    throw "Offline Vosk model incomplete; installer cannot be released"
}

# The release must include a REAL OFFLINE AI runtime and model, not a first-run
# Ollama dependency. Assets are verified against pinned upstream SHA-256 digests.
& (Join-Path $root 'packaging\fetch_offline_ai.ps1')
Require-LastExit "offline AI model/runtime acquisition"
& (Join-Path $root 'packaging\fetch_neural_voice.ps1')
Require-LastExit "verified offline neural speech acquisition"
if (-not (Test-Path (Join-Path $root 'assets\tts\kokoro-v1.0.int8.onnx'))) {
    throw "Offline neural voice model missing; refusing an incomplete installer"
}
$localServer = Join-Path $root 'assets\local_runtime\llama-server.exe'
$localModel = Join-Path $root 'assets\models\qwen2.5-1.5b-instruct-q4_k_m.gguf'
if (-not (Test-Path $localServer) -or -not (Test-Path $localModel)) {
    throw "Offline AI payload missing; do not publish a broken installer"
}

# One-folder bundle lives inside ONE self-contained installation EXE.
# This is more reliable than PyInstaller one-file temp extraction, and has faster startup.
$pyinstallerArgs = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
    "--name", "JarvisDesktop", "--icon", "assets\jarvis.ico",
    "--collect-all", "vosk",
    "--add-data", ("$voskModel;models/vosk-model-small-en-us-0.15"),
    "--add-data", ("$localModel;models"),
    "--add-data", ("$root\assets\licenses;licenses"),
    "--add-data", ("$root\assets\tts;tts"),
    "--collect-all", "kokoro_onnx",
    "--collect-all", "onnxruntime",
    "--collect-all", "phonemizer",
    "--collect-all", "language_tags",
    "--collect-all", "segments",
    "--collect-all", "csvw",
    "--collect-all", "clldutils",
    "--collect-all", "espeakng_loader",
    "--add-binary", ("$root\assets\local_runtime;local_runtime"),
    "--collect-all", "keyring",
    "--collect-all", "googleapiclient",
    "--collect-all", "google_auth_oauthlib",
    "--collect-all", "google.auth",
    "--collect-all", "pyttsx3",
    "--hidden-import", "pyttsx3.drivers.sapi5",
    "--collect-all", "sounddevice",
    "--collect-all", "comtypes",
    "main.py"
)
& $python @pyPrefix @pyinstallerArgs
Require-LastExit "PyInstaller bundle"
$exe = Join-Path $root "dist\JarvisDesktop\JarvisDesktop.exe"
if (-not (Test-Path $exe)) { throw "PyInstaller output not found: $exe" }

# An import-only smoke test runs even on CI without a desktop or microphone.
$p = Start-Process -FilePath $exe -ArgumentList '--package-check' -Wait -PassThru -WindowStyle Hidden

if ($p.ExitCode -ne 0) {
    $log = Join-Path $env:TEMP 'jarvis-package-error.log'
    if ($env:RUNNER_TEMP) { $log = Join-Path $env:RUNNER_TEMP 'jarvis-package-error.log' }
    if (Test-Path $log) { Get-Content $log -Tail 55 | ForEach-Object { Write-Host $_ } }
    throw "Packaged app import check failed (exit code $($p.ExitCode))"
}
$p = Start-Process -FilePath $exe -ArgumentList '--gui-smoke-check' -Wait -PassThru -WindowStyle Hidden
if ($p.ExitCode -ne 0) {
    $log = Join-Path $env:TEMP 'jarvis-gui-error.log'
    if ($env:RUNNER_TEMP) { $log = Join-Path $env:RUNNER_TEMP 'jarvis-gui-error.log' }
    if (Test-Path $log) { Get-Content $log -Tail 55 | ForEach-Object { Write-Host $_ } }
    throw "Packaged Settings UI smoke check failed (exit code $($p.ExitCode))"
}
$p = Start-Process -FilePath $exe -ArgumentList '--private-vault-check' -Wait -PassThru -WindowStyle Hidden
if ($p.ExitCode -ne 0) {
    $log = Join-Path $env:TEMP 'jarvis-private-vault-error.log'
    if ($env:RUNNER_TEMP) { $log = Join-Path $env:RUNNER_TEMP 'jarvis-private-vault-error.log' }
    if (Test-Path $log) { Get-Content $log -Tail 55 | ForEach-Object { Write-Host $_ } }
    throw "Packaged Windows DPAPI vault smoke check failed (exit code $($p.ExitCode))"
}
$p = Start-Process -FilePath $exe -ArgumentList '--offline-voice-check' -Wait -PassThru -WindowStyle Hidden

if ($p.ExitCode -ne 0) {
    $log = Join-Path $env:TEMP 'jarvis-voice-error.log'
    if ($env:RUNNER_TEMP) { $log = Join-Path $env:RUNNER_TEMP 'jarvis-voice-error.log' }
    if (Test-Path $log) { Get-Content $log -Tail 55 | ForEach-Object { Write-Host $_ } }
    throw "Packaged offline neural speech synthesis failed (exit code $($p.ExitCode))"
}

$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { $iscc = $cmd.Source }
}
if (-not $iscc) { throw "Inno Setup 6 is required on the BUILD PC. Install Inno Setup or use the GitHub Actions workflow. End users do NOT need Inno Setup." }

$env:JARVIS_SIGNING_READY = "0"
$cert = $null
$thumb = $null
$certWasAlreadyInstalled = $false
try {
    if ($env:JARVIS_SIGNING_PFX_BASE64 -and $env:JARVIS_SIGNING_PASSWORD) {
        $sdk = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
        $signtool = Get-ChildItem $sdk -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
            Sort-Object FullName -Descending | Select-Object -First 1
        if (-not $signtool) { throw "Windows SDK signtool.exe (x64) is needed for signed builds" }
        $tempPfx = Join-Path $env:TEMP ("jarvis-signing-" + [guid]::NewGuid().ToString("N") + ".pfx")
        try {
            [IO.File]::WriteAllBytes($tempPfx, [Convert]::FromBase64String($env:JARVIS_SIGNING_PFX_BASE64))
            $securePassword = ConvertTo-SecureString $env:JARVIS_SIGNING_PASSWORD -AsPlainText -Force
            $preExisting = @(Get-ChildItem 'Cert:\CurrentUser\My' | Select-Object -ExpandProperty Thumbprint)
            $cert = Import-PfxCertificate -FilePath $tempPfx -CertStoreLocation 'Cert:\CurrentUser\My' -Password $securePassword
            if (-not $cert) { throw "Signing certificate import failed" }
            $thumb = $cert.Thumbprint
            $certWasAlreadyInstalled = $thumb -in $preExisting
        } finally {
            Remove-Item $tempPfx -Force -ErrorAction SilentlyContinue
        }
        # Sign only unsigned binary payloads; retain third-party signatures where already valid.
        Get-ChildItem (Join-Path $root 'dist\JarvisDesktop') -Recurse -File |
            Where-Object { $_.Extension -in @('.exe','.dll','.pyd') } | ForEach-Object {
                $state = (Get-AuthenticodeSignature -FilePath $_.FullName).Status
                if ($state -eq 'NotSigned') {
                    & $signtool.FullName sign /sha1 $thumb /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $_.FullName
                    Require-LastExit "Sign $($_.Name)"
                } elseif ($state -ne 'Valid') {
                    throw "Bundled binary $($_.FullName) has invalid/unknown signature ($state); investigate before release."
                }
            }
        $env:JARVIS_SIGNING_READY = "1"
    } elseif ($env:JARVIS_SIGNING_PFX_BASE64 -or $env:JARVIS_SIGNING_PASSWORD) {
        throw "Both JARVIS_SIGNING_PFX_BASE64 and JARVIS_SIGNING_PASSWORD must be present for signing"
    } else {
        Write-Warning "Generating an UNSIGNED development installer. Windows Smart App Control may block it."
    }

    $env:JARVIS_VERSION = $Version
    $iss = Join-Path $root 'packaging\JARVIS.iss'
    if ($env:JARVIS_SIGNING_READY -eq '1') {
        # Inno Setup signs Setup, its temporary copies, and its uninstaller during compilation.
        $signCmd = '"' + $signtool.FullName + '" sign /sha1 ' + $thumb +
                   ' /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $f'
        & $iscc ("--signtool=jarvissign=" + $signCmd) $iss
    } else {
        & $iscc $iss
    }
    Require-LastExit "Inno Setup compilation"
    $output = Join-Path $root ("dist\JARVIS-Setup-" + $Version + "-x64.exe")
    if (-not (Test-Path $output)) { throw "Installer missing: $output" }
    if ($env:JARVIS_SIGNING_READY -eq '1') {
        $installerSignature = Get-AuthenticodeSignature -FilePath $output
        if ($installerSignature.Status -ne 'Valid') { throw "Installer Authenticode signature is not valid" }
    }
    Write-Host "Built $output" -ForegroundColor Green
} finally {
    $env:JARVIS_SIGNING_READY = "0"
    if ($cert -and -not $certWasAlreadyInstalled) { Remove-Item ("Cert:\CurrentUser\My\" + $thumb) -ErrorAction SilentlyContinue }
}
