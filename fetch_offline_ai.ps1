# Maintainer/CI ONLY. Downloads pin-verified, redistributable CPU runtime and GGUF model.
# The finished installer includes these resources and needs NO internet / API key to run.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $root 'assets\local_runtime'
$models  = Join-Path $root 'assets\models'
$licenses = Join-Path $root 'assets\licenses'
New-Item -ItemType Directory -Force -Path $runtime,$models,$licenses | Out-Null
$tag = 'b12336'
$archiveUrl = "https://github.com/ggml-org/llama.cpp/releases/download/$tag/llama-$tag-bin-win-cpu-x64.zip"
$archiveHash = 'e6734b9a11bc8b0b525922c49ce334fb6565d84df3786acb7d77b3e0a9acf4a3'
$modelUrl = 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf'
$modelHash = '6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e'
$modelFile = Join-Path $models 'qwen2.5-1.5b-instruct-q4_k_m.gguf'

function Get-VerifiedFile($url, $file, $expected) {
    if (Test-Path $file) {
        $digest = (Get-FileHash -Algorithm SHA256 $file).Hash.ToLowerInvariant()
        if ($digest -eq $expected) { Write-Host "Verified existing $file"; return }
        Remove-Item -Force $file
    }
    Write-Host "Downloading pinned asset: $url"
    & curl.exe --fail --location --retry 3 --connect-timeout 30 --output "$file.part" $url
    if ($LASTEXITCODE -ne 0) { Remove-Item "$file.part" -Force -ErrorAction SilentlyContinue; throw 'Download failed' }
    $actual = (Get-FileHash -Algorithm SHA256 "$file.part").Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        Remove-Item "$file.part" -Force -ErrorAction SilentlyContinue
        throw "SHA-256 MISMATCH. Expected $expected got $actual for $url"
    }
    Move-Item -Force "$file.part" $file
}

$archive = Join-Path $env:TEMP 'jarvis-pinned-llama-win-cpu-x64.zip'
Get-VerifiedFile $archiveUrl $archive $archiveHash
if (-not (Test-Path (Join-Path $runtime 'llama-server.exe'))) {
    $temp = Join-Path $env:TEMP ('jarvis-llama-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force $temp | Out-Null
    try {
        Expand-Archive -Path $archive -DestinationPath $temp -Force
        $server = Get-ChildItem $temp -Recurse -File -Filter 'llama-server.exe' | Select-Object -First 1
        if (-not $server) { throw 'The pinned llama.cpp archive has no llama-server.exe' }
        Copy-Item $server.FullName -Destination $runtime -Force
        # Keep its DLLs alongside its executable, to preserve the release runtime linkage.
        Get-ChildItem $server.Directory.FullName -File -Filter '*.dll' | Copy-Item -Destination $runtime -Force
    } finally { Remove-Item $temp -Force -Recurse -ErrorAction SilentlyContinue }
}
Get-VerifiedFile $modelUrl $modelFile $modelHash
# Licenses are part of the redistributable package.
& curl.exe --fail --location --retry 2 --output (Join-Path $licenses 'llama.cpp-MIT.txt') "https://raw.githubusercontent.com/ggml-org/llama.cpp/$tag/LICENSE"
if ($LASTEXITCODE -ne 0) { throw 'Could not retrieve llama.cpp redistribution license' }
& curl.exe --fail --location --retry 2 --output (Join-Path $licenses 'Qwen2.5-Apache-2.0.txt') 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/LICENSE'
if ($LASTEXITCODE -ne 0) { throw 'Could not retrieve Qwen redistribution license' }
if (-not (Test-Path (Join-Path $runtime 'llama-server.exe'))) { throw 'llama.cpp executable missing' }
if ((Get-Item $modelFile).Length -lt 500000000) { throw 'Offline GGUF model unexpectedly small' }
Write-Host 'Verified complete local AI runtime and model' -ForegroundColor Green
