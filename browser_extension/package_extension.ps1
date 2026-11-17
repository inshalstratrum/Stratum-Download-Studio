$ErrorActionPreference = 'Stop'

$extensionRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = Split-Path -Parent $extensionRoot
$firefoxRoot = Join-Path $repositoryRoot 'firefox_extension'
$packageRoot = Join-Path $repositoryRoot 'extension_packages'
$firefoxStage = Join-Path $packageRoot '.firefox-staging'
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

$sharedFiles = @(
    (Join-Path $extensionRoot 'media_candidates.js'),
    (Join-Path $extensionRoot 'file_interception.js'),
    (Join-Path $extensionRoot 'background.js'),
    (Join-Path $extensionRoot 'content.js'),
    (Join-Path $extensionRoot 'options.html'),
    (Join-Path $extensionRoot 'options.js')
)
$chromiumFiles = @((Join-Path $extensionRoot 'manifest.json')) +
    $sharedFiles +
    @((Join-Path $extensionRoot 'README.md'), (Join-Path $extensionRoot 'icons'))

$chromePackage = Join-Path $packageRoot 'i-ds-chrome.zip'
$edgePackage = Join-Path $packageRoot 'i-ds-edge.zip'
$firefoxPackage = Join-Path $packageRoot 'i-ds-firefox.zip'

Compress-Archive -LiteralPath $chromiumFiles -DestinationPath $chromePackage -CompressionLevel Optimal -Force
Compress-Archive -LiteralPath $chromiumFiles -DestinationPath $edgePackage -CompressionLevel Optimal -Force

try {
    if (Test-Path -LiteralPath $firefoxStage) {
        Remove-Item -LiteralPath $firefoxStage -Recurse -Force
    }
    New-Item -ItemType Directory -Path $firefoxStage | Out-Null
    Copy-Item -LiteralPath $sharedFiles -Destination $firefoxStage
    Copy-Item -LiteralPath (Join-Path $extensionRoot 'icons') -Destination (Join-Path $firefoxStage 'icons') -Recurse
    Copy-Item -LiteralPath (Join-Path $firefoxRoot 'manifest.json') -Destination (Join-Path $firefoxStage 'manifest.json')
    Copy-Item -LiteralPath (Join-Path $firefoxRoot 'README.md') -Destination (Join-Path $firefoxStage 'README.md')
    Compress-Archive -Path (Join-Path $firefoxStage '*') -DestinationPath $firefoxPackage -CompressionLevel Optimal -Force
} finally {
    if (Test-Path -LiteralPath $firefoxStage) {
        Remove-Item -LiteralPath $firefoxStage -Recurse -Force
    }
}

Write-Output $chromePackage
Write-Output $edgePackage
Write-Output $firefoxPackage
