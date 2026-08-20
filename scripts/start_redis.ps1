<#
Starts the project-local Redis cache on Windows.

Prerequisite:
  winget install --id taizod1024.redis-windows-fork --exact

The script generates a runtime-only config with the correct local path. Redis is
bound to 127.0.0.1, so no password is required for this local development setup.
#>

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$redisDataDir = Join-Path $projectRoot 'data\redis'
New-Item -ItemType Directory -Force -Path $redisDataDir | Out-Null

function ConvertTo-CygwinPath([string] $windowsPath) {
    $fullPath = (Resolve-Path -LiteralPath $windowsPath).Path
    $drive = $fullPath.Substring(0, 1).ToLowerInvariant()
    $segments = $fullPath.Substring(3).Replace('\', '/')
    return "/cygdrive/$drive/$segments"
}

if (Get-NetTCPConnection -LocalPort 6379 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host 'Redis is already listening on 127.0.0.1:6379.'
    exit 0
}

$redisServer = (Get-Command redis-server -ErrorAction Stop).Source
$cygwinDataDir = ConvertTo-CygwinPath $redisDataDir
$configPath = Join-Path $redisDataDir 'redis.windows.conf'
$config = @"
bind 127.0.0.1
port 6379
protected-mode yes
dir $cygwinDataDir
dbfilename dump.rdb
appendonly yes
appendfilename appendonly.aof
appendfsync everysec
logfile $cygwinDataDir/redis.log
"@
[System.IO.File]::WriteAllText($configPath, $config, [System.Text.UTF8Encoding]::new($false))

Start-Process -FilePath $redisServer -ArgumentList (ConvertTo-CygwinPath $configPath) -WindowStyle Hidden
Start-Sleep -Seconds 2
if (-not (Get-NetTCPConnection -LocalPort 6379 -State Listen -ErrorAction SilentlyContinue)) {
    throw 'Redis did not start. Check data\redis\redis.log.'
}
Write-Host 'Redis started on 127.0.0.1:6379.'