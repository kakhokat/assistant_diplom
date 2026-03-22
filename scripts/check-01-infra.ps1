
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\lib.ps1"

Write-Host "Infra: checking compose status, health and published ports..." -ForegroundColor Cyan

$ids = @(docker compose ps -q)
if ($ids.Count -eq 0) {
  throw "No containers found. Did you run: docker compose up -d --build ?"
}

$bad = @()
$serviceNames = @()

foreach ($id in $ids) {
  $i = docker inspect $id | ConvertFrom-Json | Select-Object -First 1
  $name = ($i.Name -replace "^/","")
  $service = $i.Config.Labels."com.docker.compose.service"
  $serviceNames += $service
  $state = $i.State.Status
  $health = $null
  if ($i.State.Health) { $health = $i.State.Health.Status }

  $isInit = $service -in @("es_init")

  if ($isInit) {
    if (!($state -eq "exited" -and $i.State.ExitCode -eq 0)) {
      $bad += "${name}: expected exited(0), got state=$state exit=$($i.State.ExitCode) health=$health"
    }
    continue
  }

  if ($state -ne "running") {
    $bad += "${name}: state=$state health=$health"
    continue
  }

  if ($health -and $health -ne "healthy") {
    $bad += "${name}: unhealthy ($health)"
  }
}

if ($bad.Count -gt 0) {
  Write-Host "Bad services:" -ForegroundColor Red
  $bad | ForEach-Object { Write-Host " - $_" }
  throw "Infra check failed"
}

$required = @(
  "gateway_nginx","frontend_demo","auth_api","auth_postgres","auth_redis","jaeger",
  "elasticsearch","async_api","async_nginx","async_redis","mongodb","ugc_api","ugc_nginx","assistant_api"
)
foreach ($svc in $required) {
  if ($serviceNames -notcontains $svc) {
    throw "Required service '$svc' is not present in current compose project"
  }
}

$disallowed = @(
  "django-app","admin_nginx","admin_etl","theatre-db",
  "notifications_api","notifications_worker","notifications_postgres","rabbitmq","mailhog",
  "kafka","kafka-init","zookeeper","clickhouse","clickhouse-init","api","etl"
)
foreach ($svc in $disallowed) {
  if ($serviceNames -contains $svc) {
    throw "Disallowed service '$svc' is still present in the cleaned compose project"
  }
}

$portBad = @()
$gatewayBindingCount = 0
foreach ($id in $ids) {
  $i = docker inspect $id | ConvertFrom-Json | Select-Object -First 1
  $name = ($i.Name -replace "^/","")
  $service = $i.Config.Labels."com.docker.compose.service"

  $bindings = @()
  $portsObj = $i.NetworkSettings.Ports
  if ($portsObj) {
    foreach ($p in $portsObj.PSObject.Properties) {
      $containerPort = $p.Name
      $val = $p.Value
      if ($val -ne $null) {
        foreach ($b in $val) {
          if ($b.HostPort) {
            $hostIp = "$($b.HostIp)"
            if ([string]::IsNullOrWhiteSpace($hostIp)) { $hostIp = "*" }
            $bindings += [pscustomobject]@{
              ContainerPort = "$containerPort"
              HostIp        = $hostIp
              HostPort      = "$($b.HostPort)"
              Rendered      = ("{0}->{1}:{2}" -f $containerPort, $hostIp, $b.HostPort)
            }
          }
        }
      }
    }
  }

  if ($bindings.Count -gt 0) {
    if ($service -ne "gateway_nginx") {
      $portBad += "${name}: publishes host ports ($(($bindings | ForEach-Object Rendered) -join ', ')), but only gateway_nginx is allowed"
    } else {
      $gatewayBindingCount = $bindings.Count

      $extra = @(
        $bindings | Where-Object {
          $_.ContainerPort -ne "80/tcp" -or $_.HostPort -ne "80"
        }
      )
      if ($extra.Count -gt 0) {
        $portBad += "${name}: extra published ports not allowed: $(($extra | ForEach-Object Rendered) -join ', ')"
      }

      $badIps = @(
        $bindings | Where-Object {
          $_.ContainerPort -eq "80/tcp" -and $_.HostPort -eq "80" -and $_.HostIp -notin @("0.0.0.0", "::", "*")
        }
      )
      if ($badIps.Count -gt 0) {
        $portBad += "${name}: unexpected host IP bindings for public 80/tcp: $(($badIps | ForEach-Object Rendered) -join ', ')"
      }
    }
  }
}

if ($gatewayBindingCount -eq 0) {
  $portBad += "gateway_nginx: expected published port 80, got none"
}

if ($portBad.Count -gt 0) {
  Write-Host "Port exposure violations:" -ForegroundColor Red
  $portBad | ForEach-Object { Write-Host " - $_" }
  throw "Infra port exposure check failed"
}

$health = Invoke-Json -Method Get -Url "http://localhost/_health"
Assert-Status $health 200 "gateway /_health should be reachable on host port 80"

Write-Host "Infra OK [OK]" -ForegroundColor Green
