param(
    [string]$OutputRoot = '',
    [string]$WorkRoot = '',
    [switch]$Overwrite
)
$ErrorActionPreference='Stop'
$project=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if(-not $OutputRoot){$OutputRoot=Join-Path $project 'dist'}
if(-not $WorkRoot){$WorkRoot=Join-Path $project 'build\I-DS-release'}
$OutputRoot=[System.IO.Path]::GetFullPath($OutputRoot)
$WorkRoot=[System.IO.Path]::GetFullPath($WorkRoot)
$appOutput=Join-Path $OutputRoot 'app\I-DS.exe'
$setupOutput=Join-Path $OutputRoot 'I-DS-Setup.exe'
foreach($candidate in @($appOutput,$setupOutput)){
    if((Test-Path $candidate) -and -not $Overwrite){
        throw "Release candidate already exists: $candidate. Use -Overwrite only after verifying the prior result."
    }
}
New-Item -ItemType Directory -Force -Path $OutputRoot,$WorkRoot | Out-Null
$py=Get-Command py -ErrorAction Stop
$spec=Join-Path $project 'StratumDownloadStudio.spec'
$buildAppArgs=@('-3.14','-m','PyInstaller','--noconfirm',
    '--distpath',(Join-Path $OutputRoot 'app'),
    '--workpath',(Join-Path $WorkRoot 'app'),$spec)
Push-Location $project
try {
    & $py.Source @buildAppArgs
    if($LASTEXITCODE -ne 0 -or -not(Test-Path $appOutput)){
        throw 'Application packaging failed; setup not attempted'
    }
    $licenses=Join-Path $WorkRoot 'FFmpeg-LICENSE.txt'
    & ffmpeg -L | Out-File $licenses -Encoding UTF8
    if($LASTEXITCODE -ne 0 -or -not(Test-Path $licenses)){
        throw 'Cannot collect the FFmpeg distribution license'
    }
    $setupArgs=@('-3.14','-m','PyInstaller','--noconfirm','--onefile','--windowed',
        '--name','I-DS-Setup',
        '--icon',(Join-Path $project 'stratum-download-studio.ico'),
        '--distpath',$OutputRoot,
        '--workpath',(Join-Path $WorkRoot 'setup'),
        '--specpath',$WorkRoot)
    $extras=@(
        $appOutput,
        (Join-Path $project 'scripts\install_ids_windows.ps1'),
        (Join-Path $project 'scripts\uninstall_ids_windows.ps1'),
        (Join-Path $project 'LICENSE'),
        $licenses,
        (Join-Path $project '00 - START HERE.txt')
    )
    foreach($file in $extras){
        if(-not(Test-Path $file)){ throw "Required setup asset missing: $file" }
        $setupArgs+='--add-data'
        $setupArgs+=("$file;.")
    }
    $setupArgs+=(Join-Path $project 'scripts\ids_installer_gui.py')
    & $py.Source @setupArgs
    if($LASTEXITCODE -ne 0 -or -not(Test-Path $setupOutput)){
        throw 'Setup packaging failed'
    }
    Write-Output "PASS private staged release candidates: $appOutput and $setupOutput"
    Write-Output 'Unsigned staging only: sign, review bundled licenses, and pass owner browser acceptance before publishing.'
}
finally {
    Pop-Location
}
