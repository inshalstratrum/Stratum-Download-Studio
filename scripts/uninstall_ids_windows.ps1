param([string]$InstallRoot='', [string]$ShortcutsRoot='')
$ErrorActionPreference='Stop'
$testMode = -not [string]::IsNullOrWhiteSpace($env:I_DS_TEST_INSTALLROOT)
if ($testMode) {
  $InstallRoot=$env:I_DS_TEST_INSTALLROOT
  $ShortcutsRoot=$env:I_DS_TEST_SHORTCUTSROOT
}
if (-not $InstallRoot) { $InstallRoot=Split-Path -Parent $PSCommandPath }
if (-not $ShortcutsRoot) { $ShortcutsRoot=Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs' }
$target=Join-Path $InstallRoot 'I-DS.exe'
$shell=New-Object -ComObject WScript.Shell
foreach($name in @('I-DS Download Support.lnk','Uninstall I-DS.lnk')) {
  $path=Join-Path $ShortcutsRoot $name
  if (-not (Test-Path -LiteralPath $path)) {continue}
  $shortcut=$shell.CreateShortcut($path)
  $expected=if($name -eq 'I-DS Download Support.lnk'){$target}else{Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'}
  if ($shortcut.TargetPath -eq $expected) { Remove-Item -LiteralPath $path -Force }
}
foreach($name in @('I-DS.exe','I-DS.previous.exe','Uninstall I-DS.ps1','README - START HERE.txt','THIRD_PARTY_NOTICES.txt','FFmpeg-LICENSE.txt','LICENSE.txt')) {
  $path=Join-Path $InstallRoot $name
  if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path -Force}
}
Write-Output 'I-DS program removed; user downloads and settings were preserved.'
