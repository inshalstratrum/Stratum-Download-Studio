param([string]$InstallRoot='', [string]$ShortcutsRoot='', [string]$DesktopRoot='')
$ErrorActionPreference='Stop'
$testMode = -not [string]::IsNullOrWhiteSpace($env:I_DS_TEST_INSTALLROOT)
if ($testMode) {
  $InstallRoot=$env:I_DS_TEST_INSTALLROOT
  $ShortcutsRoot=$env:I_DS_TEST_SHORTCUTSROOT
  $DesktopRoot=$env:I_DS_TEST_DESKTOPROOT
}
if (-not $InstallRoot) { $InstallRoot=Split-Path -Parent $PSCommandPath }
if (-not $ShortcutsRoot) { $ShortcutsRoot=Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs' }
if (-not $testMode -and -not $DesktopRoot) { $DesktopRoot=[Environment]::GetFolderPath('DesktopDirectory') }
$target=Join-Path $InstallRoot 'I-DS.exe'
$shell=New-Object -ComObject WScript.Shell
foreach($name in @('I-DS Download Support.lnk','Uninstall I-DS.lnk')) {
  $path=Join-Path $ShortcutsRoot $name
  if (-not (Test-Path -LiteralPath $path)) {continue}
  $shortcut=$shell.CreateShortcut($path)
  $expected=if($name -eq 'I-DS Download Support.lnk'){$target}else{Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'}
  if ($shortcut.TargetPath -eq $expected) { Remove-Item -LiteralPath $path -Force }
}
if($DesktopRoot -and (Test-Path -LiteralPath $DesktopRoot -PathType Container)){
  $desktopLink=Join-Path $DesktopRoot 'I-DS Download Support.lnk'
  if(Test-Path -LiteralPath $desktopLink){
    $shortcut=$shell.CreateShortcut($desktopLink)
    if($shortcut.TargetPath -eq $target){Remove-Item -LiteralPath $desktopLink -Force}
  }
}
# Remove owned browser companion files; leave any unrecognized custom files.
$extensionRoot=Join-Path $InstallRoot 'Browser Extension'
$extensionManifest=Join-Path $extensionRoot 'manifest.json'
if(Test-Path -LiteralPath $extensionManifest){
  $manifestText=Get-Content -LiteralPath $extensionManifest -Raw -ErrorAction SilentlyContinue
  if($manifestText -match 'I-DS Download Support'){
    foreach($name in @('manifest.json','background.js','content.js','media_candidates.js','file_interception.js','options.html','options.js','README.md')){
      $path=Join-Path $extensionRoot $name
      if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path -Force}
    }
    $icons=Join-Path $extensionRoot 'icons'
    if(Test-Path -LiteralPath $icons){
      foreach($name in @('i-ds-16.png','i-ds-32.png','i-ds-48.png','i-ds-128.png')){
        $icon=Join-Path $icons $name
        if(Test-Path -LiteralPath $icon){Remove-Item -LiteralPath $icon -Force}
      }
      if(-not @(Get-ChildItem -LiteralPath $icons -Force)){Remove-Item -LiteralPath $icons}
    }
    if(-not @(Get-ChildItem -LiteralPath $extensionRoot -Force)){Remove-Item -LiteralPath $extensionRoot}
  }
}
foreach($name in @('I-DS.exe','I-DS.previous.exe','Uninstall I-DS.ps1','README - START HERE.txt','THIRD_PARTY_NOTICES.txt','FFmpeg-LICENSE.txt','LICENSE.txt')) {
  $path=Join-Path $InstallRoot $name
  if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path -Force}
}
Write-Output 'I-DS program removed; user downloads and settings were preserved.'
