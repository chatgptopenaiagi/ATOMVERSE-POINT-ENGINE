param([Parameter(Mandatory=$true)][string]$Python, [Parameter(Mandatory=$true)][string]$JavaHome, [string]$GradleCache)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not $env:ANDROID_HOME) { throw 'ANDROID_HOME must identify an existing verified SDK' }
$env:ATOMVERSE_BUILD_PYTHON=$Python
$env:JAVA_HOME=$JavaHome
if ($GradleCache) { $env:GRADLE_USER_HOME=$GradleCache }
$signingPath=Join-Path $projectRoot '.local/android-signing.properties'
if (-not (Test-Path -LiteralPath $signingPath)) {
    $env:ATOMVERSE_KEY_PASS=[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    & (Join-Path $JavaHome 'bin/keytool.exe') -genkeypair -keystore .local/atomverse-android.jks -storepass:env ATOMVERSE_KEY_PASS -keypass:env ATOMVERSE_KEY_PASS -alias atomverse -keyalg RSA -keysize 3072 -validity 3650 -dname 'CN=ATOMVERSE Point Engine' -noprompt
    if ($LASTEXITCODE -ne 0) { throw 'Signing key creation failed' }
    ('storePassword='+$env:ATOMVERSE_KEY_PASS) | Set-Content -LiteralPath $signingPath -Encoding ascii
    Remove-Item Env:ATOMVERSE_KEY_PASS
}
('sdk.dir='+$env:ANDROID_HOME.Replace('\','/')) | Set-Content -LiteralPath android/local.properties -Encoding ascii
& gradle -p android --no-daemon --console plain assembleRelease
if ($LASTEXITCODE -ne 0) { throw 'Android build failed' }
Write-Output 'Built signed ARM64 release candidate. Installation and execution verification are required before publication.'
