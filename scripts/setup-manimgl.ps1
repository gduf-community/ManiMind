<#
.SYNOPSIS
Create the repository-local ManimGL environment used by ManiMind.
#>

param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Python = "python"
)

$environmentPath = Join-Path $Root "manimgl_env"
$environmentPython = Join-Path $environmentPath "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $environmentPython)) {
    & $Python -m venv $environmentPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create ManimGL virtual environment."
    }
}

& $environmentPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip in ManimGL environment."
}

& $environmentPython -m pip install "setuptools<81" "manimgl>=1.7.2,<1.8"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install ManimGL dependencies."
}

Write-Host "ManimGL environment ready: $environmentPath"
Write-Host "Renderer: $(Join-Path $environmentPath 'Scripts\manimgl.exe')"
