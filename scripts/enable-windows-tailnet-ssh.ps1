[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$MacAddress,
    [Parameter(Mandatory=$true)][string]$WindowsAddress,
    [string]$Root = 'F:\ManiMind-Remote'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
foreach ($value in @($MacAddress, $WindowsAddress)) {
    $ip = [Net.IPAddress]::Parse($value)
    $bytes = $ip.GetAddressBytes()
    if ($bytes.Length -ne 4 -or $bytes[0] -ne 100 -or $bytes[1] -lt 64 -or $bytes[1] -gt 127) {
        throw 'Only explicit Tailscale IPv4 addresses are allowed'
    }
}
if ($MacAddress -eq $WindowsAddress) { throw 'Peer and local address must differ' }
$status = & 'C:\Program Files\Tailscale\tailscale.exe' status --json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $status.BackendState -ne 'Running' -or $WindowsAddress -notin $status.TailscaleIPs) {
    throw 'The local Tailscale identity is not connected at this address'
}
$peers = @($status.Peer.PSObject.Properties | Where-Object { $MacAddress -in $_.Value.TailscaleIPs -and $_.Value.Online })
if ($peers.Count -ne 1) { throw 'Expected exactly one online Mac peer at the authorized address' }
$allow = 'ManiMind-Tailnet-SSH-From-Mac'
$block = 'ManiMind-Tailnet-SSH-Block-Other-IPv4'
foreach ($name in @($allow, $block)) {
    if (Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue) { throw 'Tailnet rules already exist; inspect instead of replacing them' }
}
$config = 'C:\ProgramData\ssh\sshd_config'
$authorized = 'C:\ProgramData\ssh\administrators_authorized_keys'
$keyId = 'AAAAC3NzaC1lZDI1NTE5AAAAIIbjyoUwULbc5fvW5SnwZJUlLJZhObiqtE6Lg2bpjPHi'
$lines = [IO.File]::ReadAllLines($authorized)
$matching = @(0..($lines.Length - 1) | Where-Object { $lines[$_] -match [regex]::Escape($keyId) })
if ($matching.Count -ne 1 -or $lines[$matching[0]] -notmatch 'from="192\.168\.86\.17"') {
    throw 'Expected the verified dedicated Mac public key with its original LAN restriction'
}
$contents = [IO.File]::ReadAllText($config)
if ($contents -match ('(?m)^\s*ListenAddress\s+' + [regex]::Escape($WindowsAddress) + '\s*$')) {
    throw 'Tailnet listener already exists; inspect before changing it'
}
$backup = Join-Path $Root ('tailnet-ssh-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item -LiteralPath $config -Destination (Join-Path $backup 'sshd_config.before')
Copy-Item -LiteralPath $authorized -Destination (Join-Path $backup 'administrators_authorized_keys.before')
$keyAcl = Get-Acl -LiteralPath $authorized
$created = @()
try {
    New-NetFirewallRule -Name $allow -DisplayName $allow -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22 -LocalAddress $WindowsAddress -RemoteAddress $MacAddress -Profile Any | Out-Null
    $created += $allow
    $ipBytes = [Net.IPAddress]::Parse($MacAddress).GetAddressBytes()
    if ($ipBytes[3] -eq 0 -or $ipBytes[3] -eq 255) { throw 'Boundary peer address requires reviewed firewall ranges' }
    $before = $ipBytes.Clone(); $before[3]--
    $after = $ipBytes.Clone(); $after[3]++
    $other = @(('0.0.0.0-' + ([Net.IPAddress]::new([byte[]]$before)).ToString()), (([Net.IPAddress]::new([byte[]]$after)).ToString() + '-255.255.255.255'))
    New-NetFirewallRule -Name $block -DisplayName $block -Direction Inbound -Action Block -Protocol TCP -LocalPort 22 -LocalAddress $WindowsAddress -RemoteAddress $other -Profile Any | Out-Null
    $created += $block
    $lines[$matching[0]] = $lines[$matching[0]].Replace('from="192.168.86.17"', ('from="192.168.86.17,' + $MacAddress + '"'))
    [IO.File]::WriteAllLines($authorized, $lines, [Text.UTF8Encoding]::new($false))
    Set-Acl -LiteralPath $authorized -AclObject $keyAcl
    [IO.File]::WriteAllText($config, ('ListenAddress ' + $WindowsAddress + "`r`n" + $contents), [Text.UTF8Encoding]::new($false))
    & 'C:\Windows\System32\OpenSSH\sshd.exe' -t -f $config
    if ($LASTEXITCODE -ne 0) { throw 'sshd syntax check failed' }
    Restart-Service sshd
    Start-Sleep -Seconds 2
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort 22 | Select-Object -ExpandProperty LocalAddress)
    if ($WindowsAddress -notin $listeners -or '192.168.86.11' -notin $listeners -or '0.0.0.0' -in $listeners -or '::' -in $listeners) {
        throw 'Expected private-only SSH listeners with the LAN fallback retained'
    }
    [pscustomobject]@{ local_address = $WindowsAddress; authorized_peer = $MacAddress; listeners = $listeners;
        backup = $backup; sshd = [string](Get-Service sshd).Status; scope = 'Configured; Mac login is a separate acceptance check' } | ConvertTo-Json
}
catch {
    Copy-Item -LiteralPath (Join-Path $backup 'sshd_config.before') -Destination $config -Force
    Copy-Item -LiteralPath (Join-Path $backup 'administrators_authorized_keys.before') -Destination $authorized -Force
    Set-Acl -LiteralPath $authorized -AclObject $keyAcl
    foreach ($name in $created) { Remove-NetFirewallRule -Name $name -ErrorAction SilentlyContinue }
    Restart-Service sshd
    throw
}
