$ErrorActionPreference = 'Stop'

$extensionRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = Split-Path -Parent $extensionRoot
$packageRoot = Join-Path $repositoryRoot 'extension_packages'
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

$packageFiles = @(
    (Join-Path $extensionRoot 'manifest.json'),
    (Join-Path $extensionRoot 'background.js'),
    (Join-Path $extensionRoot 'options.html'),
    (Join-Path $extensionRoot 'options.js'),
    (Join-Path $extensionRoot 'README.md')
)

$chromePackage = Join-Path $packageRoot 'stratrum-download-studio-chrome.zip'
$edgePackage = Join-Path $packageRoot 'stratrum-download-studio-edge.zip'

Compress-Archive -LiteralPath $packageFiles -DestinationPath $chromePackage -CompressionLevel Optimal -Force
Compress-Archive -LiteralPath $packageFiles -DestinationPath $edgePackage -CompressionLevel Optimal -Force

Write-Output $chromePackage
Write-Output $edgePackage
