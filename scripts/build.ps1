param([Parameter(Mandatory=$true)][string]$Python)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:PYINSTALLER_CONFIG_DIR=Join-Path $projectRoot '.local/pyinstaller-cache'
& $Python -m PyInstaller --noconfirm --windowed --onedir --name ATOMVERSE-POINT-ENGINE --paths src --exclude-module torch --exclude-module numpy --exclude-module matplotlib --exclude-module tkinter --exclude-module PyQt6 --distpath dist/candidate --workpath build/work --specpath build src/main.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Output 'Built dist/candidate/ATOMVERSE-POINT-ENGINE/ATOMVERSE-POINT-ENGINE.exe; verify before release.'
