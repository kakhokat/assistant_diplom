$ErrorActionPreference = "Stop"

. "$PSScriptRoot\lib.ps1"

$artifactDir = Join-Path $PSScriptRoot ".artifacts"
$authArtifact = Join-Path $artifactDir "auth.json"
$demoArtifact = Join-Path $artifactDir "demo-user.json"

Write-Host "Preparing demo user..." -ForegroundColor Cyan

if (-not (Test-Path $authArtifact)) {
  Write-Host "auth artifact missing, running check-02-auth.ps1..." -ForegroundColor Yellow
  & (Join-Path $PSScriptRoot "check-02-auth.ps1")
}

$auth = Load-ArtifactJson $authArtifact
$base = $auth.base
$login = $auth.user.login
$password = $auth.user.password
$userId = $auth.user.id

$loginResp = Invoke-Json -Method Post -Url "$base/api/v1/auth/login" -Body @{
  login = $login
  password = $password
}
Assert-Status $loginResp 200 "demo user login should be 200"
if (-not $loginResp.body.access_token) { throw "No access_token in login response" }

$token = $loginResp.body.access_token
$headers = @{ Authorization = "Bearer $token" }

$filmsResp = Invoke-Json -Method Get -Url "$base/api/v1/films?page_number=1&page_size=20&sort=-imdb_rating"
Assert-Status $filmsResp 200 "films list should be 200"
$films = @($filmsResp.body)
if ($films.Count -lt 12) {
  throw "Need at least 12 films in catalog for demo seeding; got $($films.Count)"
}

$bookmarkCount = [Math]::Min(5, $films.Count)
$likeCount = [Math]::Min(12, $films.Count)

$bookmarked = @()
for ($i = 0; $i -lt $bookmarkCount; $i++) {
  $film = $films[$i]
  if (-not $film.uuid) { continue }
  $resp = Invoke-Json -Method Put -Url "$base/ugc/bookmarks" -Headers $headers -Body @{
    user_id = $userId
    film_id = $film.uuid
  }
  Assert-Status $resp 200 "bookmark upsert should be 200"
  $bookmarked += [pscustomobject]@{
    film_id = $film.uuid
    title = $film.title
  }
}

$liked = @()
for ($i = 0; $i -lt $likeCount; $i++) {
  $film = $films[$i]
  if (-not $film.uuid) { continue }
  $value = 10 - ($i % 5)
  if ($value -lt 6) { $value = 6 }
  $resp = Invoke-Json -Method Put -Url "$base/ugc/likes" -Headers $headers -Body @{
    user_id = $userId
    film_id = $film.uuid
    value = $value
  }
  Assert-Status $resp 200 "like upsert should be 200"
  $liked += [pscustomobject]@{
    film_id = $film.uuid
    title = $film.title
    value = $value
  }
}

Save-ArtifactJson $demoArtifact @{
  base = $base
  user = @{
    login = $login
    password = $password
    id = $userId
  }
  counts = @{
    bookmarks = $bookmarked.Count
    likes = $liked.Count
  }
  bookmarks = $bookmarked
  likes = $liked
}

Write-Host ""
Write-Host "DEMO USER READY" -ForegroundColor Green
Write-Host "Base URL : $base"
Write-Host "Login    : $login"
Write-Host "Password : $password"
Write-Host "User ID  : $userId"
Write-Host "Bookmarks: $($bookmarked.Count)"
Write-Host "Likes    : $($liked.Count)"
Write-Host "Artifact : $demoArtifact"
Write-Host ""
Write-Host "Suggested demo flow:" -ForegroundColor Cyan
Write-Host "  1) As guest ask: what is in my bookmarks?"
Write-Host "  2) Log in with the demo user"
Write-Host "  3) Ask: what is in my bookmarks?"
Write-Host "  4) Ask: recommend movies based on my favorite genres"
Write-Host "  5) Ask: what should I watch based on my likes?"
Write-Host ""
Write-Host "Seeded bookmarks:" -ForegroundColor Cyan
foreach ($item in $bookmarked) {
  Write-Host ("  - " + $item.title + " [" + $item.film_id + "]")
}
Write-Host ""
Write-Host "Seeded likes:" -ForegroundColor Cyan
foreach ($item in $liked) {
  Write-Host ("  - " + $item.title + " [" + $item.value + "]")
}
