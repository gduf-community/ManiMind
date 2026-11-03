[CmdletBinding()]
param([string]$Root = 'F:\ManiMind-Remote')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = [IO.Path]::GetFullPath($Root)
$name = 'ManiMind-QwenVoice-5080'
$python = Join-Path $Root '.venv\Scripts\python.exe'
$worker = Join-Path $Root 'qwen_service.py'
$model = Join-Path $Root 'models\Qwen3-TTS-12Hz-1.7B-CustomVoice'
$private = Join-Path $Root 'private'
$token = Join-Path $private 'speech.token'
foreach ($path in @($python, $worker, $token, (Join-Path $Root 'setup-receipt.json'))) {
    if (-not (Test-Path -LiteralPath $path)) { throw ('Required deployment file is missing: ' + $path) }
}
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { throw 'Task already exists; inspect it before changing deployment' }
if (Get-NetTCPConnection -State Listen -LocalPort 8766 -ErrorAction SilentlyContinue) { throw 'Port 8766 is already occupied' }
$current = [Security.Principal.WindowsIdentity]::GetCurrent()
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetOwner($current.User)
$acl.SetAccessRuleProtection($true, $false)
$inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
foreach ($sid in @($current.User, [Security.Principal.SecurityIdentifier]::new('S-1-5-18'), [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', $inherit, 'None', 'Allow'))
}
Set-Acl -LiteralPath $private -AclObject $acl
New-Item -ItemType Directory -Path (Join-Path $Root 'audio-cache'), (Join-Path $Root 'logs') -Force | Out-Null
$arguments = @('-u', '-B', ('"' + $worker + '"'), '--model-path', ('"' + $model + '"'),
    '--cache', ('"' + (Join-Path $Root 'audio-cache') + '"'), '--token-file', ('"' + $token + '"'),
    '--log-file', ('"' + (Join-Path $Root 'logs\speech.log') + '"')) -join ' '
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $Root
$principal = New-ScheduledTaskPrincipal -UserId $current.Name -LogonType S4U -RunLevel Limited
$triggers = @(New-ScheduledTaskTrigger -AtStartup; New-ScheduledTaskTrigger -AtLogOn -User $current.Name)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$task = New-ScheduledTask -Action $action -Principal $principal -Trigger $triggers -Settings $settings
Register-ScheduledTask -TaskName $name -InputObject $task | Out-Null
Export-ScheduledTask -TaskName $name | Set-Content -LiteralPath (Join-Path $Root 'speech-task.xml') -Encoding UTF8
Start-ScheduledTask -TaskName $name
$installed = Get-ScheduledTask -TaskName $name
[pscustomobject]@{ TaskName = $installed.TaskName; State = [string]$installed.State;
    User = $installed.Principal.UserId; LogonType = [string]$installed.Principal.LogonType;
    RunLevel = [string]$installed.Principal.RunLevel } | ConvertTo-Json
