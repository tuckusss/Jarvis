# JARVIS Windows release trust boundary.
# Developer CI can exercise an unsigned DRAFT candidate.
# Stable/public release MUST have a trusted code signature and matching publisher.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Installer,
    [Parameter(Mandatory)][string]$DistributionDir,
    [ValidateSet("development", "stable")][string]$Channel = "development",
    [string]$ExpectedPublisher = "",
    [string]$OutputManifest = ""
)
$ErrorActionPreference = "Stop"
$installerFile = (Resolve-Path $Installer).Path
$appDir = (Resolve-Path $DistributionDir).Path
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$appExe = Join-Path $appDir "JarvisDesktop.exe"
if (-not (Test-Path $appExe)) { throw "Packaged JARVIS app is missing" }
if ($installerFile -notmatch "JARVIS-Setup-\d+\.\d+\.\d+-x64\.exe$") {
    throw "Unexpected JARVIS installer filename"
}
$files = @(Get-Item $installerFile) + @(
    Get-ChildItem -Path $appDir -Recurse -File |
        Where-Object { $_.Extension.ToLowerInvariant() -in @('.exe', '.dll', '.pyd') }
)
if ($Channel -eq "stable" -and -not $ExpectedPublisher.Trim()) {
    throw "Stable build requires an explicitly configured publisher subject"
}
$unsigned = 0
$badSignatures = @()
$entries = @()
foreach ($item in $files) {
    $signature = Get-AuthenticodeSignature -FilePath $item.FullName
    $status = [string]$signature.Status
    if ($status -eq "NotSigned") { $unsigned++ }
    elseif ($status -ne "Valid") { $badSignatures += $item.FullName }
    if ($Channel -eq "stable") {
        if ($status -ne "Valid") { throw "Stable release contains an untrusted binary signature: $($item.Name)" }
        if ($item.FullName -in @($installerFile, $appExe)) {
            if (-not $signature.SignerCertificate -or
                $signature.SignerCertificate.Subject -ne $ExpectedPublisher) {
                throw "First-party binary does not match the expected publisher: $($item.Name)"
            }
        }
    }
    $entries += [ordered]@{
        file = $item.FullName.Substring($root.Length).TrimStart('\')
        bytes = [long]$item.Length
        sha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        signature_status = $status
    }
}
if ($badSignatures.Count -gt 0) {
    throw "Packaged binaries have invalid/untrusted signatures; investigate before any release"
}
if ($Channel -eq "stable" -and $unsigned -gt 0) {
    throw "Stable release cannot contain unsigned executable files"
}
$report = [ordered]@{
    channel = $Channel
    installer = (Split-Path $installerFile -Leaf)
    trusted_publisher_required = ($Channel -eq "stable")
    unsigned_binaries = $unsigned
    unsigned_allowed_for_development = ($Channel -ne "stable")
    files = $entries
}
if (-not $OutputManifest) {
    $OutputManifest = Join-Path (Split-Path $installerFile -Parent) "JARVIS-integrity.json"
}
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputManifest -Encoding utf8
if ($Channel -eq "development" -and $unsigned -gt 0) {
    Write-Warning "Development candidate is unsigned; do not distribute as trusted Windows software"
}
Write-Host "JARVIS_RELEASE_CHANNEL=$Channel"
Write-Host "JARVIS_UNSIGNED_BINARIES=$unsigned"
Write-Host "JARVIS_INTEGRITY_MANIFEST=$OutputManifest"
