param([Parameter(Mandatory=$true)][string]$Python, [ValidateSet('onedir','onefile')][string]$Mode='onedir')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:PYINSTALLER_CONFIG_DIR=Join-Path $projectRoot '.local/pyinstaller-cache'
$version=(Get-Content VERSION -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+-alpha\.\d+$') { throw 'Invalid build version' }
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$destination="dist/candidates/$version-$Mode-$stamp"
if (Test-Path -LiteralPath $destination) { throw 'Build destination exists; refusing overwrite' }
$name=if ($Mode -eq 'onefile') { "ATOMVERSE-POINT-ENGINE-$version-windows-x64" } else { 'ATOMVERSE-POINT-ENGINE' }
& $Python -m PyInstaller --noconfirm --windowed "--$Mode" --name $name --paths src --add-data "${projectRoot}/LICENSES:LICENSES" --add-data "${projectRoot}/THIRD-PARTY-NOTICES.md:." --add-data "${projectRoot}/LICENSE-DECISION.md:." --exclude-module torch --exclude-module numpy --exclude-module matplotlib --exclude-module tkinter --exclude-module PyQt6 --distpath $destination --workpath "build/$version-$Mode" --specpath build src/main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
if ($Mode -eq 'onefile') {
    (Join-Path $projectRoot "$destination/$name.exe") | Set-Content .local/latest-onefile.txt
    Write-Output "Built $destination/$name.exe; verify before release."
    exit 0
}
$application=Join-Path $destination 'ATOMVERSE-POINT-ENGINE'
Copy-Item -LiteralPath LICENSES -Destination $application -Recurse
foreach ($document in @('README.md','LICENSE-DECISION.md','THIRD-PARTY-NOTICES.md')) { if (Test-Path -LiteralPath $document) { Copy-Item -LiteralPath $document -Destination $application } }
(Join-Path $projectRoot "$application/ATOMVERSE-POINT-ENGINE.exe") | Set-Content .local/latest-build.txt
Write-Output "Built $application/ATOMVERSE-POINT-ENGINE.exe; verify before release. Previous builds were preserved."
