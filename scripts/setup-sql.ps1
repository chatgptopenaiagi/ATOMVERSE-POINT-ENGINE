param([string]$Server='localhost')
$ErrorActionPreference='Stop'
$migration=Join-Path (Split-Path -Parent $PSScriptRoot) 'migrations/001_history.sql'
# Run from an account granted CREATE DATABASE on this SQL Server.
# This creates only the dedicated engine database and additive schema.
& sqlcmd -S $Server -E -C -l 5 -b -Q "IF DB_ID('ATOMVERSE_POINT_ENGINE') IS NULL CREATE DATABASE ATOMVERSE_POINT_ENGINE;"
if ($LASTEXITCODE -ne 0) { throw 'SQL administrator must provision the dedicated database; existing databases were not changed.' }
& sqlcmd -S $Server -E -C -l 5 -b -d ATOMVERSE_POINT_ENGINE -i $migration
if ($LASTEXITCODE -ne 0) { throw 'SQL schema migration failed' }
Write-Output 'Dedicated point-history database and schema are ready for the current Windows login.'
