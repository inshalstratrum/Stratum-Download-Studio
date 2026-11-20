param()
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$launcher = Join-Path $root 'START I-DS.pyw'
$icon = Join-Path $root 'stratum-download-studio.ico'
if (-not (Test-Path -LiteralPath $launcher) -or -not (Test-Path -LiteralPath $icon)) {
    throw 'I-DS GUI launcher or icon is missing'
}
$candidates = @(
    (Get-Command pythonw.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source),
    'C:\Python314\pythonw.exe',
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\pythonw.exe')
)
$pythonw = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $pythonw) {
    $pythonExe = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source
    if ($pythonExe) {
        $alternative = Join-Path (Split-Path -Parent $pythonExe) 'pythonw.exe'
        if (Test-Path -LiteralPath $alternative) { $pythonw = $alternative }
    }
}
if (-not $pythonw) {
    throw 'Pythonw (GUI version of Python) is unavailable. Install Python with GUI support.'
}
$linkPath = Join-Path $root '00 - OPEN I-DS.lnk'
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($linkPath)
$link.TargetPath = $pythonw
$link.Arguments = '"' + $launcher + '"'
$link.WorkingDirectory = $root
$link.IconLocation = $icon + ',0'
$link.Description = 'I-DS - I.os Download Support (no terminal)'
$link.WindowStyle = 1
$link.Save()
$check = $shell.CreateShortcut($linkPath)
if ($check.TargetPath -ne $pythonw -or -not (Test-Path -LiteralPath $linkPath)) {
    throw 'Could not verify saved I-DS shortcut'
}
Write-Output 'Created I-DS shortcut with product icon. Use 00 - OPEN I-DS.'
