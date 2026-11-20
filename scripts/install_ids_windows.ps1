param(
  [string]$SourceExe = (Join-Path $PSScriptRoot 'I-DS.exe'),
  [string]$InstallRoot = '',
  [string]$ShortcutsRoot = '',
  [string]$DesktopRoot = '',
  [switch]$NoLaunch,
  [switch]$Upgrade
)
$ErrorActionPreference='Stop'
$testMode = -not [string]::IsNullOrWhiteSpace($env:I_DS_TEST_INSTALLROOT)
if ($testMode) {
  $InstallRoot=$env:I_DS_TEST_INSTALLROOT
  $ShortcutsRoot=$env:I_DS_TEST_SHORTCUTSROOT
  $DesktopRoot=$env:I_DS_TEST_DESKTOPROOT
  $NoLaunch=$true
}
if (-not $InstallRoot) { $InstallRoot=Join-Path $env:LOCALAPPDATA 'Programs\I-DS' }
if (-not $ShortcutsRoot) { $ShortcutsRoot=Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs' }
if (-not $testMode -and -not $DesktopRoot) { $DesktopRoot=[Environment]::GetFolderPath('DesktopDirectory') }
$extensionSource=Join-Path $PSScriptRoot 'browser_extension'
if (-not $testMode -and -not (Test-Path -LiteralPath (Join-Path $extensionSource 'manifest.json'))) {
  throw 'The browser extension is missing from this setup. Please use a complete I-DS installer.'
}
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
if(Test-Path -LiteralPath (Join-Path $extensionSource 'manifest.json')){
  $extensionTarget=Join-Path $InstallRoot 'Browser Extension'
  $icons=Join-Path $extensionSource 'icons'
  if(-not(Test-Path -LiteralPath $icons)){throw 'Browser extension icons were not packaged'}
  New-Item -ItemType Directory -Path $extensionTarget -Force | Out-Null
  foreach($name in @('manifest.json','background.js','content.js','media_candidates.js','file_interception.js','options.html','options.js','README.md')){
    $path=Join-Path $extensionSource $name
    if(-not(Test-Path -LiteralPath $path)){throw "Missing packaged extension file: $name"}
    Copy-Item -LiteralPath $path -Destination (Join-Path $extensionTarget $name) -Force
  }
  Copy-Item -LiteralPath $icons -Destination $extensionTarget -Recurse -Force
  if(-not(Test-Path -LiteralPath (Join-Path $extensionTarget 'manifest.json'))){throw 'Extension installation verification failed'}
}
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
# Use the Windows shell's actual Desktop folder (also handles OneDrive redirection).
if($DesktopRoot -and (Test-Path -LiteralPath $DesktopRoot -PathType Container)){
  $desktopLink=Join-Path $DesktopRoot 'I-DS Download Support.lnk'
  $canWrite=$true
  if(Test-Path -LiteralPath $desktopLink){
    $existing=$shell.CreateShortcut($desktopLink)
    if($existing.TargetPath -ne $target){$canWrite=$false;Write-Output 'Preserved unrelated desktop shortcut with the same name'}
  }
  if($canWrite){
    $desktopShortcut=$shell.CreateShortcut($desktopLink)
    $desktopShortcut.TargetPath=$target
    $desktopShortcut.WorkingDirectory=$InstallRoot
    $desktopShortcut.IconLocation="$target,0"
    $desktopShortcut.Description='I-DS | I.os Download Support'
    $desktopShortcut.Save()
    if($shell.CreateShortcut($desktopLink).TargetPath -ne $target){throw 'Desktop shortcut verification failed'}
  }
}else{Write-Output 'No existing Windows Desktop folder was available; Start Menu shortcut still installed'}
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
