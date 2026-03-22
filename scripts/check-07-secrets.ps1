$ErrorActionPreference = "Stop"

. "$PSScriptRoot\lib.ps1"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Write-Host "Secrets hygiene: checking env examples, repo hygiene, compose files and code-level insecure fallbacks..." -ForegroundColor Cyan

$gitignorePath = Join-Path $repoRoot ".gitignore"
$gitignore = Get-FileText $gitignorePath
$requiredIgnoreRules = @(
  '.env',
  'services/*/.env',
  'scripts/.artifacts/'
)
foreach ($rule in $requiredIgnoreRules) {
  if ($gitignore -notmatch [regex]::Escape($rule)) {
    throw ".gitignore does not contain required rule: $rule"
  }
}

$requiredExamples = @(
  '.env.example',
  'services/auth/.env.example',
  'services/ugc/.env.example',
  'services/async_api/.env.example',
  'services/assistant/.env.example'
)
foreach ($rel in $requiredExamples) {
  $path = Join-Path $repoRoot $rel
  if (-not (Test-Path $path)) {
    throw "Missing env example: $rel"
  }
}

$composeFiles = @(
  'docker-compose.yml',
  'docker-compose.dev.yml',
  'services/auth/docker-compose.yml',
  'services/async_api/docker-compose.yml',
  'services/ugc/docker-compose.yml'
)
$badFindings = @()
foreach ($rel in $composeFiles) {
  $path = Join-Path $repoRoot $rel
  if (-not (Test-Path $path)) { continue }
  $text = Get-FileText $path

  $patterns = @(
    '--password\s+"[^$][^"]+"',
    'POSTGRES_PASSWORD:\s*[A-Za-z0-9_\-]+',
    'SECRET_KEY:\s*[A-Za-z0-9_\-]+'
  )
  foreach ($pattern in $patterns) {
    if ($text -match $pattern) {
      $badFindings += "$rel matches inline-secret pattern: $pattern"
    }
  }
}

$exampleFiles = @(
  '.env.example',
  'services/auth/.env.example',
  'services/ugc/.env.example',
  'services/async_api/.env.example',
  'services/assistant/.env.example'
)

$forbiddenExamplePatterns = @(
  @{ Pattern = '(?im)^\s*DEBUG\s*=\s*True\s*$'; Message = 'env example must not enable DEBUG=True by default' },
  @{ Pattern = '(?im)^\s*SECRET_KEY\s*=\s*(changeme|secret_key|replace-me)\s*$'; Message = 'env example contains an insecure SECRET_KEY placeholder' },
  @{ Pattern = '(?im)^\s*JWT_SECRET\s*=\s*(super-secret-key|changeme|secret)\s*$'; Message = 'env example contains an insecure JWT secret placeholder' },
  @{ Pattern = '(?im)^\s*POSTGRES_PASSWORD\s*=\s*(postgres|password|changeme)\s*$'; Message = 'env example contains a trivial database password' },
  @{ Pattern = '(?im)^\s*ALLOWED_HOSTS\s*=\s*\*\s*$'; Message = 'env example must not allow wildcard ALLOWED_HOSTS in prod-like mode' },
  @{ Pattern = '(?im)^\s*GATEWAY_HTTP_PORT\s*=\s*(?!80\s*$)'; Message = 'root env example must publish gateway on port 80 by default' },
  @{ Pattern = '(?im)^\s*(AUTH|ADMIN|ASYNC|UGC|NOTIFICATIONS)_HTTP_PORT\s*='; Message = 'root env example must not expose per-service host ports in prod-like mode' }
)

foreach ($rel in $exampleFiles) {
  $path = Join-Path $repoRoot $rel
  if (-not (Test-Path $path)) { continue }
  $text = Get-FileText $path
  foreach ($rule in $forbiddenExamplePatterns) {
    if ($text -match $rule.Pattern) {
      $badFindings += "${rel}: $($rule.Message)"
    }
  }
}

if ($badFindings.Count -gt 0) {
  $badFindings | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
  throw "Secrets hygiene check failed"
}


# Runtime auth artifacts may be created by regression locally; remove them before hygiene checks.
$runtimeArtifact = Join-Path $PSScriptRoot ".artifacts\auth.json"
if (Test-Path $runtimeArtifact) {
  Write-Host "Removing runtime artifact left by local regression: scripts/.artifacts/auth.json" -ForegroundColor Yellow
  Remove-Item -Force $runtimeArtifact
}

# Code must not contain insecure config fallbacks for runtime secrets and critical settings
$codeChecks = @(
  @{ File = Join-Path $repoRoot "services/auth/src/core/settings.py"; Pattern = 'DB_PASSWORD\s*:\s*str\s*=\s*"'; Message = 'auth settings must not hardcode DB_PASSWORD defaults' },
  @{ File = Join-Path $repoRoot "services/auth/src/core/settings.py"; Pattern = 'JWT_SECRET\s*:\s*str\s*=\s*"'; Message = 'auth settings must not hardcode JWT_SECRET defaults' },
  @{ File = Join-Path $repoRoot "services/auth/src/core/settings.py"; Pattern = 'BOOTSTRAP_ADMIN_PASSWORD\s*:\s*str\s*=\s*"'; Message = 'auth settings must not hardcode bootstrap admin password defaults' },
  @{ File = Join-Path $repoRoot "services/auth/src/core/settings.py"; Pattern = 'CORS_ALLOW_ORIGINS\s*:\s*str\s*=\s*"'; Message = 'auth settings must not hardcode CORS defaults' },
  @{ File = Join-Path $repoRoot "services/auth/src/core/settings.py"; Pattern = 'PROXY_TRUSTED_HOSTS\s*:\s*str\s*=\s*"'; Message = 'auth settings must not hardcode proxy trust defaults' },
  @{ File = Join-Path $repoRoot "services/async_api/src/core/settings.py"; Pattern = 'CORS_ALLOW_ORIGINS\s*:\s*str\s*=\s*"'; Message = 'async settings must not hardcode CORS defaults' },
  @{ File = Join-Path $repoRoot "services/async_api/src/core/settings.py"; Pattern = 'PROXY_TRUSTED_HOSTS\s*:\s*str\s*=\s*"'; Message = 'async settings must not hardcode proxy trust defaults' },
  @{ File = Join-Path $repoRoot "services/async_api/src/core/auth.py"; Pattern = 'os\.getenv\([^\)]*,\s*"[^"]+"\)'; Message = 'async auth must not use getenv fallbacks for JWT settings' },
  @{ File = Join-Path $repoRoot "services/ugc/services/ugc_api/app/auth.py"; Pattern = 'os\.getenv\([^\)]*,\s*"HS256"\)'; Message = 'ugc auth must not fallback to HS256 in code' },
  @{ File = Join-Path $repoRoot "services/assistant/src/core/settings.py"; Pattern = 'AUTH_API_BASE_URL\s*:\s*str\s*=\s*"'; Message = 'assistant settings must not hardcode auth base url defaults' },
  @{ File = Join-Path $repoRoot "services/assistant/src/core/settings.py"; Pattern = 'CATALOG_API_BASE_URL\s*:\s*str\s*=\s*"'; Message = 'assistant settings must not hardcode catalog base url defaults' },
  @{ File = Join-Path $repoRoot "services/assistant/src/core/settings.py"; Pattern = 'UGC_API_BASE_URL\s*:\s*str\s*=\s*"'; Message = 'assistant settings must not hardcode ugc base url defaults' }
)

foreach ($check in $codeChecks) {
  if (-not (Test-Path $check.File)) { throw "Missing file for secrets check: $($check.File)" }
  $content = Get-Content $check.File -Raw
  if ($content -match $check.Pattern) {
    throw $check.Message
  }
}

Write-Host "Secrets hygiene OK [OK]" -ForegroundColor Green
