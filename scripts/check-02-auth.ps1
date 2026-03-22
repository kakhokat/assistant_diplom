$ErrorActionPreference = "Stop"

. "$PSScriptRoot\lib.ps1"

$base = "http://localhost"
$art = Join-Path $PSScriptRoot ".artifacts\auth.json"

# --- 0) Negative: /me without token -> 401 ---
$resp = Invoke-Json -Method Get -Url "$base/api/v1/auth/me"
Assert-Status $resp 401 "Auth /me without token should be 401"

# --- 1) Create random user (idempotent) ---
$login = "user_" + (Get-Random) + "_" + ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
$pass = "password123"

Write-Host "Auth: signup/login at $base ..." -ForegroundColor Cyan

# signup
$resp = Invoke-Json -Method Post -Url "$base/api/v1/auth/signup" -Body @{ login = $login; password = $pass }
if ($resp.status -eq 409) {
  Write-Host "User already exists (rare), continuing..." -ForegroundColor Yellow
} else {
  Assert-Status $resp 201 "signup should be 201"
}

# Negative: signup with invalid body -> 422
$bad = Invoke-Json -Method Post -Url "$base/api/v1/auth/signup" -Body @{ login = ""; password = "1" }
Assert-Status $bad 422 "signup invalid body should be 422"

# login
$tokens = Invoke-Json -Method Post -Url "$base/api/v1/auth/login" -Body @{ login = $login; password = $pass }
Assert-Status $tokens 200 "login should be 200"
if (-not $tokens.body.access_token) { throw "No access_token in login response" }

Write-Host ("Got access token: " + $tokens.body.access_token.Substring(0,25) + "...") -ForegroundColor Green

# Negative: login wrong password -> 401
$badLogin = Invoke-Json -Method Post -Url "$base/api/v1/auth/login" -Body @{ login = $login; password = "wrong" }
Assert-Status $badLogin 401 "login wrong password should be 401"

# me
$headers = @{ Authorization = "Bearer $($tokens.body.access_token)" }
$me = Invoke-Json -Method Get -Url "$base/api/v1/auth/me" -Headers $headers
Assert-Status $me 200 "/me with token should be 200"
if (-not $me.body.id) { throw "Auth /me returned no id" }



# refresh negative (missing token) -> 400
$refreshBad = Invoke-Json -Method Post -Url "$base/api/v1/auth/refresh" -Body @{}
Assert-Status $refreshBad 400 "refresh without refresh_token should be 400"

# refresh valid
$refreshOk = Invoke-Json -Method Post -Url "$base/api/v1/auth/refresh" -Body @{ refresh_token = $tokens.body.refresh_token }
Assert-Status $refreshOk 200 "refresh should be 200"
if (-not $refreshOk.body.access_token) { throw "No access_token in refresh response" }

# logout (should revoke current access token)
$logout = Invoke-Json -Method Post -Url "$base/api/v1/auth/logout" -Headers $headers
Assert-Status $logout 204 "logout should be 204"

# after logout, /me should be 401 (token revoked or invalid)
$meAfterLogout = Invoke-Json -Method Get -Url "$base/api/v1/auth/me" -Headers $headers
if ($meAfterLogout.status -ne 401 -and $meAfterLogout.status -ne 403) {
  throw "Expected 401/403 after logout, got $($meAfterLogout.status)"
}

# Re-login to restore session tokens for subsequent checks
$tokens = Invoke-Json -Method Post -Url "$base/api/v1/auth/login" -Body @{ login = $login; password = $pass }
Assert-Status $tokens 200 "re-login should be 200"
$headers = @{ Authorization = "Bearer $($tokens.body.access_token)" }
$me = Invoke-Json -Method Get -Url "$base/api/v1/auth/me" -Headers $headers
Assert-Status $me 200 "re-login /me should be 200"

# --- 2) Login as bootstrap admin / privileged account for regression ---
$authEnv = Resolve-Path (Join-Path $PSScriptRoot "..\services\auth\.env")
$adminLogin = Get-DotEnvValue $authEnv "BOOTSTRAP_ADMIN_LOGIN"
$adminPass  = Get-DotEnvValue $authEnv "BOOTSTRAP_ADMIN_PASSWORD"
if ([string]::IsNullOrWhiteSpace($adminLogin) -or [string]::IsNullOrWhiteSpace($adminPass)) { throw "BOOTSTRAP_ADMIN_LOGIN / BOOTSTRAP_ADMIN_PASSWORD must be set in services/auth/.env" }

$adminTok = Invoke-Json -Method Post -Url "$base/api/v1/auth/login" -Body @{ login = $adminLogin; password = $adminPass }
# If admin bootstrap не поднялся, тут будет 401 и это сигнал, что нужно проверить auth bootstrap
Assert-Status $adminTok 200 "bootstrap admin login failed; check auth bootstrap env"

# save artifacts for other scripts
Save-ArtifactJson $art @{
  base = $base
  user = @{ login = $login; password = $pass; id = $me.body.id }
  tokens = @{ access = $tokens.body.access_token; refresh = $tokens.body.refresh_token }
  admin = @{ login = $adminLogin; id = $null; access = $adminTok.body.access_token }
}

Write-Host "Auth OK [OK]" 
