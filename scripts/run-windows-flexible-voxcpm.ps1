# The worker owns the GPU mutex during generation; restoration reacquires it only after exit.
# New attempt evidence is create-only; operators/auditors consume it as history.
# New process/deployment/input/service state invalidates it. Never retry an unknown take.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Output,
      [Parameter(Mandatory=$true)][string]$WorkerDirectory,
      [Parameter(Mandatory=$true)][string]$Plan,
      [Parameter(Mandatory=$true)][string]$Reference,
      [string]$GpuBaseline,
      [string]$Root = 'F:\ManiMind-Remote')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$Output = [IO.Path]::GetFullPath($Output)
$WorkerDirectory = [IO.Path]::GetFullPath($WorkerDirectory)
$Plan = [IO.Path]::GetFullPath($Plan)
$Reference = [IO.Path]::GetFullPath($Reference)
$Root = [IO.Path]::GetFullPath($Root)
if ($GpuBaseline) { $GpuBaseline = [IO.Path]::GetFullPath($GpuBaseline) }
if (Test-Path -LiteralPath $Output) { throw 'Existing attempt; inspect it without rerunning' }
$attempt = Split-Path -Path $Output -Leaf
if ($attempt -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,100}$' -or
    $attempt -match '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$') { throw 'Use a unique Windows-safe attempt name' }
$python = Join-Path $Root '.venv-voxcpm2\Scripts\python.exe'
$worker = Join-Path $WorkerDirectory 'flexible_voxcpm.py'
$setup = Join-Path $Root 'voxcpm2-setup-receipt.json'
foreach ($path in @($python, $worker, (Join-Path $WorkerDirectory 'voxcpm_audition.py'), $setup, $Plan, $Reference)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Missing required input; no worker started' }
}
if ($GpuBaseline -and -not (Test-Path -LiteralPath $GpuBaseline -PathType Leaf)) { throw 'Missing GPU baseline' }
$argsList = @('-u','-B',$worker,'generate','--model',(Join-Path $Root 'models\VoxCPM2'),
    '--output',$Output,'--setup-receipt',$setup,'--plan',$Plan,'--reference',$Reference)
if ($GpuBaseline) { $argsList += @('--gpu-baseline', $GpuBaseline) }
if (@($argsList | Where-Object { $_.Contains('"') -or $_.EndsWith('\') -or $_ -match '[\r\n\x00]' }).Count) {
    throw 'Unsupported quoted, control-character or trailing-separator argument'
}
$quotedArgs = @($argsList | ForEach-Object { '"' + $_ + '"' }) -join ' '
$logs = Join-Path $Root 'logs'
$null = [IO.Directory]::CreateDirectory($logs)
$stdout = Join-Path $logs ($attempt + '.stdout.log')
$stderr = Join-Path $logs ($attempt + '.stderr.log')
$restorePath = Join-Path $logs ($attempt + '-service-restore.json')
$claimPath = Join-Path $logs ($attempt + '-flexible-runner.json')
foreach ($path in @($stdout, $stderr, $restorePath, $claimPath)) {
    if (Test-Path -LiteralPath $path) { throw 'Existing attempt evidence; inspect without rerunning' }
}
# The create-only claim prevents two copies of this runner from starting the same attempt.
$claim = [IO.File]::Open($claimPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
try {
    $bytes = [Text.Encoding]::UTF8.GetBytes((([ordered]@{
        schema_version=1; writer='Flexible VoxCPM maintenance runner'; consumers=@('operator','auditor')
        lifecycle='One maintenance attempt'; invalidation='New process, inputs, deployment or service state'
        started_at=[DateTimeOffset]::UtcNow.ToString('o'); worker=$worker; plan=$Plan; reference=$Reference
        gpu_baseline=$GpuBaseline; output=$Output; automatic_retry=$false
    }) | ConvertTo-Json -Depth 4))
    $claim.Write($bytes, 0, $bytes.Length)
} finally { $claim.Dispose() }

$restore = $false
$started = $false
$process = $null
$outStream = $null
$errStream = $null
$outCopy = $null
$errCopy = $null
$workerExitCode = $null
try {
    $task = Get-ScheduledTask -TaskName 'ManiMind-QwenVoice-5080'
    $listeners = @(Get-NetTCPConnection -ErrorAction Stop | Where-Object { $_.LocalPort -eq 8766 -and $_.State -eq 'Listen' })
    if ([string]$task.State -ne 'Ready' -or $listeners.Count) {
        throw 'Qwen is online; coordinate maintenance and pause it explicitly before a NEW attempt'
    }
    $token = [IO.File]::ReadAllText((Join-Path $Root 'private\speech.token')).Trim()
    if ($token.Length -lt 32 -or $token -match '\s') { throw 'Private token file is invalid' }
    $outStream = [IO.File]::Open($stdout, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    $errStream = [IO.File]::Open($stderr, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    $env:PYTHONUTF8 = '1'
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    $env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
    $env:HF_HOME = Join-Path $Root 'hf-cache-voxcpm2'
    $process = New-Object Diagnostics.Process
    $process.StartInfo.FileName = $python
    $process.StartInfo.Arguments = $quotedArgs
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $restore = $true
    $started = $process.Start()
    if (-not $started) { throw 'Worker did not start; no automatic retry' }
    $outCopy = $process.StandardOutput.BaseStream.CopyToAsync($outStream)
    $errCopy = $process.StandardError.BaseStream.CopyToAsync($errStream)
    $processHandle = $process.Handle
    $process.WaitForExit()
    try { $workerExitCode = $process.ExitCode }
    catch { throw 'Worker exit code unavailable; preserve evidence and do not rerun' }
    if ($null -eq $workerExitCode) { throw 'Worker exit code unavailable; preserve evidence and do not rerun' }
    if ($workerExitCode -ne 0) { throw 'Worker failed; preserve first-take evidence without automatic retry' }
}
finally {
    try {
        # Never restore Qwen while a launched worker may still be using CUDA.
        if ($started) { $process.WaitForExit() }
        try { if ($null -ne $outCopy) { $outCopy.GetAwaiter().GetResult() } }
        finally { if ($null -ne $errCopy) { $errCopy.GetAwaiter().GetResult() } }
    }
    finally {
        if ($null -ne $outStream) { $outStream.Dispose() }
        if ($null -ne $errStream) { $errStream.Dispose() }
        if ($null -ne $process) { $process.Dispose() }
        if ($restore) {
            $record = [ordered]@{
                schema_version=1; status='restore_failed'; checked_at=[DateTimeOffset]::UtcNow.ToString('o')
                worker_exit_code=$workerExitCode; inference_rerun=$false
                writer='Flexible VoxCPM maintenance runner'; consumers=@('operator','auditor')
                lifecycle='This maintenance attempt only'; invalidation='New process, deployment or service state'
            }
            $restoreMutex = $null
            $restoreOwned = $false
            try {
                $record['failure_reason']='gpu_slot_not_clear_for_restore'
                $restoreMutex = New-Object Threading.Mutex($false, 'Global\ManiMind-VoiceDesign-Audition')
                try { $restoreOwned = $restoreMutex.WaitOne(0) }
                catch [Threading.AbandonedMutexException] {
                    $restoreOwned = $true
                    throw 'Abandoned GPU slot; inspect previous owner before restoring Qwen'
                }
                if (-not $restoreOwned) { throw 'Another worker owns GPU slot; do not start Qwen' }
                if ([string](Get-ScheduledTask -TaskName 'ManiMind-QwenVoice-5080').State -ne 'Ready') {
                    throw 'Qwen task is not enabled and ready for restoration'
                }
                $record['failure_reason']='task_start_or_health_inspection_failed'
                Start-ScheduledTask -TaskName 'ManiMind-QwenVoice-5080'
                $clock = [Diagnostics.Stopwatch]::StartNew()
                do {
                    $health = $null
                    $remaining = 90 - $clock.Elapsed.TotalSeconds
                    if ($remaining -le 0) { break }
                    $timeout = [int][Math]::Min(3, [Math]::Ceiling($remaining))
                    try {
                        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/health' -MaximumRedirection 0 `
                            -Headers @{Authorization=('Bearer ' + $token)} -TimeoutSec $timeout
                    } catch { $health = $null }
                    if ($null -ne $health -and $health.status -eq 'ready') {
                        if ($health.engine.worker_sha256 -cne '555ee3544a45e2ab090d974e1f3c0f3cfb04db7eb0450b89f7f570d3e576ec93' -or
                            $health.engine.model_files_sha256 -cne 'c1d77e1fbb1a24e2474cea448e9d2e34f3b52a207d1fa7d8040bf033f7701766') {
                            $record['failure_reason']='original_worker_or_model_identity_changed'
                            throw 'Original Qwen worker/model identity changed'
                        }
                        $record.status='restored_ready'
                        $record['worker_sha256']=$health.engine.worker_sha256
                        $record['model_files_sha256']=$health.engine.model_files_sha256
                        $record['authenticated']=$true
                        $record.Remove('failure_reason')
                        break
                    }
                    $sleepMs = [int][Math]::Max(0, [Math]::Min(2000, (90 - $clock.Elapsed.TotalSeconds) * 1000))
                    if ($sleepMs -gt 0) { Start-Sleep -Milliseconds $sleepMs }
                } while ($clock.Elapsed.TotalSeconds -lt 90)
                if ($record.status -ne 'restored_ready') {
                    $record['failure_reason']='authenticated_ready_timeout'
                    throw 'Original Qwen not authenticated ready within 90 seconds'
                }
                Write-Output 'Original Qwen service identity verified ready'
            }
            catch { $record['error_type']=$_.Exception.GetType().FullName; throw 'Qwen restore failed; inspect service evidence, never rerun inference' }
            finally {
                if ($null -ne $restoreMutex) {
                    try { if ($restoreOwned) { $restoreMutex.ReleaseMutex() } }
                    finally { $restoreMutex.Dispose() }
                }
                $record['finished_at']=[DateTimeOffset]::UtcNow.ToString('o')
                $bytes = [Text.Encoding]::UTF8.GetBytes(($record | ConvertTo-Json -Depth 4))
                $stream = [IO.File]::Open($restorePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
                try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose(); $token=$null }
            }
        }
    }
}
