param(
    [string]$OutputRoot = '',
    [string]$WorkRoot = '',
    [string]$FFmpegLicensePath = '',
    [switch]$Overwrite,
    [switch]$KeepIntermediates
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
$buildSuccessful=$false
$buildAppArgs=@('-3.14','-m','PyInstaller','--noconfirm',
    '--distpath',(Join-Path $OutputRoot 'app'),
    '--workpath',(Join-Path $WorkRoot 'app'),$spec)
Push-Location $project
try {
    $appLog=Join-Path $WorkRoot 'app-build.log'
    $priorPreference=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    try {
        & $py.Source @buildAppArgs 2>&1 | ForEach-Object { $_.ToString() } | Set-Content -LiteralPath $appLog -Encoding UTF8
        $appExit=$LASTEXITCODE
    }
    finally { $ErrorActionPreference=$priorPreference }
    if($appExit -ne 0 -or -not(Test-Path $appOutput)){
        Get-Content -LiteralPath $appLog -Tail 15 -ErrorAction SilentlyContinue | Write-Warning
        throw 'Application packaging failed; setup not attempted'
    }
    # ffmpeg -L emits banner text on stderr and is NOT a reliable GPL license file.
    # Use the license supplied with the *same* binary build, not an empty log.
    $ffmpegCommand=Get-Command ffmpeg.exe -ErrorAction Stop
    $ffmpegItem=Get-Item -LiteralPath $ffmpegCommand.Source
    $ffmpegBinary=if($ffmpegItem.Target){[string]$ffmpegItem.Target[0]}else{$ffmpegItem.FullName}
    $ffmpegRoot=Split-Path -Parent (Split-Path -Parent $ffmpegBinary)
    if(-not $FFmpegLicensePath){$FFmpegLicensePath=Join-Path $ffmpegRoot 'LICENSE'}
    if(-not(Test-Path -LiteralPath $FFmpegLicensePath -PathType Leaf)){
        throw "Matching FFmpeg license not found: $FFmpegLicensePath"
    }
    $licenseText=Get-Content -LiteralPath $FFmpegLicensePath -Raw -Encoding UTF8
    if($licenseText.Length -lt 10000 -or $licenseText -notmatch '(?i)GNU GENERAL PUBLIC LICENSE'){
        throw 'Refusing a missing, empty or unexpected FFmpeg GPL license document'
    }
    $licenses=Join-Path $WorkRoot 'FFmpeg-LICENSE.txt'
    Copy-Item -LiteralPath $FFmpegLicensePath -Destination $licenses -Force
    if((Get-Item -LiteralPath $licenses).Length -lt 10000){
        throw 'Bundled FFmpeg license is unexpectedly short'
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
        (Join-Path $project 'THIRD_PARTY_NOTICES.txt'),
        $licenses,
        (Join-Path $project '00 - START HERE.txt'),
        (Join-Path $project 'stratum-download-studio.ico'),
        (Join-Path $project 'browser_extension')
    )
    foreach($file in $extras){
        if(-not(Test-Path $file)){ throw "Required setup asset missing: $file" }
        $setupArgs+='--add-data'
        $destination=if((Get-Item -LiteralPath $file).PSIsContainer){'browser_extension'}else{'.'}
        $setupArgs+=("$file;$destination")
    }
    $setupArgs+=(Join-Path $project 'scripts\ids_installer_gui.py')
    $setupLog=Join-Path $WorkRoot 'setup-build.log'
    $priorPreference=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    try {
        & $py.Source @setupArgs 2>&1 | ForEach-Object { $_.ToString() } | Set-Content -LiteralPath $setupLog -Encoding UTF8
        $setupExit=$LASTEXITCODE
    }
    finally { $ErrorActionPreference=$priorPreference }
    if($setupExit -ne 0 -or -not(Test-Path $setupOutput)){
        Get-Content -LiteralPath $setupLog -Tail 15 -ErrorAction SilentlyContinue | Write-Warning
        throw 'Setup packaging failed'
    }
    $buildSuccessful=$true
    Write-Output "PASS private staged release candidates: $appOutput and $setupOutput"
    Write-Output 'Unsigned staging only: sign, review bundled licenses, and pass owner browser acceptance before publishing.'
}
finally {
    Pop-Location
    # Keep a single installer after a successful build; regenerate intermediates
    # whenever needed. Never remove other files or delete a failed build's logs.
    if($buildSuccessful -and -not $KeepIntermediates){
        foreach($part in @('app','setup')){
            $generated=Join-Path $WorkRoot $part
            if(Test-Path -LiteralPath $generated){
                Remove-Item -LiteralPath $generated -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
        foreach($name in @('FFmpeg-LICENSE.txt','I-DS-Setup.spec','app-build.log','setup-build.log')){
            $artifact=Join-Path $WorkRoot $name
            if(Test-Path -LiteralPath $artifact){
                Remove-Item -LiteralPath $artifact -Force -ErrorAction SilentlyContinue
            }
        }
        $duplicates=Join-Path $OutputRoot 'app'
        if((Test-Path -LiteralPath $duplicates) -and
           (@(Get-ChildItem -LiteralPath $duplicates -Recurse -File -Force)).Count -eq 1 -and
           (Test-Path -LiteralPath $appOutput) -and
           (Test-Path -LiteralPath $setupOutput)){
            Remove-Item -LiteralPath $duplicates -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-Output 'Cleanup: generated work and duplicate app copy removed where verified; setup retained.'
    }
}
