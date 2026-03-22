function Get-EnvOrDefault([string]$name, [string]$default) {
  $v = [Environment]::GetEnvironmentVariable($name)
  if ([string]::IsNullOrWhiteSpace($v)) { return $default }
  return $v
}

function Convert-ResponseContentToString {
  param($Content)

  if ($null -eq $Content) { return $null }
  if ($Content -is [string]) { return $Content }
  if ($Content -is [char[]]) { return (-join $Content) }
  if ($Content -is [byte[]]) { return [Text.Encoding]::UTF8.GetString($Content) }

  if ($Content -is [System.Array]) {
    $items = @($Content)
    if ($items.Count -gt 0 -and $items[0] -is [byte]) {
      return [Text.Encoding]::UTF8.GetString([byte[]]$items)
    }
    if ($items.Count -gt 0 -and $items[0] -is [char]) {
      return (-join [char[]]$items)
    }
  }

  return [string]$Content
}

function ConvertTo-StableJsonValue {
  param($Value)

  if ($null -eq $Value) { return $null }
  if (
    $Value -is [string] -or $Value -is [char] -or $Value -is [bool] -or
    $Value -is [byte] -or $Value -is [int16] -or $Value -is [int32] -or
    $Value -is [int64] -or $Value -is [single] -or $Value -is [double] -or
    $Value -is [decimal]
  ) {
    return $Value
  }

  if ($Value -is [System.Collections.IDictionary]) {
    $obj = [ordered]@{}
    foreach ($key in @($Value.Keys)) {
      $obj[[string]$key] = ConvertTo-StableJsonValue $Value[$key]
    }
    return [pscustomobject]$obj
  }

  if ($Value -is [System.Collections.IEnumerable] -and $Value -isnot [string]) {
    $arr = @()
    foreach ($item in $Value) {
      $arr += ,(ConvertTo-StableJsonValue $item)
    }
    return ,$arr
  }

  return $Value
}

function Test-IsJsonArray {
  param($Value)

  return (
    $Value -is [System.Collections.IEnumerable] -and
    $Value -isnot [string] -and
    $Value -isnot [System.Collections.IDictionary] -and
    $Value -isnot [pscustomobject]
  )
}

function ConvertFrom-JsonStable {
  param(
    [Parameter(Mandatory=$true)][string]$JsonText
  )

  if ([string]::IsNullOrWhiteSpace($JsonText)) { return $null }

  try {
    Add-Type -AssemblyName System.Web.Extensions -ErrorAction Stop | Out-Null
    $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $serializer.MaxJsonLength = [int]::MaxValue
    $rawValue = $serializer.DeserializeObject($JsonText)
    return ConvertTo-StableJsonValue $rawValue
  } catch {
    $parsed = $JsonText | ConvertFrom-Json
    $trimmed = $JsonText.TrimStart()
    if ($trimmed.StartsWith('[')) {
      if ($null -eq $parsed) {
        return ,@()
      }
      if (-not (Test-IsJsonArray $parsed)) {
        return ,@($parsed)
      }
    }
    return $parsed
  }
}

function Invoke-Json {
  param(
    [Parameter(Mandatory=$true)][string]$Method,
    [Parameter(Mandatory=$true)][string]$Url,
    [hashtable]$Headers = @{},
    $Body = $null
  )

  $bodyStr = $null
  if ($null -ne $Body) {
    if ($Body -is [string]) { $bodyStr = $Body }
    else { $bodyStr = ($Body | ConvertTo-Json -Depth 20 -Compress) }
  }

  try {
    $params = @{
      Method = $Method
      Uri = $Url
      Headers = $Headers
      ContentType = 'application/json; charset=utf-8'
      UseBasicParsing = $true
    }
    if ($null -ne $bodyStr) {
      $params.Body = [System.Text.Encoding]::UTF8.GetBytes($bodyStr)
    }

    $r = Invoke-WebRequest @params
    $status = [int]$r.StatusCode
    $raw = Convert-ResponseContentToString $r.Content
  } catch {
    $resp = $_.Exception.Response
    if ($null -eq $resp) { throw }

    $status = [int]$resp.StatusCode
    $raw = $null
    try {
      $reader = New-Object System.IO.StreamReader($resp.GetResponseStream(), [System.Text.Encoding]::UTF8)
      $raw = $reader.ReadToEnd()
      $reader.Close()
    } catch {
      try {
        $raw = Convert-ResponseContentToString $resp.Content
      } catch {}
    }
  }

  $parsed = $null
  if ($null -ne $raw) {
    $rawText = [string]$raw
    if (-not [string]::IsNullOrWhiteSpace($rawText)) {
      try {
        $parsed = ConvertFrom-JsonStable -JsonText $rawText
      } catch {
        $parsed = $null
      }
      $raw = $rawText
    } else {
      $raw = $rawText
    }
  }

  return @{ status = $status; body = $parsed; raw = $raw }
}

function Assert-Status {
  param(
    [Parameter(Mandatory=$true)]$Resp,
    [Parameter(Mandatory=$true)][int]$Expected,
    [string]$Hint = ''
  )
  if ($Resp.status -ne $Expected) {
    $msg = "Expected HTTP $Expected but got $($Resp.status). $Hint"
    if ($Resp.raw) { $msg += "`nResponse: $($Resp.raw)" }
    throw $msg
  }
}

function Assert-True {
  param(
    [Parameter(Mandatory=$true)][bool]$Condition,
    [Parameter(Mandatory=$true)][string]$Message
  )
  if (-not $Condition) { throw $Message }
}

function Ensure-Dir([string]$Path) {
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
  }
}

function Save-ArtifactJson([string]$Path, $Obj) {
  Ensure-Dir (Split-Path $Path)
  ($Obj | ConvertTo-Json -Depth 20) | Set-Content -Encoding UTF8 -Path $Path
}

function Load-ArtifactJson([string]$Path) {
  if (-not (Test-Path $Path)) {
    throw "Artifact not found: $Path"
  }
  Get-Content $Path -Raw | ConvertFrom-Json
}

function Get-DotEnvValue {
  param(
    [Parameter(Mandatory=$true)][string]$DotEnvPath,
    [Parameter(Mandatory=$true)][string]$Key,
    [string]$Default = ""
  )
  if (-not (Test-Path $DotEnvPath)) { return $Default }
  $lines = Get-Content $DotEnvPath
  foreach ($ln in $lines) {
    $s = $ln.Trim()
    if ($s -eq "" -or $s.StartsWith("#")) { continue }
    $idx = $s.IndexOf("=")
    if ($idx -lt 1) { continue }
    $k = $s.Substring(0, $idx).Trim()
    if ($k -ne $Key) { continue }
    $v = $s.Substring($idx + 1).Trim()
    if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
      $v = $v.Substring(1, $v.Length - 2)
    }
    if ([string]::IsNullOrWhiteSpace($v)) { return $Default }
    return $v
  }
  return $Default
}

function UrlEncode([string]$Value) {
  return [System.Uri]::EscapeDataString($Value)
}

function Assert-HasKeys {
  param(
    [Parameter(Mandatory=$true)]$Obj,
    [Parameter(Mandatory=$true)][string[]]$Keys,
    [string]$Context = 'response'
  )
  foreach ($k in $Keys) {
    if ($null -eq $Obj.PSObject.Properties[$k]) {
      throw "$Context missing key: $k"
    }
  }
}

function Assert-OpenApiPathExists {
  param(
    [Parameter(Mandatory=$true)]$Spec,
    [Parameter(Mandatory=$true)][string]$Path,
    [string[]]$Methods = @()
  )

  $paths = $Spec.paths
  if ($null -eq $paths) {
    throw 'OpenAPI spec has no paths section'
  }

  $pathNode = $null
  if ($paths -is [System.Collections.IDictionary]) {
    $pathNode = $paths[$Path]
  }
  if ($null -eq $pathNode -and $paths.PSObject.Properties[$Path]) {
    $pathNode = $paths.PSObject.Properties[$Path].Value
  }
  if ($null -eq $pathNode) {
    throw "OpenAPI path not found: $Path"
  }

  foreach ($method in $Methods) {
    $methodNode = $null
    if ($pathNode -is [System.Collections.IDictionary]) {
      $methodNode = $pathNode[$method.ToLower()]
    }
    if ($null -eq $methodNode -and $pathNode.PSObject.Properties[$method.ToLower()]) {
      $methodNode = $pathNode.PSObject.Properties[$method.ToLower()].Value
    }
    if ($null -eq $methodNode) {
      throw "OpenAPI method not found for ${Path}: $method"
    }
  }
}
