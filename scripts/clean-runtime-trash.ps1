[CmdletBinding()]
param(
    [string]$Root = ".",
    [switch]$DryRun,
    [switch]$IncludeLogs
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host $Message -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host $Message -ForegroundColor Green
}

function Write-WarnMsg([string]$Message) {
    Write-Host $Message -ForegroundColor Yellow
}

function Remove-ItemSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    if ($DryRun) {
        Write-Host "[DRY-RUN] remove $Path" -ForegroundColor DarkYellow
        return
    }

    try {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        Write-Host "[REMOVED] $Path" -ForegroundColor DarkGreen
    }
    catch {
        Write-WarnMsg "[SKIPPED] $Path :: $($_.Exception.Message)"
    }
}

$rootPath = Resolve-Path $Root
Write-Info "Cleanup root: $rootPath"

$excludeDirNames = @(
    ".git",
    ".venv",
    "venv",
    "node_modules"
)

$trashDirNames = @(
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "htmlcov",
    "test-results",
    "reports",
    "allure-results",
    "allure-report"
)

$trashFilePatterns = @(
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".coverage",
    ".coverage.*",
    ".DS_Store",
    "Thumbs.db"
)

if ($IncludeLogs) {
    $trashFilePatterns += "*.log"
}

Write-Info "Searching directories to remove..."

$dirsToRemove = New-Object System.Collections.Generic.List[string]

Get-ChildItem -LiteralPath $rootPath -Recurse -Force -Directory |
    Where-Object {
        $name = $_.Name
        $full = $_.FullName

        foreach ($excluded in $excludeDirNames) {
            if ($full -match [regex]::Escape("\$excluded\")) {
                return $false
            }
            if ($full.EndsWith("\$excluded")) {
                return $false
            }
        }

        return $trashDirNames -contains $name
    } |
    ForEach-Object {
        $dirsToRemove.Add($_.FullName)
    }

Write-Info "Searching files to remove..."

$filesToRemove = New-Object System.Collections.Generic.List[string]

Get-ChildItem -LiteralPath $rootPath -Recurse -Force -File |
    Where-Object {
        $full = $_.FullName

        foreach ($excluded in $excludeDirNames) {
            if ($full -match [regex]::Escape("\$excluded\")) {
                return $false
            }
            if ($full.EndsWith("\$excluded")) {
                return $false
            }
        }

        foreach ($pattern in $trashFilePatterns) {
            if ($_.Name -like $pattern) {
                return $true
            }
        }

        return $false
    } |
    ForEach-Object {
        $filesToRemove.Add($_.FullName)
    }

Write-Info "Directories found: $($dirsToRemove.Count)"
Write-Info "Files found: $($filesToRemove.Count)"

if (($dirsToRemove.Count -eq 0) -and ($filesToRemove.Count -eq 0)) {
    Write-Ok "Nothing to clean."
    exit 0
}

Write-Info "Removing directories..."
foreach ($dir in ($dirsToRemove | Sort-Object -Descending)) {
    Remove-ItemSafe -Path $dir
}

Write-Info "Removing files..."
foreach ($file in $filesToRemove) {
    Remove-ItemSafe -Path $file
}

Write-Ok "Cleanup finished."