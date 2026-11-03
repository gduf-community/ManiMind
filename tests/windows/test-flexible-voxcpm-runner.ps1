# Synthetic Windows PowerShell 5.1 behavior tests. No services, sockets, SDK or GPU.
# Files are create-only and retained; only this suite's cooperative children exit.
[CmdletBinding()]
param(
    [string]$WorkspaceRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [string]$Runner,
    [string]$Python
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$mutexName = 'Global\ManiMind-VoiceDesign-Audition'
$suiteMutex = $null
$suiteOwned = $false
$suiteRoot = $null

function Write-NewText([string]$Path, [string]$Text) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        $stream.Write($bytes, 0, $bytes.Length)
    } finally { $stream.Dispose() }
}

function Write-NewJson([string]$Path, $Value) {
    Write-NewText $Path ($Value | ConvertTo-Json -Depth 12)
}

function New-Directory([string]$Path) {
    if (Test-Path -LiteralPath $Path) { throw 'Synthetic directory already exists; refusing reuse' }
    $null = [IO.Directory]::CreateDirectory($Path)
}

function Assert-Check([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw ('Synthetic assertion: ' + $Message) }
}

function Assert-NoRealWorker {
    # Read-only process/listener inspection, never a health request or task command.
    $processes = @(CimCmdlets\Get-CimInstance -ClassName Win32_Process -ErrorAction Stop)
    $voice = '(?i)(flexible_voxcpm|voxcpm_(audition|narration)|voicedesign_audition|cosyvoice_audition|qwen_service|' +
        'run-windows-(flexible-voxcpm|voxcpm2|voicedesign|cosyvoice)|ManiMind-QwenVoice)'
    foreach ($item in $processes) {
        if ([int]$item.ProcessId -eq $PID) { continue }
        if ([string]$item.CommandLine -match $voice) {
            throw 'Safety refusal: a real voice worker/runner may be active; coordinate maintenance first'
        }
        if ([string]$item.Name -match '^(python(w)?|qwen.*|voxcpm.*)\.exe$' -and
            [string]::IsNullOrWhiteSpace([string]$item.CommandLine)) {
            throw 'Safety refusal: a possible worker has an uninspectable command line'
        }
    }
    $listeners = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    if (@($listeners | Where-Object { $_.Port -eq 8766 }).Count) {
        throw 'Safety refusal: port 8766 is listening; do not stop it from this test'
    }
    $probe = $null
    $owned = $false
    try {
        try { $probe = [Threading.Mutex]::OpenExisting($mutexName) }
        catch [Threading.WaitHandleCannotBeOpenedException] { return }
        try { $owned = $probe.WaitOne(0) }
        catch [Threading.AbandonedMutexException] {
            $owned = $true
            throw 'Safety refusal: existing GPU mutex is abandoned; inspect its previous owner'
        }
        if (-not $owned) { throw 'Safety refusal: GPU mutex occupied; refusing the ENTIRE suite' }
    } finally {
        if ($null -ne $probe) {
            try { if ($owned) { $probe.ReleaseMutex() } } finally { $probe.Dispose() }
        }
    }
}

function Start-TestPowerShell([string]$Script, [string[]]$Arguments) {
    $parts = @('-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'RemoteSigned', '-File', $Script) + $Arguments
    foreach ($part in $parts) {
        if ($part.Contains('"') -or $part -match '[\r\n\x00]' -or $part.EndsWith('\')) {
            throw 'Unsupported synthetic process argument'
        }
    }
    $p = New-Object Diagnostics.Process
    $p.StartInfo.FileName = Join-Path $PSHOME 'powershell.exe'
    $p.StartInfo.Arguments = (@($parts | ForEach-Object { '"' + $_ + '"' }) -join ' ')
    $p.StartInfo.UseShellExecute = $false
    $p.StartInfo.CreateNoWindow = $true
    $p.StartInfo.RedirectStandardOutput = $true
    $p.StartInfo.RedirectStandardError = $true
    $null = $p.Start()
    return $p
}

function Wait-TestProcess($Process, [string]$LogPrefix) {
    # Read concurrently to avoid pipe deadlock. No Kill/Stop-Process, including timeout.
    $out = $Process.StandardOutput.ReadToEndAsync()
    $err = $Process.StandardError.ReadToEndAsync()
    $handle = $Process.Handle
    $Process.WaitForExit()
    $code = $Process.ExitCode
    Write-NewText ($LogPrefix + '.stdout.log') $out.GetAwaiter().GetResult()
    Write-NewText ($LogPrefix + '.stderr.log') $err.GetAwaiter().GetResult()
    return $code
}

$holderSource = @'
param([string]$CaseRoot, [ValidateSet('Hold','Abandon','Probe')][string]$Mode)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$mutex = $null
$owned = $false
function Mark([string]$Name) {
    $s = [IO.File]::Open((Join-Path $CaseRoot $Name), 'CreateNew', 'Write', 'Read')
    try {
        $b = [Text.Encoding]::UTF8.GetBytes('{"synthetic":true,"no_gpu":true}')
        $s.Write($b, 0, $b.Length)
    } finally { $s.Dispose() }
}
try {
    $mutex = New-Object Threading.Mutex($false, 'Global\ManiMind-VoiceDesign-Audition')
    try { $owned = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $owned = $true; exit 24 }
    if ($Mode -eq 'Probe') {
        if ($owned) { exit 23 }
        exit 0
    }
    if (-not $owned) { exit 25 }
    Mark 'synthetic-holder-ready.json'
    $clock = [Diagnostics.Stopwatch]::StartNew()
    while (-not [IO.File]::Exists((Join-Path $CaseRoot 'synthetic-holder-release.json'))) {
        if ($clock.Elapsed.TotalSeconds -gt 120) { exit 26 }
        Start-Sleep -Milliseconds 50
    }
    if ($Mode -eq 'Abandon') {
        Mark 'synthetic-holder-abandoning.json'
        # Deliberately bypass finally in this disposable, no-GPU process only.
        [Environment]::Exit(0)
    }
} finally {
    if ($null -ne $mutex) {
        try { if ($owned) { $mutex.ReleaseMutex() } } finally { $mutex.Dispose() }
    }
}
'@

$wrapperSource = @'
param([string]$ConfigPath)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$global:cfg = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$global:syntheticEvents = New-Object 'Collections.Generic.List[string]'
$global:syntheticStarts = 0
$global:syntheticHealthCalls = 0
$global:syntheticToken = [IO.File]::ReadAllText((Join-Path $cfg.root 'private\speech.token')).Trim()
function Assert-Mock([bool]$OK) { if (-not $OK) { throw 'Synthetic mock contract violation' } }
function Get-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName)
    Assert-Mock ($TaskName -ceq 'ManiMind-QwenVoice-5080')
    $global:syntheticEvents.Add('get_task')
    [pscustomobject]@{State=$cfg.task_state}
}
function Get-NetTCPConnection {
    [CmdletBinding()]param()
    $global:syntheticEvents.Add('get_connections')
    if ($cfg.listener) { [pscustomobject]@{LocalPort=8766; State='Listen'} }
}
function Start-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName)
    Assert-Mock ($TaskName -ceq 'ManiMind-QwenVoice-5080' -and $cfg.task_state -ceq 'Ready')
    $markers = @(Get-ChildItem -LiteralPath $cfg.worker -Filter 'synthetic-worker-start-*.json')
    Assert-Mock ($markers.Count -eq 1)
    $marker = Get-Content -LiteralPath $markers[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $live = $null
    try { $live = [Diagnostics.Process]::GetProcessById([int]$marker.pid) }
    catch [ArgumentException] { }
    try { Assert-Mock ($null -eq $live -or $live.HasExited) }
    finally { if ($null -ne $live) { $live.Dispose() } }
    # Another process, not this reentrant thread, must be unable to acquire it.
    $probe = & (Join-Path $PSHOME 'powershell.exe') -NoLogo -NoProfile -NonInteractive `
        -ExecutionPolicy RemoteSigned -File $cfg.holder_script -CaseRoot $cfg.case_root -Mode Probe 2>&1
    Assert-Mock ($LASTEXITCODE -eq 0)
    $global:syntheticEvents.Add('restore_mutex_verified_by_other_process')
    $global:syntheticStarts++
    $global:syntheticEvents.Add('start_task_after_worker_exit')
}
function Invoke-RestMethod {
    [CmdletBinding()]param([string]$Uri, [int]$MaximumRedirection, [hashtable]$Headers, [int]$TimeoutSec)
    Assert-Mock ($Uri -ceq 'http://127.0.0.1:8766/health' -and $MaximumRedirection -eq 0)
    Assert-Mock ($Headers.Count -eq 1 -and $Headers.Authorization -ceq ('Bearer ' + $global:syntheticToken))
    Assert-Mock ($TimeoutSec -gt 0 -and $TimeoutSec -le 3 -and $global:syntheticStarts -eq 1)
    $global:syntheticEvents.Add('authenticated_mock_health')
    $global:syntheticHealthCalls++
    $identity = '555ee3544a45e2ab090d974e1f3c0f3cfb04db7eb0450b89f7f570d3e576ec93'
    if ($cfg.bad_identity) { $identity = 'synthetic-unknown-worker-identity' }
    [pscustomobject]@{status='ready'; engine=[pscustomobject]@{
        worker_sha256=$identity
        model_files_sha256='c1d77e1fbb1a24e2474cea448e9d2e34f3b52a207d1fa7d8040bf033f7701766'
    }}
}
$env:MANIMIND_SYNTHETIC_PYTHON = [string]$cfg.python
$threw = $false
$errorType = $null
$errorMessage = $null
try {
    & $cfg.runner -Root $cfg.root -Output $cfg.output -WorkerDirectory $cfg.worker `
        -Plan $cfg.plan -Reference $cfg.reference | Out-Null
} catch {
    $threw = $true
    $errorType = $_.Exception.GetType().FullName
    $errorMessage = $_.Exception.Message.Replace($global:syntheticToken, '[redacted]')
} finally {
    $result = [ordered]@{synthetic=$true; runner_threw=$threw; error_type=$errorType; error_message=$errorMessage
        task_starts=$global:syntheticStarts; health_calls=$global:syntheticHealthCalls; events=@($global:syntheticEvents.ToArray())}
    $bytes = [Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 5))
    $s = [IO.File]::Open((Join-Path $cfg.case_root 'synthetic-mock-result.json'), 'CreateNew', 'Write', 'Read')
    try { $s.Write($bytes, 0, $bytes.Length) } finally { $s.Dispose(); $global:syntheticToken=$null }
}
'@

$stubSource = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
public static class SyntheticFlexibleWorker {
    static void NewText(string path, string text) {
        using (var s = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read)) {
            byte[] b = Encoding.UTF8.GetBytes(text); s.Write(b, 0, b.Length);
        }
    }
    public static int Main(string[] args) {
        if (args.Length < 4 || args[0] != "-u" || args[1] != "-B" ||
            Path.GetFileName(args[2]) != "flexible_voxcpm.py" || args[3] != "generate") return 91;
        string dir = Path.GetDirectoryName(args[2]);
        int code = Int32.Parse(File.ReadAllText(Path.Combine(dir, "synthetic-exit-code.txt")));
        if (code != 0 && code != 7) return 92;
        string id = Guid.NewGuid().ToString("N");
        NewText(Path.Combine(dir, "synthetic-worker-start-" + id + ".json"),
            "{\"synthetic\":true,\"pid\":" + Process.GetCurrentProcess().Id + "}");
        string python = Environment.GetEnvironmentVariable("MANIMIND_SYNTHETIC_PYTHON");
        if (!String.IsNullOrEmpty(python)) {
            // Use the original installation in place; never copy Python/DLLs or import site/SDKs.
            var p = new Process();
            p.StartInfo.FileName = python;
            var quoted = new string[args.Length];
            for (int i = 0; i < args.Length; i++) quoted[i] = "\"" + args[i] + "\"";
            p.StartInfo.Arguments = "-I -S " + String.Join(" ", quoted);
            p.StartInfo.UseShellExecute = false;
            p.StartInfo.CreateNoWindow = true;
            p.Start(); var handle = p.Handle; p.WaitForExit(); code = p.ExitCode; p.Dispose();
        }
        NewText(Path.Combine(dir, "synthetic-worker-end-" + id + ".json"),
            "{\"synthetic\":true,\"exit_code\":" + code + "}");
        Console.WriteLine("SYNTHETIC worker only; no SDK/CUDA/model");
        Console.Error.WriteLine("SYNTHETIC controlled exit " + code);
        return code;
    }
}
'@

function Invoke-SyntheticCase($Spec) {
    Assert-NoRealWorker
    $caseRoot = Join-Path $suiteRoot $Spec.name
    New-Directory $caseRoot
    $root = Join-Path $caseRoot 'synthetic remote root'
    $worker = Join-Path $caseRoot 'synthetic worker'
    foreach ($dir in @($root, $worker, (Join-Path $root 'private'),
        (Join-Path $root '.venv-voxcpm2'), (Join-Path $root '.venv-voxcpm2\Scripts'))) {
        New-Directory $dir
    }
    [IO.File]::Copy($stubExe, (Join-Path $root '.venv-voxcpm2\Scripts\python.exe'), $false)
    Write-NewText (Join-Path $worker 'flexible_voxcpm.py') ("# SYNTHETIC; no imports, SDK or model`nraise SystemExit(" + $Spec.code + ")`n")
    Write-NewText (Join-Path $worker 'voxcpm_audition.py') '# SYNTHETIC unused helper; no SDK'
    Write-NewText (Join-Path $worker 'synthetic-exit-code.txt') ([string]$Spec.code)
    Write-NewJson (Join-Path $root 'voxcpm2-setup-receipt.json') @{synthetic=$true; no_model=$true}
    $plan = Join-Path $caseRoot 'synthetic-plan.json'
    $reference = Join-Path $caseRoot 'synthetic-reference.wav'
    Write-NewJson $plan @{synthetic=$true; segments=@()}
    Write-NewText $reference 'SYNTHETIC placeholder; not audio, not a human voice'
    # This is not a credential; never print it or read any real private directory.
    Write-NewText (Join-Path $root 'private\speech.token') ('synthetic-only-not-a-credential-' + [Guid]::NewGuid().ToString('N'))
    $output = Join-Path $caseRoot 'synthetic-attempt'
    $config = [ordered]@{synthetic=$true; case_root=$caseRoot; root=$root; worker=$worker
        runner=$runnerCopy; holder_script=$holderScript; output=$output; plan=$plan; reference=$reference
        task_state=$Spec.state; listener=$Spec.listener; bad_identity=$Spec.bad_identity; python=$Python}
    $configPath = Join-Path $caseRoot 'synthetic-config.json'
    Write-NewJson $configPath $config
    $holder = $null
    $keeper = $null
    $child = $null
    $release = Join-Path $caseRoot 'synthetic-holder-release.json'
    $holderCode = $null
    try {
        if ($Spec.lock -ne 'none') {
            # Only the independent holder owns it. The controller merely keeps a handle open.
            $holder = Start-TestPowerShell $holderScript @('-CaseRoot', $caseRoot, '-Mode', $Spec.lock)
            $clock = [Diagnostics.Stopwatch]::StartNew()
            while (-not [IO.File]::Exists((Join-Path $caseRoot 'synthetic-holder-ready.json'))) {
                if ($holder.HasExited -or $clock.Elapsed.TotalSeconds -gt 15) { throw 'Synthetic holder did not become ready' }
                Start-Sleep -Milliseconds 50
            }
            $keeper = [Threading.Mutex]::OpenExisting($mutexName)
            if ($Spec.lock -eq 'Abandon') {
                Write-NewJson $release @{synthetic=$true; release=$true}
                $holderCode = Wait-TestProcess $holder (Join-Path $caseRoot 'synthetic-holder')
                Assert-Check ($holderCode -eq 0) 'abandon holder exited cooperatively'
            }
        }
        $child = Start-TestPowerShell $wrapperScript @('-ConfigPath', $configPath)
        $childCode = Wait-TestProcess $child (Join-Path $caseRoot 'synthetic-wrapper')
        Assert-Check ($childCode -eq 0) 'mock wrapper completed and wrote result'
        $result = Get-Content -LiteralPath (Join-Path $caseRoot 'synthetic-mock-result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $markers = @(Get-ChildItem -LiteralPath $worker -Filter 'synthetic-worker-start-*.json')
        $ends = @(Get-ChildItem -LiteralPath $worker -Filter 'synthetic-worker-end-*.json')
        $count = 1
        if ($Spec.state -ne 'Ready' -or $Spec.listener) { $count = 0 }
        Assert-Check ($markers.Count -eq $count -and $ends.Count -eq $count) 'exact child launch/exit count; no retry'
        Assert-Check ($result.runner_threw -eq $Spec.throws) 'expected runner success or failure'
        Assert-Check ($result.task_starts -eq $Spec.starts) 'exact mock Qwen start count'
        Assert-Check ($result.health_calls -eq $Spec.starts) 'exact authenticated mock health count'
        $logs = Join-Path $root 'logs'
        $recordPath = Join-Path $logs 'synthetic-attempt-service-restore.json'
        $claimPath = Join-Path $logs 'synthetic-attempt-flexible-runner.json'
        Assert-Check ([IO.File]::Exists($claimPath)) 'create-only claim exists'
        $claim = Get-Content -LiteralPath $claimPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Assert-Check ($claim.automatic_retry -eq $false) 'claim disallows automatic retry'
        Assert-Check (-not (Test-Path -LiteralPath $output)) 'fake worker created no media/output'
        if ($count -eq 0) {
            Assert-Check (-not [IO.File]::Exists($recordPath)) 'preflight rejection did not restore'
            Assert-Check (-not [IO.File]::Exists((Join-Path $logs 'synthetic-attempt.stdout.log'))) 'no worker stream opened'
        } else {
            $end = Get-Content -LiteralPath $ends[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json
            Assert-Check ($end.exit_code -eq $Spec.code) 'stub/real Python returned requested exit code'
            $record = Get-Content -LiteralPath $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json
            Assert-Check ($record.worker_exit_code -eq $Spec.code -and $record.inference_rerun -eq $false) 'exit code retained without rerun'
            Assert-Check ($record.status -ceq $Spec.status) 'restore status'
            if ($Spec.starts -eq 1) {
                Assert-Check ($result.events -contains 'restore_mutex_verified_by_other_process') 'restore actually holds mutex'
                Assert-Check ($result.events[-1] -ceq 'authenticated_mock_health') 'health follows worker exit, lock and task start'
            }
            if ($Spec.reason) {
                Assert-Check ($record.failure_reason -ceq $Spec.reason) 'explicit failure_reason'
                Assert-Check (-not [string]::IsNullOrWhiteSpace($record.error_type)) 'failure exception type recorded'
            } else {
                Assert-Check (-not ($record.PSObject.Properties.Name -contains 'failure_reason')) 'healthy restoration has no failure reason'
                Assert-Check ($record.authenticated -eq $true) 'mock health authentication verified'
                Assert-Check ($record.worker_sha256 -ceq '555ee3544a45e2ab090d974e1f3c0f3cfb04db7eb0450b89f7f570d3e576ec93') 'original worker identity retained'
                Assert-Check ($record.model_files_sha256 -ceq 'c1d77e1fbb1a24e2474cea448e9d2e34f3b52a207d1fa7d8040bf033f7701766') 'original model identity retained'
            }
            foreach ($suffix in @('.stdout.log', '.stderr.log')) {
                $text = [IO.File]::ReadAllText((Join-Path $logs ('synthetic-attempt' + $suffix)))
                Assert-Check ($text -match 'SYNTHETIC') 'retained child stream labeled synthetic'
            }
        }
        # Check all retained text except the deliberately fake token input; never echo matches.
        $fakeToken = [IO.File]::ReadAllText((Join-Path $root 'private\speech.token'))
        foreach ($file in @(Get-ChildItem -LiteralPath $caseRoot -Recurse -File)) {
            if ($file.Extension -in @('.json', '.log', '.py', '.txt') -and $file.Name -ne 'speech.token') {
                Assert-Check (-not [IO.File]::ReadAllText($file.FullName).Contains($fakeToken)) 'no token in evidence'
            }
        }
        if ($Spec.lock -eq 'Hold') { Assert-Check (-not $holder.HasExited) 'independent holder remained alive through refusal' }
        return [ordered]@{synthetic=$true; name=$Spec.name; status='passed'; worker_launches=$count
            expected_worker_exit_code=$Spec.code; mock_task_starts=$result.task_starts; path=$caseRoot}
    } finally {
        try {
            if ($null -ne $child) {
                try { $child.WaitForExit() } finally { $child.Dispose() }
            }
        } finally {
            try {
                if ($null -ne $holder) {
                    try {
                        if (-not [IO.File]::Exists($release)) { Write-NewJson $release @{synthetic=$true; release=$true} }
                        if ($null -eq $holderCode) { $holderCode = Wait-TestProcess $holder (Join-Path $caseRoot 'synthetic-holder') }
                        if ($holderCode -ne 0) { throw 'Synthetic holder failed or hit its cooperative deadline' }
                    } finally {
                        try { $holder.WaitForExit() } finally { $holder.Dispose() }
                    }
                }
            } finally { if ($null -ne $keeper) { $keeper.Dispose() } }
        }
    }
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or
        $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
        $PSVersionTable.PSEdition -ne 'Desktop') {
        throw 'Requires native Windows PowerShell 5.1 Desktop; no cross-platform pass is claimed'
    }
    $WorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).ProviderPath
    if (-not $Runner) { $Runner = Join-Path $WorkspaceRoot 'scripts\run-windows-flexible-voxcpm.ps1' }
    elseif (-not [IO.Path]::IsPathRooted($Runner)) { $Runner = Join-Path $WorkspaceRoot $Runner }
    $Runner = (Resolve-Path -LiteralPath $Runner).ProviderPath
    Assert-Check ([IO.File]::Exists($Runner) -and [IO.Path]::GetExtension($Runner) -eq '.ps1') 'runner is a local ps1 file'
    if ($Python) {
        $Python = (Resolve-Path -LiteralPath $Python).ProviderPath
        Assert-Check ([IO.File]::Exists($Python) -and [IO.Path]::GetFileName($Python) -ieq 'python.exe') 'Python is an existing real python.exe'
    }
    $suiteMutex = New-Object Threading.Mutex($false, 'Global\ManiMind-FlexibleRunner-SyntheticTests')
    try { $suiteOwned = $suiteMutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $suiteOwned = $true; throw 'Prior synthetic suite abandoned; inspect before rerunning' }
    if (-not $suiteOwned) { throw 'Another synthetic suite is active; refusing the ENTIRE suite' }
    Assert-NoRealWorker
    $suiteRoot = Join-Path ([IO.Path]::GetTempPath()) ('ManiMind-synthetic-flexible-runner-' + [Guid]::NewGuid().ToString('N'))
    New-Directory $suiteRoot
    Write-NewText (Join-Path $suiteRoot 'SYNTHETIC-ONLY.txt') @'
Synthetic runner behavior fixtures only. No real task, health, model, CUDA, GPU or audio validation.
Writer: this test suite and its isolated children. Consumers: operator/test reviewer.
Lifecycle: immutable evidence for one local test run; retain until manually reviewed.
Invalidation: runner bytes, host/runtime, mocks or test inputs change. No automatic cleanup/retry.
'@
    $runnerCopy = Join-Path $suiteRoot 'synthetic-runner-under-test.ps1'
    $runnerHash = (Get-FileHash -LiteralPath $Runner -Algorithm SHA256).Hash
    [IO.File]::Copy($Runner, $runnerCopy, $false)
    Assert-Check ((Get-FileHash -LiteralPath $runnerCopy -Algorithm SHA256).Hash -ceq $runnerHash) 'byte-identical runner snapshot'
    $holderScript = Join-Path $suiteRoot 'synthetic-mutex-process.ps1'
    $wrapperScript = Join-Path $suiteRoot 'synthetic-mock-wrapper.ps1'
    Write-NewText $holderScript $holderSource
    Write-NewText $wrapperScript $wrapperSource
    Write-NewText (Join-Path $suiteRoot 'SyntheticFlexibleWorker.cs') $stubSource
    $stubExe = Join-Path $suiteRoot 'synthetic-worker.exe'
    Assert-Check (-not [IO.File]::Exists($stubExe)) 'compiler output is new'
    Add-Type -TypeDefinition $stubSource -Language CSharp -OutputAssembly $stubExe -OutputType ConsoleApplication
    $mode = 'compiled-stub-no-python'
    if ($Python) { $mode = 'real-python-original-installation-isolated-no-site' }
    Write-NewJson (Join-Path $suiteRoot 'synthetic-suite-input.json') ([ordered]@{
        synthetic=$true; runner=$Runner; runner_sha256=$runnerHash; mode=$mode
        powershell_version=$PSVersionTable.PSVersion.ToString(); host_pid=$PID
        real_worker_preflight='processes/listeners/mutex checked; operator maintenance still required'
    })
    $specs = @(
        @{name='synthetic-disabled'; state='Disabled'; code=0; lock='none'; listener=$false; bad_identity=$false; throws=$true; starts=0; status=''; reason=''},
        @{name='synthetic-ready-zero'; state='Ready'; code=0; lock='none'; listener=$false; bad_identity=$false; throws=$false; starts=1; status='restored_ready'; reason=''},
        @{name='synthetic-ready-seven'; state='Ready'; code=7; lock='none'; listener=$false; bad_identity=$false; throws=$true; starts=1; status='restored_ready'; reason=''},
        @{name='synthetic-busy-other-process'; state='Ready'; code=7; lock='Hold'; listener=$false; bad_identity=$false; throws=$true; starts=0; status='restore_failed'; reason='gpu_slot_not_clear_for_restore'},
        @{name='synthetic-abandoned-other-process'; state='Ready'; code=7; lock='Abandon'; listener=$false; bad_identity=$false; throws=$true; starts=0; status='restore_failed'; reason='gpu_slot_not_clear_for_restore'},
        @{name='synthetic-unknown-health-identity'; state='Ready'; code=0; lock='none'; listener=$false; bad_identity=$true; throws=$true; starts=1; status='restore_failed'; reason='original_worker_or_model_identity_changed'},
        @{name='synthetic-running-task'; state='Running'; code=0; lock='none'; listener=$false; bad_identity=$false; throws=$true; starts=0; status=''; reason=''},
        @{name='synthetic-listening-port'; state='Ready'; code=0; lock='none'; listener=$true; bad_identity=$false; throws=$true; starts=0; status=''; reason=''}
    )
    $results = New-Object 'Collections.Generic.List[object]'
    foreach ($spec in $specs) {
        # A live-state refusal aborts the remaining suite, not just one case.
        Assert-NoRealWorker
        try {
            $result = Invoke-SyntheticCase $spec
            $results.Add($result)
            Write-Output ('PASS ' + $spec.name + ' (synthetic only)')
        } catch {
            if ($_.Exception.Message -like 'Safety refusal:*') { throw }
            $results.Add([ordered]@{synthetic=$true; name=$spec.name; status='failed'; error_type=$_.Exception.GetType().FullName
                detail=$_.Exception.Message; path=(Join-Path $suiteRoot $spec.name)})
            Write-Output ('FAIL ' + $spec.name + ' (inspect retained synthetic evidence)')
        }
    }
    Assert-NoRealWorker
    Assert-Check ((Get-FileHash -LiteralPath $Runner -Algorithm SHA256).Hash -ceq $runnerHash) 'source runner unchanged during tests'
    $failed = @($results.ToArray() | Where-Object { $_.status -eq 'failed' }).Count
    Write-NewJson (Join-Path $suiteRoot 'synthetic-summary.json') ([ordered]@{
        synthetic=$true; production_validation=$false; mode=$mode; failed=$failed; cases=$results.ToArray()
        skipped=@(@{name='unknown-uninspectable-gpu-mutex'; reason='Not changing real Global mutex ACLs or production mutex implementation'})
    })
    Write-Output ('Retained SYNTHETIC fixtures/logs: ' + $suiteRoot)
    Write-Output 'SKIP unknown/uninspectable GPU mutex: no real mutex ACL changes; unknown health identity tested separately'
    if ($failed) { exit 1 }
} catch {
    if ($suiteRoot) {
        $refusal = Join-Path $suiteRoot 'synthetic-suite-refusal.json'
        if (-not [IO.File]::Exists($refusal)) {
            Write-NewJson $refusal @{synthetic=$true; error_type=$_.Exception.GetType().FullName; detail=$_.Exception.Message}
        }
        Write-Output ('Retained SYNTHETIC fixtures/logs: ' + $suiteRoot)
    }
    Write-Error ('Synthetic suite refused/incomplete: ' + $_.Exception.Message) -ErrorAction Continue
    exit 2
} finally {
    if ($null -ne $suiteMutex) {
        try { if ($suiteOwned) { $suiteMutex.ReleaseMutex() } } finally { $suiteMutex.Dispose() }
    }
}
