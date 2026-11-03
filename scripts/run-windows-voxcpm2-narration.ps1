[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Output,
      [Parameter(Mandatory=$true)][string]$WorkerDirectory,
      [Parameter(Mandatory=$true)][string]$Plan,
      [Parameter(Mandatory=$true)][string]$Reference,
      [string]$Root = 'F:\ManiMind-Remote')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
if (Test-Path -LiteralPath $Output) { throw 'Existing narration attempt; inspect before retrying' }
$attempt = Split-Path -Path $Output -Leaf
if ($attempt -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,100}$') { throw 'Use a unique simple attempt name' }
$stdout = Join-Path $Root ('logs\' + $attempt + '.stdout.log')
$stderr = Join-Path $Root ('logs\' + $attempt + '.stderr.log')
$restorePath = Join-Path $Root ('logs\' + $attempt + '-service-restore.json')
if ((Test-Path $stdout) -or (Test-Path $stderr) -or (Test-Path $restorePath)) { throw 'Existing attempt evidence' }
$mutex = New-Object Threading.Mutex($false, 'Global\ManiMind-VoiceDesign-Audition')
if (-not $mutex.WaitOne(0)) { $mutex.Dispose(); throw 'Another speech worker owns the GPU slot' }
$restore = $false
try {
    if ([string](Get-ScheduledTask -TaskName 'ManiMind-QwenVoice-5080').State -eq 'Running' -or
        (Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue)) {
        throw 'Pause Qwen in an operator-coordinated exclusive maintenance window first'
    }
    $token = [IO.File]::ReadAllText((Join-Path $Root 'private\speech.token')).Trim()
    $argsList = @('-u','-B',(Join-Path $WorkerDirectory 'voxcpm_narration.py'),'generate','--model',(Join-Path $Root 'models\VoxCPM2'),
        '--output',$Output,'--setup-receipt',(Join-Path $Root 'voxcpm2-setup-receipt.json'),'--plan',$Plan,'--reference',$Reference)
    if (@($argsList | Where-Object { $_.Contains('"') -or $_.EndsWith('\') }).Count) { throw 'Unsupported quoted or trailing-separator argument' }
    $quotedArgs = @($argsList | ForEach-Object { '"' + $_ + '"' }) -join ' '
    if ((Test-Path $stdout) -or (Test-Path $stderr) -or (Test-Path $restorePath)) { throw 'Attempt evidence appeared while acquiring GPU slot' }
    $restore = $true
    $env:PYTHONUTF8 = '1'
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    $env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
    $env:HF_HOME = Join-Path $Root 'hf-cache-voxcpm2'
    $process = Start-Process -FilePath (Join-Path $Root '.venv-voxcpm2\Scripts\python.exe') -ArgumentList $quotedArgs -RedirectStandardOutput $stdout -RedirectStandardError $stderr -NoNewWindow -PassThru
    $null = $process.Handle
    while (-not $process.HasExited) {
        Start-Sleep -Seconds 8
        $state = Join-Path $Output 'state.json'
        if (Test-Path $state) {
            try { $s=Get-Content $state -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Output ($s | Select-Object status,attempted,done | ConvertTo-Json -Compress) }
            catch { Write-Output 'Narration state update in progress' }
        }
        $process.Refresh()
    }
    $process.WaitForExit()
    Get-Content $stdout -Encoding UTF8
    $exitCode = $process.ExitCode
    if ($null -eq $exitCode) { throw 'Process exit code unavailable; inspect the immutable worker state instead of rerunning' }
    if ($exitCode -ne 0) { Get-Content $stderr -Encoding UTF8; throw 'Narration failed; preserve attempt without automatic retry' }
}
finally {
    try {
        if ($restore) {
            $record = [ordered]@{status='restore_failed'; checked_at=[DateTimeOffset]::UtcNow.ToString('o'); inference_rerun=$false
                writer='VoxCPM2 narration maintenance runner'; consumers=@('operator','auditor')
                lifecycle='This maintenance attempt'; invalidation='New process, deployment or service state'}
            try {
                Start-ScheduledTask -TaskName 'ManiMind-QwenVoice-5080'
                $deadline = [DateTime]::UtcNow.AddSeconds(90)
                do {
                    try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/health' -Headers @{Authorization=('Bearer ' + $token)} -TimeoutSec 3 } catch { $health = $null }
                    if ($null -ne $health -and $health.status -eq 'ready') {
                        if ($health.engine.worker_sha256 -ne '555ee3544a45e2ab090d974e1f3c0f3cfb04db7eb0450b89f7f570d3e576ec93' -or $health.engine.model_files_sha256 -ne 'c1d77e1fbb1a24e2474cea448e9d2e34f3b52a207d1fa7d8040bf033f7701766') { throw 'Original engine identity changed' }
                        $record.status='restored_ready'; $record['engine']=$health.engine; break
                    }
                    Start-Sleep -Seconds 2
                } while ([DateTime]::UtcNow -lt $deadline)
                if ($record.status -ne 'restored_ready') { throw 'Original Qwen did not become ready within 90 seconds' }
                Write-Output 'Original Qwen service verified ready'
            }
            catch { $record['error']=$_.Exception.Message; throw }
            finally {
                $bytes=[Text.Encoding]::UTF8.GetBytes(($record | ConvertTo-Json -Depth 5))
                $stream=[IO.File]::Open($restorePath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
                try { $stream.Write($bytes,0,$bytes.Length) } finally { $stream.Dispose() }
            }
        }
    }
    finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
}
