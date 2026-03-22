$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\lib.ps1"

function Decode-JsonString([Parameter(Mandatory=$true)][string]$Escaped) {
  return (ConvertFrom-Json ('"' + $Escaped + '"'))
}

function Assert-AssistantEnvelope {
  param(
    [Parameter(Mandatory=$true)]$Resp,
    [string]$Context = 'assistant response'
  )

  Assert-HasKeys -Obj $Resp.body -Keys @('session_id', 'answer_text', 'speak_text', 'intent', 'requires_auth') -Context $Context
  if ([string]::IsNullOrWhiteSpace([string]$Resp.body.session_id)) {
    throw "$Context must contain non-empty session_id"
  }
  if ([string]::IsNullOrWhiteSpace([string]$Resp.body.answer_text)) {
    throw "$Context must contain non-empty answer_text"
  }
  if ([string]::IsNullOrWhiteSpace([string]$Resp.body.speak_text)) {
    throw "$Context must contain non-empty speak_text"
  }
}

$QNeedAuth = Decode-JsonString '\u0447\u0442\u043e \u0443 \u043c\u0435\u043d\u044f \u0432 \u0437\u0430\u043a\u043b\u0430\u0434\u043a\u0430\u0445\u003f'
$QGenericRecommend = Decode-JsonString '\u043f\u043e\u0441\u043e\u0432\u0435\u0442\u0443\u0439 \u0444\u0438\u043b\u044c\u043c'
$QOverviewPrefix = Decode-JsonString '\u0440\u0430\u0441\u0441\u043a\u0430\u0436\u0438 \u043f\u0440\u043e \u0444\u0438\u043b\u044c\u043c'
$QFeedback = Decode-JsonString '\u043a\u0442\u043e \u0441\u043d\u044f\u043b \u044d\u0442\u043e\u0442 \u0444\u0438\u043b\u044c\u043c\u003f'

$authArtifact = Join-Path $PSScriptRoot '.artifacts\auth.json'
if (-not (Test-Path $authArtifact)) {
  Write-Host 'Assistant: auth artifact missing, running check-02-auth.ps1 first...' -ForegroundColor Yellow
  & (Join-Path $PSScriptRoot 'check-02-auth.ps1')
}

$auth = Load-ArtifactJson $authArtifact
$base = $auth.base

$relogin = Invoke-Json -Method Post -Url "$base/api/v1/auth/login" -Body @{
  login    = $auth.user.login
  password = $auth.user.password
}
Assert-Status $relogin 200 'Assistant preflight re-login should be 200'
$userToken = $relogin.body.access_token
$headers = @{ Authorization = "Bearer $userToken" }

Write-Host 'Assistant: smoke checks for demo, docs, public flows and auth-gated flows...' -ForegroundColor Cyan

$health = Invoke-Json -Method Get -Url "$base/assistant/health"
Assert-Status $health 200 'assistant /health should be 200'

$docs = Invoke-Json -Method Get -Url "$base/assistant/docs"
Assert-Status $docs 200 'assistant /docs should be 200'

$demoResp = Invoke-Json -Method Get -Url "$base/demo/"
Assert-Status $demoResp 200 'demo frontend should be reachable at /demo/'
if ($demoResp.raw -notmatch 'assistant-query') { throw 'demo frontend must contain assistant input' }

$demoConfig = Invoke-Json -Method Get -Url "$base/demo/demo-config.json"
Assert-Status $demoConfig 200 'demo config must be reachable'
if (-not $demoConfig.body.assistantExamples[0]) { throw 'demo config must contain assistantExamples' }

$specResp = Invoke-Json -Method Get -Url "$base/assistant/openapi.json"
Assert-Status $specResp 200 'assistant OpenAPI should be reachable'
$spec = $specResp.body
if (-not $spec.openapi) { throw 'Assistant OpenAPI JSON does not look like a spec' }
Assert-OpenApiPathExists -Spec $spec -Path '/assistant/api/v1/ask' -Methods @('POST')
Assert-OpenApiPathExists -Spec $spec -Path '/assistant/api/v1/feedback' -Methods @('POST')
Assert-OpenApiPathExists -Spec $spec -Path '/assistant/api/v1/search' -Methods @('GET')
Assert-OpenApiPathExists -Spec $spec -Path '/assistant/api/v1/feed' -Methods @('GET')
Assert-OpenApiPathExists -Spec $spec -Path '/assistant/health' -Methods @('GET')

$anonFeed = Invoke-Json -Method Get -Url "$base/assistant/api/v1/feed?limit=5"
Assert-Status $anonFeed 200 'assistant public feed without token should be 200'
$feedItems = @($anonFeed.body)
if ($feedItems.Count -lt 1) { throw 'assistant public feed should return at least one film' }
$firstFilm = $feedItems[0]
if ([string]::IsNullOrWhiteSpace([string]$firstFilm.title)) { throw 'assistant public feed first film should have title' }
if ([string]::IsNullOrWhiteSpace([string]$firstFilm.uuid)) { throw 'assistant public feed first film should have uuid' }

$searchQuery = [string]$firstFilm.title
$anonSearch = Invoke-Json -Method Get -Url "$base/assistant/api/v1/search?query=$(UrlEncode $searchQuery)"
Assert-Status $anonSearch 200 'assistant public search without token should be 200'
$searchItems = @($anonSearch.body)
if ($searchItems.Count -lt 1) { throw 'assistant public search should return at least one film' }
if (-not ($searchItems | Where-Object { [string]$_.title -eq $searchQuery -or [string]$_.original_title -eq $searchQuery })) {
  throw 'assistant public search should include the queried film on the first page'
}

$publicRecommend = Invoke-Json -Method Post -Url "$base/assistant/api/v1/ask" -Body @{ query = $QGenericRecommend; session_id = 'assistant-smoke-public-recommend' }
Assert-Status $publicRecommend 200 'assistant public generic recommendation should be 200'
Assert-AssistantEnvelope -Resp $publicRecommend -Context 'assistant public recommend response'
if ($publicRecommend.body.requires_auth) { throw 'assistant public generic recommendation must not require auth' }
if ($null -eq $publicRecommend.body.result) { throw 'assistant public generic recommendation should contain result payload' }
if (@($publicRecommend.body.result.items).Count -lt 1) { throw 'assistant public generic recommendation should contain at least one item' }

$publicOverview = Invoke-Json -Method Post -Url "$base/assistant/api/v1/ask" -Body @{ query = "$QOverviewPrefix $searchQuery"; session_id = 'assistant-smoke-overview' }
Assert-Status $publicOverview 200 'assistant public overview-style ask should be 200'
Assert-AssistantEnvelope -Resp $publicOverview -Context 'assistant public overview response'

$needAuth = Invoke-Json -Method Post -Url "$base/assistant/api/v1/ask" -Body @{ query = $QNeedAuth; session_id = 'assistant-smoke-auth-required' }
Assert-Status $needAuth 200 'assistant personalized ask without token should still be 200'
Assert-AssistantEnvelope -Resp $needAuth -Context 'assistant auth-required response'
if (-not $needAuth.body.requires_auth) { throw 'assistant personalized ask without token must set requires_auth=true' }
if ($needAuth.body.answer_text -match '(?i)missing bearer token|invalid bearer token') {
  throw 'assistant personalized ask without token must not expose raw bearer token errors'
}

$bookmarksSeed = Invoke-Json -Method Put -Url "$base/ugc/bookmarks" -Headers $headers -Body @{
  user_id = "$($auth.user.id)"
  film_id = "$($firstFilm.uuid)"
}
Assert-Status $bookmarksSeed 200 'seed bookmark for assistant bookmarks should be 200'

$bookmarks = Invoke-Json -Method Post -Url "$base/assistant/api/v1/ask" -Headers $headers -Body @{ query = $QNeedAuth; session_id = 'assistant-smoke-bookmarks' }
Assert-Status $bookmarks 200 'assistant bookmarks query after login should be 200'
Assert-AssistantEnvelope -Resp $bookmarks -Context 'assistant bookmarks response'
if ($bookmarks.body.requires_auth) { throw 'assistant bookmarks query after login must not require auth' }
if ($null -eq $bookmarks.body.result) { throw 'assistant bookmarks query after login should contain result payload' }
if (@($bookmarks.body.result.items).Count -lt 1) { throw 'assistant bookmarks query after login should return at least one item' }

$feedback = Invoke-Json -Method Post -Url "$base/assistant/api/v1/feedback" -Body @{
  session_id = 'assistant-smoke-feedback'
  query = $QFeedback
  reaction = 'up'
  intent = [string]$publicOverview.body.intent
  metadata = @{ source = 'check-05-smoke' }
}
Assert-Status $feedback 200 'assistant feedback endpoint should accept feedback'
if ([string]$feedback.body.status -ne 'ok') { throw 'assistant feedback response.status must be ok' }

Write-Host 'Assistant OK [OK]' -ForegroundColor Green
