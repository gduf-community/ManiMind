[CmdletBinding()]
param([string]$Root = 'F:\ManiMind-Remote')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = '1'
$uv = (Get-Command uv -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$python = Join-Path $Root '.kokoro-venv\Scripts\python.exe'
$requirements = Join-Path $Root 'kokoro-5080-requirements.txt'
$receipt = Join-Path $Root 'kokoro-setup-receipt.json'
if (Test-Path -LiteralPath $receipt) { throw 'Existing setup receipt: inspect before changing this environment' }
if (-not (Test-Path -LiteralPath $requirements)) { throw 'Pinned requirements are missing' }
$log = Join-Path $Root ('setup-logs\kokoro-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '.log')
Start-Transcript -LiteralPath $log | Out-Null
try {
    if (-not (Test-Path -LiteralPath $python)) {
        & $uv venv --python 3.12.13 (Join-Path $Root '.kokoro-venv')
        if ($LASTEXITCODE -ne 0) { throw 'Dedicated environment creation failed' }
    }
    & $uv pip install --python $python --index-url https://download.pytorch.org/whl/cu128 'torch==2.11.0'
    if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch installation failed' }
    & $uv pip install --python $python --index-url https://pypi.org/simple -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Kokoro dependency installation failed' }
    $modelId = 'hexgrad/Kokoro-82M'
    $revision = 'f3ff3571791e39611d31c381e3a41a3af07b4987'
    $model = Join-Path $Root 'models\Kokoro-82M-v1_0'
    $metadata = Invoke-RestMethod -Uri ('https://huggingface.co/api/models/' + $modelId + '/revision/' + $revision + '?blobs=true')
    if ($metadata.sha -ne $revision) { throw 'Official model revision mismatch' }
    $voices = @('zf_xiaobei', 'zf_xiaoni', 'zf_xiaoxiao', 'zf_xiaoyi', 'zm_yunjian', 'zm_yunxi', 'zm_yunxia', 'zm_yunyang')
    $names = @('config.json', 'kokoro-v1_0.pth', 'README.md', 'VOICES.md') + @($voices | ForEach-Object { 'voices/' + $_ + '.pt' })
    $files = @()
    foreach ($name in $names) {
        $target = Join-Path $model $name
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        if (-not (Test-Path -LiteralPath $target)) {
            Invoke-WebRequest -UseBasicParsing -Uri ('https://huggingface.co/' + $modelId + '/resolve/' + $revision + '/' + $name) -OutFile $target
        }
        $published = @($metadata.siblings | Where-Object rfilename -eq $name)
        if ($published.Count -ne 1) { throw ('Missing official model file: ' + $name) }
        $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($name.EndsWith('.pth') -or $name.EndsWith('.pt')) {
            if ($actual -ne $published[0].lfs.sha256) { throw ('Weight hash mismatch: ' + $name) }
        }
        else {
            $bytes = [IO.File]::ReadAllBytes($target)
            $prefix = [Text.Encoding]::UTF8.GetBytes(('blob ' + $bytes.Length + [char]0))
            $hasher = [Security.Cryptography.SHA1]::Create()
            try { $blob = ([BitConverter]::ToString($hasher.ComputeHash([byte[]]($prefix + $bytes)))).Replace('-', '').ToLowerInvariant() }
            finally { $hasher.Dispose() }
            if ($blob -ne $published[0].blobId) { throw ('Official Git blob mismatch: ' + $name) }
        }
        $files += [pscustomobject]@{file=$name; sha256=$actual}
    }
    & $uv pip freeze --python $python | Set-Content -LiteralPath (Join-Path $Root 'kokoro-requirements-frozen.txt') -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw 'Environment inventory failed' }
    [ordered]@{
        schema_version=1; model_id=$modelId; revision=$revision; model_path=$model; files=$files; declared_license=$metadata.cardData.license
        python=$python; transcript=$log; finished_at=[DateTimeOffset]::UtcNow.ToString('o')
        requirements_sha256=(Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash.ToLowerInvariant()
        writer='Dedicated Kokoro provisioner'; consumers=@('operator','audition worker','auditor')
        lifecycle='This dedicated environment and pinned model'; invalidation='Packages, weights or setup source changes'
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $receipt -Encoding UTF8
    Write-Output ('Kokoro setup ready: ' + $receipt)
}
finally { Stop-Transcript | Out-Null }
