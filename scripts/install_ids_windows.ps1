param(
  [string]$SourceExe = (Join-Path $PSScriptRoot 'I-DS.exe'),
  [string]$InstallRoot = '',
  [string]$ShortcutsRoot = '',
  [switch]$NoLaunch,
  [switch]$Upgrade
)
$ErrorActionPreference='Stop'
$testMode = -not [string]::IsNullOrWhiteSpace($env:I_DS_TEST_INSTALLROOT)
if ($testMode) {
  $InstallRoot=$env:I_DS_TEST_INSTALLROOT
  $ShortcutsRoot=$env:I_DS_TEST_SHORTCUTSROOT
  $NoLaunch=$true
}
if (-not $InstallRoot) { $InstallRoot=Join-Path $env:LOCALAPPDATA 'Programs\I-DS' }
if (-not $ShortcutsRoot) { $ShortcutsRoot=Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs' }
$SourceExe=(Resolve-Path -LiteralPath $SourceExe -ErrorAction Stop).Path
if ((Get-Item $SourceExe).Length -lt 1000000) { throw 'Installer source executable is incomplete' }
$target=Join-Path $InstallRoot 'I-DS.exe'
New-Item -ItemType Directory -Path $InstallRoot,$ShortcutsRoot -Force | Out-Null
if (Test-Path -LiteralPath $target) {
  $oldHash=(Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
  $newHash=(Get-FileHash -Algorithm SHA256 -LiteralPath $SourceExe).Hash
  if ($oldHash -ne $newHash) {
    if (-not $testMode -and -not $Upgrade) {
      $decision=Read-Host 'An existing I-DS installation was found. Type UPGRADE to back it up and replace it'
      if ($decision -ne 'UPGRADE') { throw 'Upgrade cancelled; prior installation preserved' }
    }
    Copy-Item -LiteralPath $target -Destination (Join-Path $InstallRoot 'I-DS.previous.exe') -Force
  }
}
Copy-Item -LiteralPath $SourceExe -Destination $target -Force
$sourceUninstall=Join-Path $PSScriptRoot 'uninstall_ids_windows.ps1'
if (Test-Path -LiteralPath $sourceUninstall) {
  Copy-Item -LiteralPath $sourceUninstall -Destination (Join-Path $InstallRoot 'Uninstall I-DS.ps1') -Force
}
foreach ($entry in @(
  @('LICENSE','LICENSE.txt'),
  @('THIRD_PARTY_NOTICES.txt','THIRD_PARTY_NOTICES.txt'),
  @('FFmpeg-LICENSE.txt','FFmpeg-LICENSE.txt'),
  @('README - START HERE.txt','README - START HERE.txt'),
  @('00 - START HERE.txt','README - START HERE.txt')
)) {
  $src=Join-Path $PSScriptRoot $entry[0]
  if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $InstallRoot $entry[1]) -Force }
}
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut((Join-Path $ShortcutsRoot 'I-DS Download Support.lnk'))
$shortcut.TargetPath=$target
$shortcut.WorkingDirectory=$InstallRoot
$shortcut.IconLocation="$target,0"
$shortcut.Description='I-DS | I.os Download Support'
$shortcut.Save()
$uninstall=Join-Path $InstallRoot 'Uninstall I-DS.ps1'
if (Test-Path -LiteralPath $uninstall) {
  $shortcut=$shell.CreateShortcut((Join-Path $ShortcutsRoot 'Uninstall I-DS.lnk'))
  $shortcut.TargetPath=(Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe')
  $shortcut.Arguments='-NoProfile -ExecutionPolicy Bypass -File "'+$uninstall+'"'
  $shortcut.WorkingDirectory=$InstallRoot
  $shortcut.IconLocation="$target,0"
  $shortcut.Description='Remove the I-DS app; preserve downloads and settings'
  $shortcut.Save()
}
$readback=$shell.CreateShortcut((Join-Path $ShortcutsRoot 'I-DS Download Support.lnk'))
if ($readback.TargetPath -ne $target -or -not (Test-Path $target)) { throw 'Installation verification failed' }
Write-Output ('PASS installed I-DS to '+$InstallRoot+'; shortcuts verified')
if (-not $NoLaunch) { Start-Process -FilePath $target -WorkingDirectory $InstallRoot }
