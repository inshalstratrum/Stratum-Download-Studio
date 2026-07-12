[CmdletBinding()]
param([string]$Python = "python")

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LockFile = Join-Path $RepositoryRoot "requirements-yt-dlp.lock"
$ToolManifest = Get-Content -Raw (Join-Path $RepositoryRoot "controlled-tools.json") | ConvertFrom-Json
$Deno = $ToolManifest.deno
$ExpectedUrl = "https://github.com/denoland/deno/releases/download/v$($Deno.version)/deno-x86_64-pc-windows-msvc.zip"
if ($Deno.official_release_url -cne $ExpectedUrl) { throw "The controlled Deno source is not allowlisted." }

$DependencyTarget = Join-Path $RepositoryRoot ".deps"
$ToolTarget = Join-Path $RepositoryRoot ".tools"
$DependencyStaging = Join-Path $RepositoryRoot ".deps-staging"
$ToolStaging = Join-Path $RepositoryRoot ".tools-staging"
$DependencyRollback = Join-Path $RepositoryRoot ".deps-rollback"
$ToolRollback = Join-Path $RepositoryRoot ".tools-rollback"
$Archive = Join-Path $ToolStaging "deno.zip"

foreach ($path in @($DependencyStaging, $ToolStaging)) {
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    New-Item -ItemType Directory -Path $path | Out-Null
}

$promotedDependencies = $false
$promotedTools = $false
try {
    & $Python -m pip --isolated install `
        --index-url https://pypi.org/simple `
        --require-hashes `
        --only-binary=:all: `
        --no-deps `
        --no-cache-dir `
        --disable-pip-version-check `
        --target $DependencyStaging `
        --requirement $LockFile
    if ($LASTEXITCODE -ne 0) { throw "The controlled media dependencies could not be installed." }

    Invoke-WebRequest -UseBasicParsing -Uri $Deno.official_release_url -OutFile $Archive
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToLowerInvariant() -cne $Deno.archive_sha256) {
        throw "The controlled Deno download failed integrity verification."
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        $members = @($zip.Entries | Where-Object { $_.FullName -and -not $_.FullName.EndsWith('/') })
        if ($members.Count -ne 1 -or $members[0].FullName -cne $Deno.expected_executable) {
            throw "The controlled Deno archive contains unexpected files."
        }
        $denoDirectory = Join-Path $ToolStaging "deno"
        New-Item -ItemType Directory $denoDirectory | Out-Null
        $destination = Join-Path $denoDirectory $Deno.expected_executable
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($members[0], $destination, $false)
    }
    finally { $zip.Dispose() }
    Remove-Item -LiteralPath $Archive -Force

    & $Python (Join-Path $RepositoryRoot "stratum_dependency_policy.py") $DependencyStaging $ToolStaging
    if ($LASTEXITCODE -ne 0) { throw "The controlled media capability verification failed." }

    foreach ($path in @($DependencyRollback, $ToolRollback)) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    }
    if (Test-Path -LiteralPath $DependencyTarget) { Move-Item $DependencyTarget $DependencyRollback }
    if (Test-Path -LiteralPath $ToolTarget) { Move-Item $ToolTarget $ToolRollback }
    Move-Item $DependencyStaging $DependencyTarget
    $promotedDependencies = $true
    Move-Item $ToolStaging $ToolTarget
    $promotedTools = $true
    Write-Output "Controlled yt-dlp 2026.07.04 capabilities and Deno $($Deno.version) are ready."
}
catch {
    if ($promotedDependencies -and (Test-Path $DependencyTarget)) { Remove-Item $DependencyTarget -Recurse -Force }
    if ($promotedTools -and (Test-Path $ToolTarget)) { Remove-Item $ToolTarget -Recurse -Force }
    if (Test-Path $DependencyRollback) { Move-Item $DependencyRollback $DependencyTarget }
    if (Test-Path $ToolRollback) { Move-Item $ToolRollback $ToolTarget }
    throw
}
finally {
    foreach ($path in @($DependencyStaging, $ToolStaging)) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    }
}
