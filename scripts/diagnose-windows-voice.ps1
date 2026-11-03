[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Read-Tool {
    param([string]$Name, [string[]]$Arguments)
    $tool = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $tool) {
        return [pscustomobject]@{ available = $false; exit_code = $null; output = @() }
    }
    try {
        $lines = @(& $tool.Source @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        return [pscustomobject]@{ available = $true; exit_code = $LASTEXITCODE; output = $lines }
    }
    catch {
        return [pscustomobject]@{ available = $true; exit_code = $null; error = $_.Exception.Message }
    }
}

$addresses = @()
try {
    $addresses = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' } |
        Select-Object InterfaceAlias, IPAddress)
}
catch {
    $addresses = @([pscustomobject]@{ error = $_.Exception.Message })
}

$service = Get-Service sshd -ErrorAction SilentlyContinue
$report = [ordered]@{
    schema_version = 1
    captured_at = [DateTimeOffset]::UtcNow.ToString('o')
    scope = 'Read-only inventory of this Windows host; no installation or configuration changes'
    computer_name = $env:COMPUTERNAME
    user_name = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    powershell = $PSVersionTable.PSVersion.ToString()
    ipv4_addresses = $addresses
    sshd = if ($null -eq $service) { $null } else { $service.Status.ToString() }
    gpu = Read-Tool -Name 'nvidia-smi' -Arguments @('--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits')
    python = Read-Tool -Name 'python' -Arguments @('--version')
    codex = Read-Tool -Name 'codex' -Arguments @('--version')
    tailscale_ip = Read-Tool -Name 'tailscale' -Arguments @('ip', '-4')
    note = 'Tool availability and service status do not prove network reachability, authentication, GPU inference, or speech quality'
}

$report | ConvertTo-Json -Depth 6
