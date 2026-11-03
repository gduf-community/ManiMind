[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$WindowsAddress)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$address = [Net.IPAddress]::Parse($WindowsAddress).GetAddressBytes()
if ($address.Length -ne 4 -or $address[0] -ne 100 -or $address[1] -lt 64 -or $address[1] -gt 127) { throw 'Expected a private Tailscale IPv4 address' }
$config = 'C:\ProgramData\ssh\sshd_config'
$log = Join-Path $PSScriptRoot 'ssh-boot-check.jsonl'
function Write-Result([string]$eventName) {
    [ordered]@{ time = [DateTimeOffset]::UtcNow.ToString('o'); event = $eventName;
        expected_address = $WindowsAddress; writer = 'Private SSH boot readiness task';
        scope = 'Service readiness only; not end-to-end connectivity acceptance' } |
        ConvertTo-Json -Compress | Add-Content -LiteralPath $log -Encoding UTF8
}
if ([IO.File]::ReadAllText($config) -notmatch ('(?m)^\s*ListenAddress\s+' + [regex]::Escape($WindowsAddress) + '\s*$')) {
    Write-Result 'config_changed_no_action'
    exit 1
}
$deadline = [DateTime]::UtcNow.AddMinutes(15)
while ([DateTime]::UtcNow -lt $deadline) {
    if (Get-NetIPAddress -AddressFamily IPv4 -IPAddress $WindowsAddress -ErrorAction SilentlyContinue) {
        $listener = Get-NetTCPConnection -State Listen -LocalPort 22 -LocalAddress $WindowsAddress -ErrorAction SilentlyContinue
        if (-not $listener) {
            & 'C:\Windows\System32\OpenSSH\sshd.exe' -t -f $config
            if ($LASTEXITCODE -ne 0) { Write-Result 'invalid_config_no_restart'; exit 1 }
            Restart-Service sshd
            Start-Sleep -Seconds 2
        }
        if (Get-NetTCPConnection -State Listen -LocalPort 22 -LocalAddress $WindowsAddress -ErrorAction SilentlyContinue) {
            Write-Result $(if ($listener) { 'already_listening_no_restart' } else { 'private_listener_restored' })
            exit 0
        }
    }
    Start-Sleep -Seconds 10
}
Write-Result 'private_address_or_listener_timeout'
exit 1
