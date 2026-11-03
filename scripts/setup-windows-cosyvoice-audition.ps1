[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$SourceModel, [string]$Root = 'F:\ManiMind-Remote')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$modelId = 'FunAudioLLM/Fun-CosyVoice3-0.5B-2512'
$revision = '29e01c4e8d000f4bcd70751be16fa94bf3d85a18'
$metadata = Invoke-RestMethod -Uri ('https://huggingface.co/api/models/' + $modelId + '?blobs=true')
if ($metadata.sha -ne $revision) { throw 'Official model revision changed; inspect before provisioning' }
$model = Join-Path $Root 'models\Fun-CosyVoice3-0.5B-2512'
$needed = @('llm.pt', 'flow.pt', 'hift.pt', 'campplus.onnx', 'speech_tokenizer_v3.onnx',
    'cosyvoice3.yaml', 'config.json', 'configuration.json', 'CosyVoice-BlankEN/config.json',
    'CosyVoice-BlankEN/generation_config.json', 'CosyVoice-BlankEN/merges.txt',
    'CosyVoice-BlankEN/model.safetensors', 'CosyVoice-BlankEN/tokenizer_config.json', 'CosyVoice-BlankEN/vocab.json')
$verified = @()
foreach ($relative in $needed) {
    $published = @($metadata.siblings | Where-Object rfilename -eq $relative)
    if ($published.Count -ne 1) { throw ('Missing official file: ' + $relative) }
    $target = Join-Path $model $relative
    New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
    $lfs = $published[0].PSObject.Properties['lfs']
    $expected = if ($lfs) { [string]$lfs.Value.sha256 } else { '' }
    $method = 'official_https_download'
    $copied = $false
    if ($expected) {
        if ((Test-Path -LiteralPath $target) -and (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expected) {
            $copied = $true; $method = 'verified_existing_copy'
        } else {
            $source = Join-Path $SourceModel $relative
            if ((Test-Path -LiteralPath $source) -and (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expected) {
                Copy-Item -LiteralPath $source -Destination $target -Force
                $copied = $true; $method = 'official_hash_matched_local_copy'
            }
        }
    }
    if (-not $copied) {
        Invoke-WebRequest -UseBasicParsing -Uri ('https://huggingface.co/' + $modelId + '/resolve/' + $revision + '/' + $relative) -OutFile $target
    }
    $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expected -and $actual -ne $expected) { throw ('Official model hash mismatch: ' + $relative) }
    $verified += [pscustomobject]@{ file = $relative; sha256 = $actual; method = $method }
}
if (Test-Path -LiteralPath (Join-Path $model 'spk2info.pt')) { throw 'Unexpected speaker database in clean audition model directory' }
$referenceUrl = 'https://raw.githubusercontent.com/FunAudioLLM/CosyVoice/074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc/asset/zero_shot_prompt.wav'
$reference = Join-Path $Root 'audition-assets\cosyvoice-official-reference.wav'
New-Item -ItemType Directory -Path (Split-Path $reference) -Force | Out-Null
Invoke-WebRequest -UseBasicParsing -Uri $referenceUrl -OutFile $reference
$receipt = [ordered]@{ model_id = $modelId; revision = $revision; model_path = $model; files = $verified;
    reference = $reference; reference_source = $referenceUrl;
    reference_sha256 = (Get-FileHash -LiteralPath $reference -Algorithm SHA256).Hash.ToLowerInvariant();
    scope = 'Public official assets only; no private speaker database or cloned voices; internal audition, not commercial voice clearance';
    writer = 'CosyVoice audition provisioner'; consumers = @('audition runner', 'maintainer');
    lifecycle = 'This pinned public model and reference'; invalidation = 'Model, source or reference hashes change' }
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Root 'cosyvoice-audition-setup.json') -Encoding UTF8
[pscustomobject]$receipt | Select-Object model_id,revision,model_path,reference,reference_sha256,scope | ConvertTo-Json
