$ErrorActionPreference = "Stop"

. "$PSScriptRoot\lib.ps1"

Write-Host "Logs: checking gateway error log, access log and service logs..." -ForegroundColor Cyan

function Get-ComposeContainerId {
  param(
    [Parameter(Mandatory=$true)][string]$Service
  )
  $id = docker compose ps -q $Service 2>$null
  if ($LASTEXITCODE -ne 0) { return $null }
  $id = ($id | Out-String).Trim()
  if ([string]::IsNullOrWhiteSpace($id)) { return $null }
  return $id
}

function Get-ContainerLogsFast {
  param(
    [Parameter(Mandatory=$true)][string]$Service,
    [int]$Tail = 120
  )
  $cid = Get-ComposeContainerId -Service $Service
  if (-not $cid) { return $null }

  $cmd = ('docker logs --tail {0} {1} 2>&1' -f $Tail, $cid)
  $txt = cmd /c $cmd
  return ($txt | Out-String)
}

$gatewayCid = Get-ComposeContainerId -Service "gateway_nginx"
if (-not $gatewayCid) {
  throw "gateway_nginx container id not found"
}

Write-Host "Logs: checking gateway error.log..." -ForegroundColor DarkCyan
$errorLog = docker exec $gatewayCid sh -c "tail -n 120 /var/log/nginx/error.log 2>/dev/null || true" 2>$null
$errorLog = ($errorLog | Out-String)

$badGatewayPatterns = @(
  'connect\(\) failed',
  'upstream prematurely closed connection',
  'no live upstreams',
  'host not found in upstream'
)

foreach ($pattern in $badGatewayPatterns) {
  if ($errorLog -match $pattern) {
    throw "gateway error.log contains bad pattern: $pattern"
  }
}

Write-Host "Logs: checking gateway access.log..." -ForegroundColor DarkCyan
# In many nginx container images /var/log/nginx/access.log is symlinked to /dev/stdout.
# Reading it via `docker exec tail -n ...` may block because it is not a regular file.
# For gateway access logs use container stdout via `docker logs` instead.
$accessLog = Get-ContainerLogsFast -Service "gateway_nginx" -Tail 400
$accessLog = ($accessLog | Out-String)
if ([string]::IsNullOrWhiteSpace($accessLog)) {
  throw "gateway access log stream is empty; expected recent traffic from regression checks"
}

$requiredAccessPatterns = @(
  '/api/v1/auth/login',
  '/api/openapi.json',
  '/ugc/',
  '/assistant/'
)
foreach ($pattern in $requiredAccessPatterns) {
  if ($accessLog -notmatch [regex]::Escape($pattern)) {
    throw "gateway access.log does not contain expected route: $pattern"
  }
}

$requiredStatuses = @(' 401 ', ' 403 ', ' 404 ', ' 422 ')
foreach ($statusChunk in $requiredStatuses) {
  if ($accessLog -notmatch [regex]::Escape($statusChunk)) {
    throw "gateway access.log does not contain expected negative status: $statusChunk"
  }
}

if ($accessLog -match 'rid=($|\s)') {
  throw "gateway access.log contains empty request id values"
}

$serverErrors = [regex]::Matches($accessLog, '"\s5\d\d\s').Count
if ($serverErrors -gt 0) {
  throw "gateway access.log contains 5xx responses: $serverErrors"
}

$services = @('auth_api','async_api','ugc_api','assistant_api')

$badServicePatterns = @(
  'Unhandled exception',
  'Outbox dispatcher tick failed',
  'env: ''bash\r''',
  'CRITICAL',
  'connect\(\) failed',
  '500 Internal Server Error'
)

foreach ($svc in $services) {
  Write-Host ("Logs: checking {0}..." -f $svc) -ForegroundColor DarkCyan
  $logText = Get-ContainerLogsFast -Service $svc -Tail 120

  if ([string]::IsNullOrWhiteSpace($logText)) {
    Write-Host ("Warning: no recent logs for {0}" -f $svc) -ForegroundColor Yellow
    continue
  }

  foreach ($pattern in $badServicePatterns) {
    if ($logText -match $pattern) {
      throw ("{0} logs contain bad pattern: {1}" -f $svc, $pattern)
    }
  }

}

Write-Host ""
Write-Host "Manual visual checks (optional, for defense/demo):" -ForegroundColor Yellow
Write-Host "  docker logs --tail 100 $gatewayCid 2>&1" -ForegroundColor Yellow
Write-Host "Confirm visually that request ids are present and routes/statuses look sane in gateway stdout." -ForegroundColor Yellow

Write-Host "Logs OK [OK]" -ForegroundColor Green
