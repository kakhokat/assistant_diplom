$ErrorActionPreference = "Stop"

. "$PSScriptRoot\lib.ps1"

$auth = Load-ArtifactJson (Join-Path $PSScriptRoot ".artifacts\auth.json")
$base = $auth.base

Write-Host "Async API: checking docs and public catalog endpoints through gateway..." -ForegroundColor Cyan

$sw = Invoke-Json -Method Get -Url "$base/api/openapi"
Assert-Status $sw 200 "Swagger UI should be reachable at /api/openapi"

$specResp = Invoke-Json -Method Get -Url "$base/api/openapi.json"
Assert-Status $specResp 200 "OpenAPI JSON should be reachable at /api/openapi.json"
$spec = $specResp.body
if (-not $spec.openapi) { throw "OpenAPI JSON does not look like a spec" }

Assert-OpenApiPathExists -Spec $spec -Path "/api/v1/films/" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/api/v1/films/search" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/api/v1/films/{film_id}" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/api/v1/genres/" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/api/v1/genres/search" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/api/v1/genres/{genre_id}" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/api/v1/persons/" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/api/v1/persons/search" -Methods @("GET")
Assert-OpenApiPathExists -Spec $spec -Path "/api/v1/persons/{person_id}" -Methods @("GET")

$badPage = Invoke-Json -Method Get -Url "$base/api/v1/films/?page_number=0&page_size=10"
Assert-Status $badPage 422 "page_number=0 should be 422"

$badSize = Invoke-Json -Method Get -Url "$base/api/v1/films/?page_number=1&page_size=1001"
Assert-Status $badSize 422 "page_size > max should be 422"

$films = Invoke-Json -Method Get -Url "$base/api/v1/films/?page_number=1&page_size=10&sort=-imdb_rating"
Assert-Status $films 200 "films list should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/api/v1/films/" -Method "GET" -StatusCode "200" -Value $films.body
$film0 = Get-FirstItem -Value $films.body -Hint "films"
Assert-HasKeys -Obj $film0 -Keys @("uuid","title") -Context "film list item"
$filmId = $film0.uuid

$filmDetail = Invoke-Json -Method Get -Url "$base/api/v1/films/$filmId"
Assert-Status $filmDetail 200 "film details should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/api/v1/films/{film_id}" -Method "GET" -StatusCode "200" -Value $filmDetail.body

$filmInvalidId = Invoke-Json -Method Get -Url "$base/api/v1/films/not-a-uuid"
Assert-Status $filmInvalidId 422 "film details with invalid UUID should be 422"

$filmMissing = Invoke-Json -Method Get -Url "$base/api/v1/films/00000000-0000-0000-0000-000000000000"
Assert-Status $filmMissing 404 "film details for missing UUID should be 404"

$filmSearch = Invoke-Json -Method Get -Url "$base/api/v1/films/search?query=star&page_number=1&page_size=50"
Assert-Status $filmSearch 200 "film search should be 200"
if ($null -eq $filmSearch.body) { throw "film search returned HTTP 200 but body is null. Raw: $($filmSearch.raw)" }
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/api/v1/films/search" -Method "GET" -StatusCode "200" -Value $filmSearch.body
if (@($filmSearch.body).Count -lt 1) { throw "film search returned empty result for 'star'" }

$badSearch = Invoke-Json -Method Get -Url "$base/api/v1/films/search?query=&page_number=1&page_size=10"
Assert-Status $badSearch 422 "empty query should be 422"

$genres = Invoke-Json -Method Get -Url "$base/api/v1/genres/?page_number=1&page_size=10"
Assert-Status $genres 200 "genres list should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/api/v1/genres/" -Method "GET" -StatusCode "200" -Value $genres.body
$genre0 = Get-FirstItem -Value $genres.body -Hint "genres"
Assert-HasKeys -Obj $genre0 -Keys @("uuid","name") -Context "genre list item"
$genreId = $genre0.uuid

$genreDetail = Invoke-Json -Method Get -Url "$base/api/v1/genres/$genreId"
Assert-Status $genreDetail 200 "genre details should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/api/v1/genres/{genre_id}" -Method "GET" -StatusCode "200" -Value $genreDetail.body

$genreInvalidId = Invoke-Json -Method Get -Url "$base/api/v1/genres/not-a-uuid"
Assert-Status $genreInvalidId 422 "genre details with invalid UUID should be 422"

$genreMissing = Invoke-Json -Method Get -Url "$base/api/v1/genres/00000000-0000-0000-0000-000000000000"
Assert-Status $genreMissing 404 "genre details for missing UUID should be 404"

$genreSearch = Invoke-Json -Method Get -Url "$base/api/v1/genres/search?query=Drama&page_number=1&page_size=50"
Assert-Status $genreSearch 200 "genre search should be 200"
if ($null -eq $genreSearch.body) { throw "genre search returned HTTP 200 but body is null. Raw: $($genreSearch.raw)" }
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/api/v1/genres/search" -Method "GET" -StatusCode "200" -Value $genreSearch.body
if (@($genreSearch.body).Count -lt 1) { throw "genre search returned empty result for 'Drama'" }

$genreBadSearch = Invoke-Json -Method Get -Url "$base/api/v1/genres/search?query=&page_number=1&page_size=10"
Assert-Status $genreBadSearch 422 "empty genre query should be 422"

$filmsByGenre = Invoke-Json -Method Get -Url "$base/api/v1/films/?page_number=1&page_size=10&genre=$genreId"
Assert-Status $filmsByGenre 200 "films filtered by genre should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/api/v1/films/" -Method "GET" -StatusCode "200" -Value $filmsByGenre.body

$persons = Invoke-Json -Method Get -Url "$base/api/v1/persons/?page_number=1&page_size=10"
Assert-Status $persons 200 "persons list should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/api/v1/persons/" -Method "GET" -StatusCode "200" -Value $persons.body
$person0 = Get-FirstItem -Value $persons.body -Hint "persons"
Assert-HasKeys -Obj $person0 -Keys @("uuid","full_name") -Context "person list item"
$personId = $person0.uuid

$personDetail = Invoke-Json -Method Get -Url "$base/api/v1/persons/$personId"
Assert-Status $personDetail 200 "person details should be 200"
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/api/v1/persons/{person_id}" -Method "GET" -StatusCode "200" -Value $personDetail.body

$personInvalidId = Invoke-Json -Method Get -Url "$base/api/v1/persons/not-a-uuid"
Assert-Status $personInvalidId 422 "person details with invalid UUID should be 422"

$personMissing = Invoke-Json -Method Get -Url "$base/api/v1/persons/00000000-0000-0000-0000-000000000000"
Assert-Status $personMissing 404 "person details for missing UUID should be 404"

$personSearch = Invoke-Json -Method Get -Url "$base/api/v1/persons/search?query=Alex&page_number=1&page_size=50"
Assert-Status $personSearch 200 "person search should be 200"
if ($null -eq $personSearch.body) { throw "person search returned HTTP 200 but body is null. Raw: $($personSearch.raw)" }
Assert-JsonMatchesOpenApiResponse -Spec $spec -Path "/api/v1/persons/search" -Method "GET" -StatusCode "200" -Value $personSearch.body
if (@($personSearch.body).Count -lt 1) { throw "person search returned empty result for 'Alex'" }

$personBadSearch = Invoke-Json -Method Get -Url "$base/api/v1/persons/search?query=&page_number=1&page_size=10"
Assert-Status $personBadSearch 422 "empty person query should be 422"

Write-Host "Async API OK [OK]" -ForegroundColor Green