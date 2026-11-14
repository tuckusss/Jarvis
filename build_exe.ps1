# Legacy developer entry point, preserved for compatibility.
# This builds a single Windows SETUP installer, not a standalone script launcher.
$ErrorActionPreference = "Stop"
& "$PSScriptRoot\packaging\build_installer.ps1"
if ($LASTEXITCODE -ne 0) { throw "Installer build failed" }
