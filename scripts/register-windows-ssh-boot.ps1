[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$WindowsAddress, [string]$Root = 'F:\ManiMind-Remote')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$name = 'ManiMind-PrivateSSH-Boot'
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { throw 'Boot task already exists; inspect it instead of replacing it' }
$ip = [Net.IPAddress]::Parse($WindowsAddress).GetAddressBytes()
if ($ip.Length -ne 4 -or $ip[0] -ne 100 -or $ip[1] -lt 64 -or $ip[1] -gt 127) { throw 'Expected a private Tailscale IPv4 address' }
$source = Join-Path $Root 'ensure-windows-tailnet-ssh.ps1'
if (-not (Test-Path -LiteralPath $source)) { throw 'Boot readiness script is missing' }
$protected = Join-Path $env:ProgramData 'ManiMind-System'
if (Test-Path -LiteralPath $protected) {
    if ((Get-Item -LiteralPath $protected).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Protected directory must not be a reparse point' }
} else { New-Item -ItemType Directory -Path $protected | Out-Null }
$acl = [Security.AccessControl.DirectorySecurity]::new()
$system = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$admins = [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$acl.SetOwner($system)
$acl.SetAccessRuleProtection($true, $false)
$inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
foreach ($sid in @($system, $admins)) {
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', $inherit, 'None', 'Allow'))
}
Set-Acl -LiteralPath $protected -AclObject $acl
$worker = Join-Path $protected 'ensure-windows-tailnet-ssh.ps1'
if (Test-Path -LiteralPath $worker) { throw 'Protected boot script already exists; inspect it before updating' }
Copy-Item -LiteralPath $source -Destination $worker
$fileAcl = Get-Acl -LiteralPath $worker
$fileAcl.SetOwner($system)
Set-Acl -LiteralPath $worker -AclObject $fileAcl
$current = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$arguments = '-NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File "' + $worker + '" -WindowsAddress ' + $WindowsAddress
$action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $protected
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$triggers = @(New-ScheduledTaskTrigger -AtStartup; New-ScheduledTaskTrigger -AtLogOn -User $current)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
$task = New-ScheduledTask -Action $action -Principal $principal -Trigger $triggers -Settings $settings
Register-ScheduledTask -TaskName $name -InputObject $task | Out-Null
Export-ScheduledTask -TaskName $name | Set-Content -LiteralPath (Join-Path $protected 'ssh-boot-task.xml') -Encoding UTF8
Start-ScheduledTask -TaskName $name
[pscustomobject]@{ task = $name; script = $worker; sha256 = (Get-FileHash $worker -Algorithm SHA256).Hash.ToLowerInvariant();
    scope = 'Boot readiness check installed; whole-machine reboot not tested' } | ConvertTo-Json
