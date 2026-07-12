[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LockFile = Join-Path $RepositoryRoot "requirements-yt-dlp.lock"
$Target = Join-Path $RepositoryRoot ".deps"
$Staging = Join-Path $RepositoryRoot ".deps-staging"

if (Test-Path -LiteralPath $Staging) {
    Remove-Item -LiteralPath $Staging -Recurse -Force
}
New-Item -ItemType Directory -Path $Staging | Out-Null

try {
    & $Python -m pip --isolated install `
        --index-url https://pypi.org/simple `
        --require-hashes `
        --only-binary=:all: `
        --no-deps `
        --no-cache-dir `
        --target $Staging `
        --requirement $LockFile
    if ($LASTEXITCODE -ne 0) {
        throw "Hash-locked yt-dlp installation failed with exit code $LASTEXITCODE."
    }

    & $Python (Join-Path $RepositoryRoot "stratum_dependency_policy.py") $Staging
    if ($LASTEXITCODE -ne 0) {
        throw "Installed yt-dlp verification failed with exit code $LASTEXITCODE."
    }

    if (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Recurse -Force
    }
    Move-Item -LiteralPath $Staging -Destination $Target
    Write-Output "Controlled yt-dlp 2026.07.04 is ready in $Target"
}
finally {
    if (Test-Path -LiteralPath $Staging) {
        Remove-Item -LiteralPath $Staging -Recurse -Force
    }
}
