[CmdletBinding()]
param(
    [int]$Films = 100000,
    [int]$ChunkSize = 5000,
    [int]$DirectorPool = 20000,
    [int]$ActorPool = 40000,
    [int]$WriterPool = 20000,
    [switch]$WithoutBaseFixtures,
    [switch]$SkipRecreate
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$args = @(
    "exec", "-T", "async_api",
    "python", "scripts/generate_catalog_dataset.py",
    "--elastic-url", "http://elasticsearch:9200",
    "--films", "$Films",
    "--chunk-size", "$ChunkSize",
    "--director-pool", "$DirectorPool",
    "--actor-pool", "$ActorPool",
    "--writer-pool", "$WriterPool"
)

if ($WithoutBaseFixtures) {
    $args += "--without-base-fixtures"
}
if ($SkipRecreate) {
    $args += "--skip-recreate"
}

Write-Host "Generating synthetic catalog inside async_api container..." -ForegroundColor Cyan
Write-Host ("Films={0}; ChunkSize={1}; Directors={2}; Actors={3}; Writers={4}" -f $Films, $ChunkSize, $DirectorPool, $ActorPool, $WriterPool) -ForegroundColor DarkCyan

docker compose @args
