[CmdletBinding()]
param([string]$Root = 'F:\ManiMind-Remote')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = '1'
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
$receipt = Join-Path $Root 'voxcpm2-setup-receipt.json'
if (Test-Path -LiteralPath $receipt) { throw 'Setup receipt exists; inspect before changing the installation' }
$python = Join-Path $Root '.venv-voxcpm2\Scripts\python.exe'
$requirements = Join-Path $Root 'voxcpm2-5080-requirements.txt'
$uv = (Get-Command uv -CommandType Application | Select-Object -First 1).Source
$started = [DateTimeOffset]::UtcNow.ToString('o')
New-Item -ItemType Directory -Path (Join-Path $Root 'setup-logs') -Force | Out-Null
$log = Join-Path $Root ('setup-logs\voxcpm2-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '.log')
Start-Transcript -LiteralPath $log | Out-Null
try {
    if (-not (Test-Path -LiteralPath $python)) {
        & $uv venv --python 3.12.13 (Join-Path $Root '.venv-voxcpm2')
        if ($LASTEXITCODE -ne 0) { throw 'Dedicated VoxCPM environment creation failed' }
    }
    & $uv pip install --python $python --index-url https://download.pytorch.org/whl/cu128 'torch==2.11.0' 'torchaudio==2.11.0'
    if ($LASTEXITCODE -ne 0) { throw 'VoxCPM CUDA dependencies failed' }
    & $uv pip install --python $python --index-url https://pypi.org/simple -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'VoxCPM dependencies failed; preserve logs' }
    $freeze = @(& $uv pip freeze --python $python)
    if ($LASTEXITCODE -ne 0) { throw 'Environment inventory failed' }
    $freezePath = Join-Path $Root 'voxcpm2-requirements-frozen.txt'
    $freeze | Set-Content -LiteralPath $freezePath -Encoding UTF8
    $modelId = 'openbmb/VoxCPM2'
    $revision = '32279effe8c19989596f05d353d1447f51d9e915'
    $metadata = Invoke-RestMethod -Uri ('https://huggingface.co/api/models/' + $modelId + '/revision/' + $revision + '?blobs=true')
    if ($metadata.sha -ne $revision) { throw 'Official revision mismatch' }
    $model = Join-Path $Root 'models\VoxCPM2'
    New-Item -ItemType Directory -Path $model -Force | Out-Null
    $files = @()
    foreach ($entry in $metadata.siblings) {
        $name = [string]$entry.rfilename
        if ($name.Contains('..') -or $name.Contains(':') -or [IO.Path]::IsPathRooted($name)) { throw 'Unexpected model path' }
        $target = Join-Path $model $name
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        if (-not (Test-Path -LiteralPath $target)) {
            $partial = $target + '.download'
            & curl.exe --fail --location --retry 3 --connect-timeout 30 --continue-at - --output $partial ('https://huggingface.co/' + $modelId + '/resolve/' + $revision + '/' + $name)
            if ($LASTEXITCODE -ne 0) { throw ('Pinned download failed: ' + $name) }
        }
        else { $partial = $target }
        $actual = (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($null -ne $entry.PSObject.Properties['lfs']) {
            if ($actual -ne $entry.lfs.sha256) { throw ('Official weight mismatch: ' + $name) }
        }
        else {
            $bytes = [IO.File]::ReadAllBytes($partial)
            $prefix = [Text.Encoding]::UTF8.GetBytes(('blob ' + $bytes.Length + [char]0))
            $h = [Security.Cryptography.SHA1]::Create()
            try { $blob = ([BitConverter]::ToString($h.ComputeHash([byte[]]($prefix + $bytes)))).Replace('-', '').ToLowerInvariant() }
            finally { $h.Dispose() }
            if ($blob -ne $entry.blobId) { throw ('Official file mismatch: ' + $name) }
        }
        if ($partial -ne $target) { Move-Item -LiteralPath $partial -Destination $target }
        $files += [pscustomobject]@{file=$name; sha256=$actual; official_blob=$entry.blobId}
        Write-Output ('Verified ' + $name)
    }
    [ordered]@{
        schema_version=1; model_id=$modelId; revision=$revision; model_path=$model; files=$files
        declared_license=$metadata.cardData.license; started_at=$started; finished_at=[DateTimeOffset]::UtcNow.ToString('o')
        python=$python; requirements_sha256=(Get-FileHash $requirements -Algorithm SHA256).Hash.ToLowerInvariant()
        frozen_environment_sha256=(Get-FileHash $freezePath -Algorithm SHA256).Hash.ToLowerInvariant(); transcript=$log
        writer='VoxCPM2 dedicated provisioner'; consumers=@('audition worker','operator','auditor')
        lifecycle='This pinned dedicated environment and model copy'; invalidation='Model, dependencies, configuration or permissions change'
        scope='Only new VoxCPM environment/model; no reference recordings, existing speech or advertising environment changes'
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $receipt -Encoding UTF8
    Write-Output ('VoxCPM2 installed: ' + $receipt)
}
finally { Stop-Transcript | Out-Null }
