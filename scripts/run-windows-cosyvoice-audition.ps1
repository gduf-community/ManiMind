[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Repo, [Parameter(Mandatory=$true)][string]$Output, [string]$Root = 'F:\ManiMind-Remote')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$python = Join-Path $Repo '.venv\Scripts\python.exe'
$worker = Join-Path $Root 'cosyvoice_audition.py'
$request = Join-Path $Root 'cosyvoice-naturalness.request.json'
foreach ($path in @($python, $worker, $request, (Join-Path $Root 'cosyvoice-audition-setup.json'))) {
    if (-not (Test-Path -LiteralPath $path)) { throw ('Required audition input is missing: ' + $path) }
}
if (Test-Path -LiteralPath $Output) { throw 'Attempt directory exists; inspect instead of restarting or overwriting it' }
$task = 'ManiMind-QwenVoice-5080'
$restore = [string](Get-ScheduledTask -TaskName $task).State -eq 'Running'
if ($restore) {
    $token = [IO.File]::ReadAllText((Join-Path $Root 'private\speech.token')).Trim()
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/health' -Headers @{Authorization = ('Bearer ' + $token)}
    if ($health.busy) { throw 'Qwen is busy; do not interrupt its request' }
}
try {
    if ($restore) {
        Stop-ScheduledTask -TaskName $task
        Start-Sleep -Seconds 3
        if (Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue) { throw 'Qwen has not stopped; avoid competing GPU processes' }
    }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:HF_HOME = Join-Path $Root 'hf-cache-cosyvoice'
    $env:TORCH_HOME = Join-Path $Root 'torch-cache-cosyvoice'
    $env:MODELSCOPE_CACHE = Join-Path $Root 'modelscope-cache-cosyvoice'
    Set-Location -LiteralPath $Root
    & $python -u -B $worker --repo $Repo --setup-receipt (Join-Path $Root 'cosyvoice-audition-setup.json') --request $request --output $Output
    if ($LASTEXITCODE -ne 0) { throw ('Audition failed; retain log and state in ' + $Output) }
    Get-Content -LiteralPath (Join-Path $Output 'receipt.json') -Raw -Encoding UTF8
}
finally {
    if ($restore) { Start-ScheduledTask -TaskName $task }
}
