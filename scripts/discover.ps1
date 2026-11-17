param([string]$OutputRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$privateRoot = Join-Path $OutputRoot '.local'
New-Item -ItemType Directory -Force $privateRoot | Out-Null
$hardware = [ordered]@{
    measured_utc = [DateTime]::UtcNow.ToString('o')
    cpu = @(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed)
    ram = @(Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,ConfiguredClockSpeed)
    gpu = @(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion)
    nvidia = (& nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv,noheader | Out-String).Trim()
    memory_bandwidth = 'Measured separately by bounded numpy copy benchmark; DIMM clocks are not bandwidth measurements.'
}
$software = [ordered]@{
    measured_utc = [DateTime]::UtcNow.ToString('o')
    powershell = $PSVersionTable.PSVersion.ToString()
    cuda_compiler = (& nvcc --version | Out-String).Trim()
    cmake = (& cmake --version | Select-Object -First 1)
    ninja = (& ninja --version)
    odbc = @(Get-OdbcDriver | Where-Object Name -match 'ODBC Driver.*SQL Server' | Select-Object Name,Platform)
    sql_service_running = ((Get-Service MSSQLSERVER).Status -eq 'Running')
    sql_query = (& sqlcmd -S localhost -E -C -l 5 -h -1 -Q "SET NOCOUNT ON; SELECT CAST(SERVERPROPERTY('ProductVersion') AS varchar(30)), CAST(SERVERPROPERTY('Edition') AS varchar(100));" | Out-String).Trim()
    source_inspection = @('ATOMVERSE-AI: read only; no changes','COG: diagnostic history export available; not an engine dependency','ARX: existing inventory/report interface; not an engine dependency')
    runtime_verification = 'See CPU-GPU-PERFORMANCE, GUI-VERIFICATION, SQL-THROUGHPUT and QWEN-INFERENCE for actual bounded execution.'
}
$hardware | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $OutputRoot 'EVIDENCE/MISSION-001-HARDWARE-DISCOVERY.json')
$software | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $OutputRoot 'EVIDENCE/MISSION-001-SOFTWARE-DISCOVERY.json')
$private = @{ drives = @(Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free); tools = @(Get-Command python,git,gh,cmake,ninja,nvcc,sqlcmd,pwsh | Select-Object Name,Source) }
$private | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $privateRoot 'workstation-paths.json')
Write-Output 'Bounded hardware/software discovery written; private paths remain in .local.'
