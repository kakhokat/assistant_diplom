$ErrorActionPreference = "Stop"

. "$PSScriptRoot\lib.ps1"

$auth = Load-ArtifactJson (Join-Path $PSScriptRoot ".artifacts\auth.json")
$base = $auth.base
$userId = $auth.user.id
$userToken = $auth.tokens.access
$adminToken = $auth.admin.access
$headers = @{ Authorization = "Bearer $userToken" }
$adminHeaders = @{ Authorization = "Bearer $adminToken" }
$badHeaders = @{ Authorization = "Bearer broken.invalid.token" }

Write-Host "UGC: docs, health and OpenAPI..." -ForegroundColor Cyan

$docs = Invoke-Json -Method Get -Url "$base/ugc/docs"
Assert-Status $docs 200 "/ugc/docs should be reachable"

$specResp = Invoke-Json -Method Get -Url "$base/ugc/openapi.json"
Assert-Status $specResp 200 "/ugc/openapi.json should be reachable"
$spec = $specResp.body
if (-not $spec.openapi) { throw "UGC OpenAPI JSON does not look like a spec" }

Assert-OpenApiPathExists -Spec $spec -Path "/likes" -Methods @("GET","PUT","DELETE")
Assert-OpenApiPathExists -Spec $spec -Path "/likes/by-user" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/likes/aggregates" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/bookmarks" -Methods @("GET","PUT","DELETE")
Assert-OpenApiPathExists -Spec $spec -Path "/bookmarks/by-user" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/reviews" -Methods @("GET","POST","PUT","DELETE")
Assert-OpenApiPathExists -Spec $spec -Path "/reviews/by-film" -Methods @("GET")

$h1 = Invoke-Json -Method Get -Url "$base/ugc/health"
Assert-Status $h1 200 "/ugc/health must be 200"
$h2 = Invoke-Json -Method Get -Url "$base/health"
Assert-Status $h2 200 "/health must be 200"

$unauth = Invoke-Json -Method Put -Url "$base/ugc/likes" -Body @{ user_id=$userId; film_id="film_test"; value=10 }
Assert-Status $unauth 401 "UGC likes without token should be 401"

$badTok = Invoke-Json -Method Put -Url "$base/ugc/likes" -Headers $badHeaders -Body @{ user_id=$userId; film_id="film_test"; value=10 }
Assert-Status $badTok 401 "UGC likes with broken token should be 401"

$filmId = "film_test_" + ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())

Write-Host "UGC: likes CRUD and negatives..." -ForegroundColor Cyan

$mismatch = Invoke-Json -Method Put -Url "$base/ugc/likes" -Headers $headers -Body @{ user_id="other"; film_id=$filmId; value=10 }
Assert-Status $mismatch 403 "like upsert with user mismatch should be 403"

$likeBadValue = Invoke-Json -Method Put -Url "$base/ugc/likes" -Headers $headers -Body @{ user_id=$userId; film_id=$filmId; value=11 }
Assert-Status $likeBadValue 422 "like value > 10 should be 422"

$likePut = Invoke-Json -Method Put -Url "$base/ugc/likes" -Headers $headers -Body @{ user_id=$userId; film_id=$filmId; value=10 }
Assert-Status $likePut 200 "like upsert should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/likes" -Method "PUT" -StatusCode "200" -Value $likePut.body

$likeGet = Invoke-Json -Method Get -Url "$base/ugc/likes?user_id=$userId&film_id=$filmId" -Headers $headers
Assert-Status $likeGet 200 "like get should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/likes" -Method "GET" -StatusCode "200" -Value $likeGet.body

$list = Invoke-Json -Method Get -Url "$base/ugc/likes/by-user?user_id=$userId&limit=50&offset=0" -Headers $headers
Assert-Status $list 200 "likes by-user should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/likes/by-user" -Method "GET" -StatusCode "200" -Value $list.body

$ag = Invoke-Json -Method Get -Url "$base/ugc/likes/aggregates?film_id=$filmId" -Headers $headers
Assert-Status $ag 200 "likes aggregates should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/likes/aggregates" -Method "GET" -StatusCode "200" -Value $ag.body

$likeGetForbidden = Invoke-Json -Method Get -Url "$base/ugc/likes?user_id=other&film_id=$filmId" -Headers $headers
Assert-Status $likeGetForbidden 403 "like get with foreign user_id should be 403"

$likeListForbidden = Invoke-Json -Method Get -Url "$base/ugc/likes/by-user?user_id=other&limit=50&offset=0" -Headers $headers
Assert-Status $likeListForbidden 403 "likes by-user with foreign user_id should be 403"

$likeDeleteForbidden = Invoke-Json -Method Delete -Url "$base/ugc/likes?user_id=other&film_id=$filmId" -Headers $headers
Assert-Status $likeDeleteForbidden 403 "like delete with foreign user_id should be 403"

$likeMissingUser = Invoke-Json -Method Get -Url "$base/ugc/likes?user_id=&film_id=$filmId" -Headers $headers
Assert-Status $likeMissingUser 422 "like get with empty user_id should be 422"

$del = Invoke-Json -Method Delete -Url "$base/ugc/likes?user_id=$userId&film_id=$filmId" -Headers $headers
Assert-Status $del 204 "like delete should be 204"

$after = Invoke-Json -Method Get -Url "$base/ugc/likes?user_id=$userId&film_id=$filmId" -Headers $headers
Assert-Status $after 404 "like should be 404 after delete"

$delMissing = Invoke-Json -Method Delete -Url "$base/ugc/likes?user_id=$userId&film_id=$filmId" -Headers $headers
Assert-Status $delMissing 404 "deleting missing like should be 404"

Write-Host "UGC: bookmarks CRUD and negatives..." -ForegroundColor Cyan

$bmPut = Invoke-Json -Method Put -Url "$base/ugc/bookmarks" -Headers $headers -Body @{ user_id=$userId; film_id=$filmId }
Assert-Status $bmPut 200 "bookmark upsert should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/bookmarks" -Method "PUT" -StatusCode "200" -Value $bmPut.body

$bmGet = Invoke-Json -Method Get -Url "$base/ugc/bookmarks?user_id=$userId&film_id=$filmId" -Headers $headers
Assert-Status $bmGet 200 "bookmark get should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/bookmarks" -Method "GET" -StatusCode "200" -Value $bmGet.body

$bmList = Invoke-Json -Method Get -Url "$base/ugc/bookmarks/by-user?user_id=$userId&limit=50&offset=0" -Headers $headers
Assert-Status $bmList 200 "bookmarks by-user should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/bookmarks/by-user" -Method "GET" -StatusCode "200" -Value $bmList.body

$bmGetForbidden = Invoke-Json -Method Get -Url "$base/ugc/bookmarks?user_id=other&film_id=$filmId" -Headers $headers
Assert-Status $bmGetForbidden 403 "bookmark get with foreign user_id should be 403"

$bmListForbidden = Invoke-Json -Method Get -Url "$base/ugc/bookmarks/by-user?user_id=other&limit=50&offset=0" -Headers $headers
Assert-Status $bmListForbidden 403 "bookmarks by-user with foreign user_id should be 403"

$bmDeleteForbidden = Invoke-Json -Method Delete -Url "$base/ugc/bookmarks?user_id=other&film_id=$filmId" -Headers $headers
Assert-Status $bmDeleteForbidden 403 "bookmark delete with foreign user_id should be 403"

$bmBadBody = Invoke-Json -Method Put -Url "$base/ugc/bookmarks" -Headers $headers -Body @{ user_id=$userId; film_id="" }
Assert-Status $bmBadBody 422 "bookmark with empty film_id should be 422"

$bmDel = Invoke-Json -Method Delete -Url "$base/ugc/bookmarks?user_id=$userId&film_id=$filmId" -Headers $headers
Assert-Status $bmDel 204 "bookmark delete should be 204"

$bmAfter = Invoke-Json -Method Get -Url "$base/ugc/bookmarks?user_id=$userId&film_id=$filmId" -Headers $headers
Assert-Status $bmAfter 404 "bookmark should be 404 after delete"

$bmDelMissing = Invoke-Json -Method Delete -Url "$base/ugc/bookmarks?user_id=$userId&film_id=$filmId" -Headers $headers
Assert-Status $bmDelMissing 404 "deleting missing bookmark should be 404"

Write-Host "UGC: reviews CRUD and negatives..." -ForegroundColor Cyan

$revCreate = Invoke-Json -Method Post -Url "$base/ugc/reviews" -Headers $headers -Body @{ user_id=$userId; film_id=$filmId; text="Nice"; user_film_rating=8 }
Assert-Status $revCreate 201 "review create should be 201"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/reviews" -Method "POST" -StatusCode "201" -Value $revCreate.body
if (-not $revCreate.body.review_id) { throw "review_id missing" }
$reviewId = $revCreate.body.review_id

$revGet = Invoke-Json -Method Get -Url "$base/ugc/reviews?review_id=$reviewId" -Headers $headers
Assert-Status $revGet 200 "review get should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/reviews" -Method "GET" -StatusCode "200" -Value $revGet.body

$revUpdate = Invoke-Json -Method Put -Url "$base/ugc/reviews?review_id=$reviewId" -Headers $headers -Body @{ text="Updated"; user_film_rating=7 }
Assert-Status $revUpdate 200 "review update should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/reviews" -Method "PUT" -StatusCode "200" -Value $revUpdate.body

$revList = Invoke-Json -Method Get -Url "$base/ugc/reviews/by-film?film_id=$filmId&limit=50&offset=0" -Headers $headers
Assert-Status $revList 200 "reviews by-film should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/reviews/by-film" -Method "GET" -StatusCode "200" -Value $revList.body

$foreignRevUpdate = Invoke-Json -Method Put -Url "$base/ugc/reviews?review_id=$reviewId" -Headers $adminHeaders -Body @{ text="Hack"; user_film_rating=5 }
Assert-Status $foreignRevUpdate 403 "foreign review update should be 403"

$foreignRevDelete = Invoke-Json -Method Delete -Url "$base/ugc/reviews?review_id=$reviewId" -Headers $adminHeaders
Assert-Status $foreignRevDelete 403 "foreign review delete should be 403"

$revEmptyText = Invoke-Json -Method Put -Url "$base/ugc/reviews?review_id=$reviewId" -Headers $headers -Body @{ text=""; user_film_rating=7 }
Assert-Status $revEmptyText 422 "review update with empty text should be 422"

$badBody = Invoke-Json -Method Post -Url "$base/ugc/reviews" -Headers $headers -Body @{ }
Assert-Status $badBody 422 "review create with invalid body should be 422"

$revDel = Invoke-Json -Method Delete -Url "$base/ugc/reviews?review_id=$reviewId" -Headers $headers
Assert-Status $revDel 204 "review delete should be 204"

$revAfter = Invoke-Json -Method Get -Url "$base/ugc/reviews?review_id=$reviewId" -Headers $headers
Assert-Status $revAfter 404 "review should be 404 after delete"

$revDelMissing = Invoke-Json -Method Delete -Url "$base/ugc/reviews?review_id=$reviewId" -Headers $headers
Assert-Status $revDelMissing 404 "deleting missing review should be 404"

Write-Host "UGC OK [OK]" -ForegroundColor Green
