[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Output, [string]$Root = 'F:\ManiMind-Remote', [string]$Plan = '', [string]$WorkerDirectory = '')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
if (Test-Path -LiteralPath $Output) { throw 'Attempt exists; inspect it instead of starting duplicate inference' }
$attemptName = Split-Path -Path $Output -Leaf
if ($attemptName -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,100}$') { throw 'Use a simple unique attempt directory name' }
if ([string]::IsNullOrWhiteSpace($Plan)) { $Plan = Join-Path $Root 'voicedesign-plan-20261025.json' }
if ([string]::IsNullOrWhiteSpace($WorkerDirectory)) { $WorkerDirectory = Join-Path $Root 'workers\voicedesign-20261025-reviewed' }
$mutex = New-Object Threading.Mutex($false, 'Global\ManiMind-VoiceDesign-Audition')
if (-not $mutex.WaitOne(0)) { $mutex.Dispose(); throw 'Another VoiceDesign worker owns the GPU slot' }
$task = 'ManiMind-QwenVoice-5080'
$restore = $false
try {
    $running = [string](Get-ScheduledTask -TaskName $task).State -eq 'Running'
    if ($running -or (Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue)) {
        throw 'Refusing to interrupt a live Qwen service. Arrange an exclusive maintenance window and pause it before running this audition.'
    }
    $token = [IO.File]::ReadAllText((Join-Path $Root 'private\speech.token')).Trim()
    $restore = $true
    $env:PYTHONUTF8 = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    $env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
    $env:HF_HOME = Join-Path $Root 'hf-cache-voicedesign'
    $worker = Join-Path $WorkerDirectory 'voicedesign_audition.py'
    $stdout = Join-Path $Root ('logs\' + $attemptName + '.stdout.log')
    $stderr = Join-Path $Root ('logs\' + $attemptName + '.stderr.log')
    if ((Test-Path -LiteralPath $stdout) -or (Test-Path -LiteralPath $stderr)) { throw 'Existing generation logs: inspect before another run' }
    $arguments = @('-u','-B',$worker,'generate','--output',$Output,'--plan',$Plan,'--setup-receipt',(Join-Path $Root 'voicedesign-setup-receipt.json'))
    $process = Start-Process -FilePath (Join-Path $Root '.venv\Scripts\python.exe') -ArgumentList $arguments -RedirectStandardOutput $stdout -RedirectStandardError $stderr -NoNewWindow -Wait -PassThru
    Get-Content -LiteralPath $stdout -Encoding UTF8
    if ($process.ExitCode -ne 0) { Get-Content -LiteralPath $stderr -Encoding UTF8; throw 'VoiceDesign generation failed; preserve all evidence' }
}
finally {
    try {
        if ($restore) {
            $record = [ordered]@{status='starting'; checked_at=[DateTimeOffset]::UtcNow.ToString('o'); inference_rerun=$false
                writer='VoiceDesign maintenance runner'; consumers=@('operator','auditor')
                lifecycle='This attempt service restoration'; invalidation='New process, deployment or service state'}
            try {
                Start-ScheduledTask -TaskName $task
                $deadline = [DateTime]::UtcNow.AddSeconds(90)
                $ready = $false
                do {
                    try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/health' -Headers @{Authorization=('Bearer ' + $token)} -TimeoutSec 3 }
                    catch { $health = $null }
                    if ($null -ne $health -and $health.status -eq 'ready') {
                        if ($health.engine.worker_sha256 -ne '555ee3544a45e2ab090d974e1f3c0f3cfb04db7eb0450b89f7f570d3e576ec93' -or $health.engine.model_files_sha256 -ne 'c1d77e1fbb1a24e2474cea448e9d2e34f3b52a207d1fa7d8040bf033f7701766') { throw 'Restored service engine identity changed' }
                        $ready = $true
                        break
                    }
                    Start-Sleep -Seconds 2
                } while ([DateTime]::UtcNow -lt $deadline)
                if (-not $ready) { throw 'Original Qwen service did not become ready within 90 seconds' }
                $record.status = 'restored_ready'
                $record['engine'] = $health.engine
                Write-Output 'Original Qwen service verified ready'
            }
            catch { $record.status = 'restore_failed'; $record['error'] = $_.Exception.Message; throw }
            finally { $record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Root ('logs\' + $attemptName + '-service-restore.json')) -Encoding UTF8 }
        }
    }
    finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
}
