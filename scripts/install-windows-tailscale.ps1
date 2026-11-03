[CmdletBinding()]
param([string]$Root = 'F:\ManiMind-Remote', [string]$Version = '1.104.2')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Use an explicit stable version' }
if (Test-Path 'C:\Program Files\Tailscale\tailscale.exe') { throw 'Tailscale already exists; inspect it instead of replacing it' }
$directory = Join-Path $Root 'installers'
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$file = 'tailscale-setup-' + $Version + '-amd64.msi'
$url = 'https://pkgs.tailscale.com/stable/' + $file
$path = Join-Path $directory $file
Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $path
$published = (Invoke-WebRequest -UseBasicParsing -Uri ($url + '.sha256')).Content.Trim().Split(' ')[0]
$actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $published) { throw 'Official package SHA256 mismatch' }
$signature = Get-AuthenticodeSignature -LiteralPath $path
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Tailscale') {
    throw 'Expected a valid Tailscale publisher signature'
}
$log = Join-Path $directory ('tailscale-install-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '.log')
$process = Start-Process msiexec.exe -ArgumentList @('/i', ('"' + $path + '"'), '/qn', '/norestart', 'TS_NOLAUNCH=1', '/L*v', ('"' + $log + '"')) -PassThru -Wait
if ($process.ExitCode -notin @(0, 3010)) { throw ('Installer failed: ' + $process.ExitCode + '; see ' + $log) }
[pscustomobject]@{ version = $Version; package_sha256 = $actual; publisher = $signature.SignerCertificate.Subject;
    exit_code = $process.ExitCode; reboot_required = ($process.ExitCode -eq 3010); log = $log;
    scope = 'Installation only; not logged in and no connectivity acceptance' } | ConvertTo-Json
