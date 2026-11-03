[CmdletBinding()]
param(
    [string]$Root = 'F:\ManiMind-Remote',
    [string]$Requirements = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = '1'
$uv = (Get-Command uv -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$Root = [IO.Path]::GetFullPath($Root)
if ([string]::IsNullOrWhiteSpace($Requirements)) { $Requirements = Join-Path $Root 'qwen-5080-requirements.txt' }
if (-not (Test-Path -LiteralPath $Requirements)) { throw 'Pinned requirements file is missing' }
$python = Join-Path $Root '.venv\Scripts\python.exe'
$logDirectory = Join-Path $Root 'setup-logs'
New-Item -ItemType Directory -Path $Root, $logDirectory -Force | Out-Null
$log = Join-Path $logDirectory ('setup-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '.log')
Start-Transcript -LiteralPath $log | Out-Null
try {
    if (-not (Test-Path -LiteralPath $python)) {
        & $uv venv --python 3.12.13 (Join-Path $Root '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Dedicated Python environment creation failed' }
    }
    & $uv pip install --python $python --index-url https://download.pytorch.org/whl/cu128 'torch==2.11.0' 'torchaudio==2.11.0'
    if ($LASTEXITCODE -ne 0) { throw 'CUDA runtime installation failed' }
    & $uv pip install --python $python --index-url https://pypi.org/simple -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw 'Speech dependencies installation failed' }

    $modelId = 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'
    $metadata = Invoke-RestMethod -Uri ('https://huggingface.co/api/models/' + $modelId + '?blobs=true')
    $revision = [string]$metadata.sha
    if ($revision -notmatch '^[0-9a-f]{40}$') { throw 'Invalid official model revision' }
    $model = Join-Path $Root 'models\Qwen3-TTS-12Hz-1.7B-CustomVoice'
    $env:HF_HOME = Join-Path $Root 'hf-cache'
    $env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
    Remove-Item Env:HF_TOKEN -ErrorAction SilentlyContinue
    $hf = Join-Path $Root '.venv\Scripts\hf.exe'
    & $hf download $modelId --revision $revision --local-dir $model
    if ($LASTEXITCODE -ne 0) { throw 'Official model download failed; preserve partial cache' }
    $verified = @()
    foreach ($relative in @('model.safetensors', 'speech_tokenizer/model.safetensors')) {
        $published = @($metadata.siblings | Where-Object rfilename -eq $relative)
        if ($published.Count -ne 1 -or -not $published[0].lfs.sha256) { throw 'Missing official weight hash' }
        $actual = (Get-FileHash -LiteralPath (Join-Path $model $relative) -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $published[0].lfs.sha256) { throw ('Model weight hash mismatch: ' + $relative) }
        $verified += [pscustomobject]@{ file = $relative; sha256 = $actual }
    }
    $freeze = @(& $uv pip freeze --python $python)
    if ($LASTEXITCODE -ne 0) { throw 'Environment inventory failed' }
    $freeze | Set-Content -LiteralPath (Join-Path $Root 'requirements-frozen.txt') -Encoding UTF8
    $record = [ordered]@{
        schema_version = 1
        finished_at = [DateTimeOffset]::UtcNow.ToString('o')
        model_id = $modelId
        model_revision = $revision
        model_path = $model
        weights = $verified
        python = $python
        requirements_sha256 = (Get-FileHash -LiteralPath $Requirements -Algorithm SHA256).Hash.ToLowerInvariant()
        frozen_environment = (Join-Path $Root 'requirements-frozen.txt')
        transcript = $log
        writer = 'Dedicated speech environment provisioner'
        consumers = @('operator', 'GPU worker', 'auditor')
        lifecycle = 'This installed environment and pinned model revision'
        invalidation = 'Environment, weights, source or permissions changes'
        limitations = @('Installation only; no generation or listening acceptance')
    }
    $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Root 'setup-receipt.json') -Encoding UTF8
    $record | ConvertTo-Json -Depth 6
}
finally {
    Stop-Transcript | Out-Null
}
