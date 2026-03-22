$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-HttpMeta {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [string]$Method = "GET"
  )

  $tmpBody = Join-Path $env:TEMP ("curl-body-" + [guid]::NewGuid().ToString() + ".tmp")

  try {
    $raw = & curl.exe -sS -D - -o $tmpBody -X $Method $Url 2>&1
    if ($LASTEXITCODE -ne 0) {
      throw "curl.exe failed for $Method $Url`n$($raw | Out-String)"
    }

    $text = ($raw | Out-String)
    $text = $text -replace "`r", ""

    $statusMatches = [regex]::Matches($text, '(?m)^HTTP/\d+(?:\.\d+)?\s+(\d{3})\b')
    if ($statusMatches.Count -lt 1) {
      throw "Could not parse HTTP status from response for $Method $Url`n$text"
    }

    $lastStatus = $statusMatches[$statusMatches.Count - 1]
    $tail = $text.Substring($lastStatus.Index)

    $parts = @($tail -split "`n`n", 2)
    $headerBlock = $parts[0]

    $statusCode = [int]$lastStatus.Groups[1].Value

    return [PSCustomObject]@{
      Url         = $Url
      Method      = $Method
      StatusCode  = $statusCode
      HeaderBlock = $headerBlock
      Raw         = $text
    }
  }
  finally {
    Remove-Item $tmpBody -Force -ErrorAction SilentlyContinue
  }
}

function Get-HeaderValue {
  param(
    [Parameter(Mandatory = $true)]$Response,
    [Parameter(Mandatory = $true)][string]$Name
  )

  $pattern = '(?im)^' + [regex]::Escape($Name) + ':\s*(.+)$'
  $m = [regex]::Match($Response.HeaderBlock, $pattern)
  if (-not $m.Success) { return "" }
  return $m.Groups[1].Value.Trim()
}

function Show-Headers {
  param(
    [Parameter(Mandatory = $true)]$Response,
    [Parameter(Mandatory = $true)][string]$Context
  )

  Write-Host "$Context headers actually returned:" -ForegroundColor Yellow
  Write-Host $Response.HeaderBlock -ForegroundColor Yellow
}

function Assert-StatusOneOf {
  param(
    [Parameter(Mandatory = $true)]$Response,
    [Parameter(Mandatory = $true)][int[]]$Allowed,
    [Parameter(Mandatory = $true)][string]$Context
  )

  if ($Allowed -notcontains [int]$Response.StatusCode) {
    throw "$Context returned HTTP $($Response.StatusCode); expected one of: $($Allowed -join ', ')"
  }
}

function Assert-HeaderPresent {
  param(
    [Parameter(Mandatory = $true)]$Response,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Context
  )

  $value = Get-HeaderValue -Response $Response -Name $Name
  if ([string]::IsNullOrWhiteSpace($value)) {
    Show-Headers -Response $Response -Context $Context
    throw "$Context is missing header $Name"
  }
}

function Assert-HeaderEquals {
  param(
    [Parameter(Mandatory = $true)]$Response,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Expected,
    [Parameter(Mandatory = $true)][string]$Context
  )

  $actual = Get-HeaderValue -Response $Response -Name $Name
  if ([string]::IsNullOrWhiteSpace($actual)) {
    Show-Headers -Response $Response -Context $Context
    throw "$Context is missing header $Name"
  }

  if ($actual -ne $Expected) {
    throw "$Context header $Name expected '$Expected' but got '$actual'"
  }
}

function Assert-HeaderContains {
  param(
    [Parameter(Mandatory = $true)]$Response,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$ExpectedPart,
    [Parameter(Mandatory = $true)][string]$Context
  )

  $actual = Get-HeaderValue -Response $Response -Name $Name
  if ([string]::IsNullOrWhiteSpace($actual)) {
    Show-Headers -Response $Response -Context $Context
    throw "$Context is missing header $Name"
  }

  if ($actual -notlike "*$ExpectedPart*") {
    throw "$Context header $Name must contain '$ExpectedPart' but got '$actual'"
  }
}

Write-Host "Security: checking gateway hardening..." -ForegroundColor Cyan

$base = "http://localhost"

# 1) gateway health
$health = Get-HttpMeta -Url "$base/_health" -Method "GET"
Assert-StatusOneOf -Response $health -Allowed @(200) -Context "/_health response"
Assert-HeaderPresent -Response $health -Name "X-Request-Id" -Context "/_health response"
Assert-HeaderEquals -Response $health -Name "X-Content-Type-Options" -Expected "nosniff" -Context "/_health response"
Assert-HeaderEquals -Response $health -Name "X-Frame-Options" -Expected "SAMEORIGIN" -Context "/_health response"
Assert-HeaderEquals -Response $health -Name "Referrer-Policy" -Expected "strict-origin-when-cross-origin" -Context "/_health response"
Assert-HeaderContains -Response $health -Name "Permissions-Policy" -ExpectedPart "camera=()" -Context "/_health response"
Assert-HeaderEquals -Response $health -Name "Cross-Origin-Opener-Policy" -Expected "same-origin" -Context "/_health response"

$serverHeader = Get-HeaderValue -Response $health -Name "Server"
if (-not [string]::IsNullOrWhiteSpace($serverHeader) -and $serverHeader -match '\d+\.\d+') {
  throw "/_health leaks server version in Server header: $serverHeader"
}

# 2) root POST must be blocked
$rootPost = Get-HttpMeta -Url "$base/" -Method "POST"
Assert-StatusOneOf -Response $rootPost -Allowed @(403, 405) -Context "POST /"

# 3) health POST must be blocked
$healthPost = Get-HttpMeta -Url "$base/_health" -Method "POST"
Assert-StatusOneOf -Response $healthPost -Allowed @(403, 405) -Context "POST /_health"

# 4) async swagger should keep gateway security headers
$docs = Get-HttpMeta -Url "$base/api/openapi" -Method "GET"
Assert-StatusOneOf -Response $docs -Allowed @(200) -Context "/api/openapi response"
Assert-HeaderPresent -Response $docs -Name "X-Request-Id" -Context "/api/openapi response"
Assert-HeaderEquals -Response $docs -Name "X-Content-Type-Options" -Expected "nosniff" -Context "/api/openapi response"
Assert-HeaderEquals -Response $docs -Name "X-Frame-Options" -Expected "SAMEORIGIN" -Context "/api/openapi response"
Assert-HeaderEquals -Response $docs -Name "Referrer-Policy" -Expected "strict-origin-when-cross-origin" -Context "/api/openapi response"

# 5) assistant docs should keep gateway security headers
$assistantDocs = Get-HttpMeta -Url "$base/assistant/docs" -Method "GET"
Assert-StatusOneOf -Response $assistantDocs -Allowed @(200) -Context "/assistant/docs response"
Assert-HeaderPresent -Response $assistantDocs -Name "X-Request-Id" -Context "/assistant/docs response"
Assert-HeaderEquals -Response $assistantDocs -Name "X-Content-Type-Options" -Expected "nosniff" -Context "/assistant/docs response"
Assert-HeaderEquals -Response $assistantDocs -Name "X-Frame-Options" -Expected "SAMEORIGIN" -Context "/assistant/docs response"

Write-Host "Security OK [OK]" -ForegroundColor Green
