param([Parameter(Mandatory=$true)][string]$Python)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:PYINSTALLER_CONFIG_DIR=Join-Path $projectRoot '.local/pyinstaller-cache'
$version=(Get-Content VERSION -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+-alpha\.\d+$') { throw 'Invalid build version' }
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$destination="dist/candidates/$version-$stamp"
if (Test-Path -LiteralPath $destination) { throw 'Build destination exists; refusing overwrite' }
& $Python -m PyInstaller --noconfirm --windowed --onedir --name ATOMVERSE-POINT-ENGINE --paths src --exclude-module torch --exclude-module numpy --exclude-module matplotlib --exclude-module tkinter --exclude-module PyQt6 --distpath $destination --workpath "build/$version" --specpath build src/main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
$application=Join-Path $destination 'ATOMVERSE-POINT-ENGINE'
Copy-Item -LiteralPath LICENSES -Destination $application -Recurse
foreach ($document in @('README.md','LICENSE-DECISION.md','THIRD-PARTY-NOTICES.md')) { if (Test-Path -LiteralPath $document) { Copy-Item -LiteralPath $document -Destination $application } }
(Join-Path $projectRoot "$application/ATOMVERSE-POINT-ENGINE.exe") | Set-Content .local/latest-build.txt
Write-Output "Built $application/ATOMVERSE-POINT-ENGINE.exe; verify before release. Previous builds were preserved."
