param([string]$Server='localhost',[string]$RuntimeLogin='')
$ErrorActionPreference='Stop'
$migration=Join-Path (Split-Path -Parent $PSScriptRoot) 'migrations/001_history.sql'
# Run from an account granted CREATE DATABASE on this SQL Server.
# This creates only the dedicated engine database and additive schema.
& sqlcmd -S $Server -E -C -l 5 -b -Q "IF DB_ID('ATOMVERSE_POINT_ENGINE') IS NULL CREATE DATABASE ATOMVERSE_POINT_ENGINE;"
if ($LASTEXITCODE -ne 0) { throw 'SQL administrator must provision the dedicated database; existing databases were not changed.' }
& sqlcmd -S $Server -E -C -l 5 -b -d ATOMVERSE_POINT_ENGINE -i $migration
if ($LASTEXITCODE -ne 0) { throw 'SQL schema migration failed' }
$migration2=Join-Path (Split-Path -Parent $PSScriptRoot) 'migrations/002_entity_state.sql'
& sqlcmd -S $Server -E -C -l 5 -b -d ATOMVERSE_POINT_ENGINE -i $migration2
if ($LASTEXITCODE -ne 0) { throw 'SQL schema 2 migration failed' }
if ($RuntimeLogin) {
    $loginLiteral=$RuntimeLogin.Replace("'","''")
    $loginIdentifier=$RuntimeLogin.Replace(']',']]')
    $grantSql=@"
IF SUSER_ID(N'$loginLiteral') IS NULL THROW 50001, 'Runtime login must already exist on this SQL Server.', 1;
IF DATABASE_PRINCIPAL_ID(N'$loginLiteral') IS NULL CREATE USER [$loginIdentifier] FOR LOGIN [$loginIdentifier];
GRANT SELECT, INSERT ON dbo.POINT_ENTITIES TO [$loginIdentifier];
GRANT SELECT, INSERT ON dbo.POINT_SESSIONS TO [$loginIdentifier];
GRANT SELECT, INSERT ON dbo.POINT_EVENTS TO [$loginIdentifier];
GRANT SELECT ON dbo.POINT_STATE_SAMPLES TO [$loginIdentifier];
GRANT SELECT ON dbo.POINT_COMMANDS TO [$loginIdentifier];
"@
    & sqlcmd -S $Server -E -C -l 5 -b -d ATOMVERSE_POINT_ENGINE -Q $grantSql
    if ($LASTEXITCODE -ne 0) { throw 'Dedicated database runtime-user grant failed' }
}
Write-Output 'Dedicated point-history database and schema are ready for the current Windows login.'
