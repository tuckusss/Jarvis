# CI/maintainer only: bundle a British neural TTS voice at build time.
# End users do not need to download models, register or install anything.
# Model and voice metadata URLs are immutable release assets and SHA256 pinned.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tts = Join-Path $root 'assets\tts'
$lic = Join-Path $root 'assets\licenses'
New-Item -ItemType Directory -Force -Path $tts,$lic | Out-Null

function Get-Verified([string]$url, [string]$file, [string]$expected) {
    if (Test-Path $file) {
        if ((Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expected) {
            Write-Host "Already verified: $file"; return
        }
        Remove-Item -Force $file
    }
    Write-Host "Downloading offline voice asset $url"
    & curl.exe --fail --location --retry 3 --connect-timeout 30 --output "$file.part" $url
    if ($LASTEXITCODE -ne 0) {
        Remove-Item "$file.part" -Force -ErrorAction SilentlyContinue
        throw "Neural voice download failed: $url"
    }
    $hash = (Get-FileHash "$file.part" -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $expected) {
        Remove-Item "$file.part" -Force -ErrorAction SilentlyContinue
        throw "Neural voice SHA256 mismatch for $url; expected $expected, got $hash"
    }
    Move-Item -Force "$file.part" $file
}

$release = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1'
Get-Verified "$release/kokoro-v1.0.int8.onnx" (Join-Path $tts 'kokoro-v1.0.int8.onnx') 'ae315a79b623f244700e4afb9246c46a26066782e049ba174bf3ba433970ee9c'
Get-Verified "$release/voices-v1.0.bin" (Join-Path $tts 'voices-v1.0.bin') 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d'

& curl.exe --fail --location --retry 2 --output (Join-Path $lic 'Kokoro-Apache-2.0.txt') 'https://www.apache.org/licenses/LICENSE-2.0.txt'
if ($LASTEXITCODE -ne 0) { throw 'Kokoro Apache 2.0 license retrieval failed' }
& curl.exe --fail --location --retry 2 --output (Join-Path $lic 'kokoro-onnx-MIT.txt') 'https://raw.githubusercontent.com/thewh1teagle/kokoro-onnx/main/LICENSE'
if ($LASTEXITCODE -ne 0) { throw 'Kokoro ONNX MIT license retrieval failed' }
Write-Host 'Verified neural speech model and British voice assets' -ForegroundColor Green
