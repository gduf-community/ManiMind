[CmdletBinding()]
param(
    [string]$Root = 'F:\ManiMind-Remote',
    [Parameter(Mandatory=$true)][string]$Source
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$receipt = Join-Path $Root 'voicedesign-setup-receipt.json'
if (Test-Path -LiteralPath $receipt) { throw 'Existing setup receipt: verify it instead of replacing it' }
$modelId = 'Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign'
$revision = '5ecdb67327fd37bb2e042aab12ff7391903235d3'
$model = Join-Path $Root 'models\Qwen3-TTS-12Hz-1.7B-VoiceDesign'
$metadata = Invoke-RestMethod -Uri ('https://huggingface.co/api/models/' + $modelId + '/revision/' + $revision + '?blobs=true')
if ($metadata.sha -ne $revision) { throw 'Official revision mismatch' }
$files = @()
foreach ($entry in $metadata.siblings) {
    $name = [string]$entry.rfilename
    if ($name.Contains('..') -or [IO.Path]::IsPathRooted($name)) { throw 'Unexpected model path' }
    $target = Join-Path $model $name
    $candidate = Join-Path $Source $name
    $lfs = $null -ne $entry.PSObject.Properties['lfs']
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    $origin = 'existing-dedicated-copy'
    if (-not (Test-Path -LiteralPath $target)) {
        $copy = $false
        if (Test-Path -LiteralPath $candidate) {
            if ($lfs) { $copy = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant() -eq $entry.lfs.sha256 }
            else {
                $bytes = [IO.File]::ReadAllBytes($candidate)
                $prefix = [Text.Encoding]::UTF8.GetBytes(('blob ' + $bytes.Length + [char]0))
                $h = [Security.Cryptography.SHA1]::Create()
                try { $copy = ([BitConverter]::ToString($h.ComputeHash([byte[]]($prefix + $bytes)))).Replace('-', '').ToLowerInvariant() -eq $entry.blobId }
                finally { $h.Dispose() }
            }
        }
        if ($copy) { Copy-Item -LiteralPath $candidate -Destination $target; $origin = 'verified-public-file-from-local-cache' }
        else {
            Invoke-WebRequest -UseBasicParsing -Uri ('https://huggingface.co/' + $modelId + '/resolve/' + $revision + '/' + $name) -OutFile $target
            $origin = 'official-pinned-download'
        }
    }
    $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($lfs) {
        if ($actual -ne $entry.lfs.sha256) { throw ('Official weight mismatch: ' + $name) }
    }
    else {
        $bytes = [IO.File]::ReadAllBytes($target)
        $prefix = [Text.Encoding]::UTF8.GetBytes(('blob ' + $bytes.Length + [char]0))
        $h = [Security.Cryptography.SHA1]::Create()
        try { $blob = ([BitConverter]::ToString($h.ComputeHash([byte[]]($prefix + $bytes)))).Replace('-', '').ToLowerInvariant() }
        finally { $h.Dispose() }
        if ($blob -ne $entry.blobId) { throw ('Official configuration mismatch: ' + $name) }
    }
    $files += [pscustomobject]@{file=$name; sha256=$actual; official_blob=$entry.blobId; origin=$origin}
}
[ordered]@{
    schema_version=1; model_id=$modelId; revision=$revision; model_path=$model; files=$files
    finished_at=[DateTimeOffset]::UtcNow.ToString('o'); declared_license=$metadata.cardData.license
    writer='VoiceDesign model provisioner'; consumers=@('audition worker','operator','auditor')
    lifecycle='This pinned dedicated model copy'; invalidation='Any model or configuration change'
    scope='Official model files only; no old recordings, private speaker databases or environment modifications'
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $receipt -Encoding UTF8
Write-Output ('VoiceDesign model ready: ' + $receipt)
