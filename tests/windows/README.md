# Synthetic Windows runner behavior tests

Run later on the Windows host in **Windows PowerShell 5.1 Desktop**, only after
the operator confirms there are no real voice workers and the maintenance window
is exclusive. This change does not perform SSH or run anything remotely.

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File 'F:\ManiMind-staging\tests\windows\test-flexible-voxcpm-runner.ps1' -WorkspaceRoot 'F:\ManiMind-staging'
```

`-Runner` optionally selects another local runner path (relative to
`-WorkspaceRoot`, or absolute). The suite copies its exact bytes into a unique
`%TEMP%\ManiMind-synthetic-flexible-runner-<guid>` directory and runs that copy.
No repository files are written. `-Python 'C:\path\to\python.exe'` optionally
uses a real interpreter **in its original installation** through a compiled
launcher; `-I -S -u -B` runs a fake `flexible_voxcpm.py` that only exits 0 or 7.
Without `-Python`, the compiled C# `python.exe` stub exits 0/7 without Python.
Both modes require the built-in `Add-Type` C# compiler, not SDK/CUDA/model files.
The real-Python mode therefore checks launcher-mediated exit propagation, not
the deployed venv or Python DLL relocation.

For the controller handoff, deploy to a new local staging tree without Zone
markers and use only `-WorkspaceRoot`, as above (no `-Runner` argument). Run
after Qwen is idle and explicitly stopped, before real generation. A parent
command line containing a production runner name can conservatively trigger
the real-worker safety regex. All child processes also use `RemoteSigned`;
the suite does not change machine/user execution policy or remove Zone markers.

The runner executes in a fresh no-profile child with fail-closed mocks for
`Get-ScheduledTask`, `Get-NetTCPConnection`, `Start-ScheduledTask`, and
`Invoke-RestMethod`. No actual task command, service control, HTTP request,
network connection or model invocation is made. Preflight only reads local CIM
process metadata, the OS TCP listener table and the named mutex. Unknown or
inaccessible safety state fails closed. These checks do not replace operator
coordination against a real worker starting after the check. This is a test
harness for the reviewed runner, **not a sandbox for arbitrary `-Runner` code**.

Coverage: Disabled/Running/listening rejection before child launch; Ready/0
restoration with authenticated mock worker/model identity; Ready/7 restoration
without retry; busy and abandoned mutex refusal after a failing child, with
`failure_reason`; unknown health identity rejection. Start mocks also check the
child PID has exited and a separate process cannot acquire the restoration lock.
Busy/abandoned use an independent no-GPU PowerShell holder of
`Global\ManiMind-VoiceDesign-Audition`, never same-thread reentrant ownership.
An open, **unowned** controller handle preserves the abandoned object until the
runner inspects it. Unknown/uninspectable mutex handling is explicitly skipped:
the suite does not alter real mutex ACLs or replace production .NET behavior.

Before any fixtures/holders run, and between cases, an occupied/abandoned mutex,
active voice worker, uninspectable possible worker or listening 8766 refuses the
whole suite. Holders release on a create-only signal and have a 120-second
cooperative deadline; abandonment exits only that disposable process. No process
killing, bulk stopping or automatic retry/cleanup exists. Concurrent suites are
also rejected. Existing files are never overwritten; all inputs, claims,
stdout/stderr, mock results and receipts remain under the synthetic temp root.
The fake token stays only in its fake input and is never printed. Runner-native
receipt schemas remain unchanged; their enclosing directory and suite metadata
explicitly identify them as synthetic, not real service/GPU validation.

Exit codes: `0` all implemented cases passed (see explicit skip); `1` behavior
assertion failed; `2` safety refusal or incomplete setup. Hand off the command to
the main controller for later SSH execution; inspect `synthetic-summary.json`
and per-case evidence on Windows before claiming runtime success. No native
Windows execution is implied by source/static checks on macOS.

2026-10-27 host verification: all eight implemented cases passed on Windows
PowerShell Desktop; the unsafe mutex-ACL injection remains explicitly skipped.
The first run exposed dynamic script-scope mock state and was retained as a
failed synthetic run. Mock state now lives only in the fresh child process's
global scope, so the separately invoked runner sees the same counters/token;
no parent process, real service or host-global setting is changed. Both runs
and the actual outer service restoration are archived under
runtime/sessions/projectile-paced-20261027/. These fixtures are not GPU/model
inference or listening evidence.
