$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vsInstall=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsInstall) { throw 'No verified Visual C++ installation found' }
$vcvars=Join-Path $vsInstall 'VC/Auxiliary/Build/vcvars64.bat'
$nativeScript=Join-Path $projectRoot '.local/verify-native.cmd'
$content=@"
@echo off
call "$vcvars"
if errorlevel 1 exit /b 1
cd /d "$projectRoot\.local"
cl /nologo /EHsc /O2 "$projectRoot\scripts\probe_native.cpp" /Fe:probe-native.exe
if errorlevel 1 exit /b 2
probe-native.exe
if errorlevel 1 exit /b 3
nvcc -arch=sm_86 "$projectRoot\scripts\probe_cuda.cu" -o probe-cuda.exe
if errorlevel 1 exit /b 4
probe-cuda.exe
exit /b %errorlevel%
"@
$content | Set-Content -LiteralPath $nativeScript -Encoding ascii
$output=& cmd.exe /d /c $nativeScript 2>&1
$code=$LASTEXITCODE
$output | Set-Content -LiteralPath (Join-Path $projectRoot '.local/native-toolchain.log')
@{ measured=$true; exit_code=$code; cpp_pass=([bool]($output -match 'C\+\+ x64 trajectory arithmetic PASS')); cuda_pass=([bool]($output -match 'CUDA compiled kernel on real GPU PASS')); raw_log_private='.local/native-toolchain.log' } | ConvertTo-Json | Set-Content (Join-Path $projectRoot 'EVIDENCE/NATIVE-TOOLCHAIN.json')
Write-Output "Native toolchain bounded probe exit code: $code"
