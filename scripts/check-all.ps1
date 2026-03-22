$ErrorActionPreference = "Stop"

$checks = @(
  ".\scripts\check-01-infra.ps1",
  ".\scripts\check-02-auth.ps1",
  ".\scripts\check-03-async-api.ps1",
  ".\scripts\check-04-ugc.ps1",
  ".\scripts\check-05-assistant.ps1"
)

$postChecks = @(
  ".\scripts\check-06-logs.ps1",
  ".\scripts\check-07-secrets.ps1",
  ".\scripts\check-08-security.ps1"
)

$artDir = Join-Path $PSScriptRoot ".artifacts"
if (Test-Path $artDir) {
  Remove-Item -Recurse -Force $artDir
}

try {
  foreach ($c in $checks) {
    Write-Host "`n==> RUN $c" -ForegroundColor Cyan
    & $c
  }

  if (Test-Path $artDir) {
    Remove-Item -Recurse -Force $artDir
  }

  foreach ($c in $postChecks) {
    Write-Host "`n==> RUN $c" -ForegroundColor Cyan
    & $c
  }

  Write-Host "`nALL CHECKS OK [OK]" -ForegroundColor Green
}
finally {
  if (Test-Path $artDir) {
    Remove-Item -Recurse -Force $artDir
  }
}
