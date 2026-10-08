param(
    [ValidateSet('Install','Uninstall','Check')][string]$Action='Install',
    [string]$GamePath,
    [string]$PackagePath=(Split-Path $PSScriptRoot -Parent),
    [switch]$NoDialog
)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new()
$packageVersion='unknown'
$releaseMetadata=Join-Path $PackagePath 'release.json'
if (Test-Path -LiteralPath $releaseMetadata) {
    $metadata=Get-Content -LiteralPath $releaseMetadata -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($metadata.version) { $packageVersion=[string]$metadata.version }
}
function Hash($path) {
    $stream=[System.IO.File]::OpenRead($path)
    $sha=[System.Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}
function Find-Audio($root) {
    foreach ($relative in @('Content\Audio\Build\Desktop','Bugsnax.app\Contents\Resources\Content\Audio\Build\Desktop','Contents\Resources\Content\Audio\Build\Desktop','')) {
        $candidate=if ($relative) { Join-Path $root $relative } else { $root }
        if (Test-Path -LiteralPath (Join-Path $candidate 'GameAudio_Filbo.bank')) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
}
function Locate-Game {
    if ($GamePath) {
        $found=Find-Audio $GamePath
        if (-not $found) { throw 'Sound banks not found in the selected game folder.' }
        return $found
    }
    $steamRoots=@()
    foreach ($key in @('HKCU:\Software\Valve\Steam','HKLM:\SOFTWARE\WOW6432Node\Valve\Steam')) {
        if (Test-Path $key) {
            $item=Get-ItemProperty $key
            foreach ($property in @('SteamPath','InstallPath')) {
                if ($item.$property) { $steamRoots += $item.$property }
            }
        }
    }
    if (${env:ProgramFiles(x86)}) { $steamRoots += Join-Path ${env:ProgramFiles(x86)} 'Steam' }
    $libraries=@($steamRoots)
    foreach ($root in $steamRoots) {
        $vdf=Join-Path $root 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            $text=Get-Content -LiteralPath $vdf -Raw
            foreach ($match in [regex]::Matches($text,'"path"\s+"([^"]+)"')) { $libraries += $match.Groups[1].Value.Replace('\\','\') }
        }
    }
    foreach ($library in ($libraries | Select-Object -Unique)) {
        $found=Find-Audio (Join-Path $library 'steamapps\common\Bugsnax')
        if ($found) { return $found }
    }
    if ($NoDialog) { throw 'Bugsnax was not found. Pass -GamePath with the Steam game folder.' }
    Add-Type -AssemblyName System.Windows.Forms
    $dialog=New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description='Select Bugsnax folder (Steam: Manage > Browse local files)'
    if ($dialog.ShowDialog() -ne 'OK') { throw 'Installation cancelled.' }
    $found=Find-Audio $dialog.SelectedPath
    if (-not $found) { throw 'Sound banks not found in the selected folder.' }
    return $found
}
if (Get-Process Bugsnax -ErrorAction SilentlyContinue) { throw 'Close Bugsnax and try again.' }
$manifest=Join-Path $PackagePath 'manifest.tsv'
if (-not (Test-Path -LiteralPath $manifest)) { throw 'manifest.tsv is missing. Download and extract the complete release ZIP.' }
$banks=@(Import-Csv -LiteralPath $manifest -Delimiter "`t")
if (-not $banks.Count) { throw 'Empty manifest.' }
foreach ($bank in $banks) {
    if ($bank.name -notmatch '^[A-Za-z0-9_]+\.bank$' -or $bank.original_sha256 -notmatch '^[a-f0-9]{64}$' -or $bank.patched_sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Invalid bank manifest.' }
}
$audio=Locate-Game
Write-Host "Game sound folder: $audio"
$state=Join-Path $audio '.bugsnax-russian-voice'
$backup=Join-Path $state 'backup'
$previous=@{}
$previousPath=Join-Path $PackagePath 'previous-manifest.tsv'
if (Test-Path -LiteralPath $previousPath) {
    foreach ($old in @(Import-Csv -LiteralPath $previousPath -Delimiter "`t")) {
        if ($old.name -notmatch '^[A-Za-z0-9_]+\.bank$' -or $old.patched_sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Invalid previous manifest.' }
        if ($previous.ContainsKey($old.name)) { $previous[$old.name] += @($old) }
        else { $previous[$old.name]=@($old) }
    }
}
function Assert-Compatible($bank,$current) {
    if ($current -in @($bank.original_sha256,$bank.patched_sha256)) { return }
    $matched=@($previous[$bank.name] | Where-Object { $_ -and $_.original_sha256 -eq $bank.original_sha256 -and $_.patched_sha256 -eq $current })
    if ($matched.Count -gt 0) {
        $saved=Join-Path $backup $bank.name
        if (-not (Test-Path -LiteralPath $saved) -or (Hash $saved) -ne $bank.original_sha256) { throw 'Previous voice pack found but original backup is missing or damaged. Restore using Steam file verification.' }
        return
    }
    throw "Unsupported game version or another audio mod: $($bank.name). No game files changed."
}
if ($Action -eq 'Install') {
    foreach ($bank in $banks) {
        $current=Hash (Join-Path $audio $bank.name)
        Assert-Compatible $bank $current
    }
    & (Join-Path $PSScriptRoot 'download_sound.ps1') -PackagePath $PackagePath
}
$operations=@()
foreach ($bank in $banks) {
    $target=Join-Path $audio $bank.name
    $current=Hash $target
    Assert-Compatible $bank $current
    if ($Action -eq 'Check') { continue }
    if ($Action -eq 'Install') {
        $source=Join-Path $PackagePath ('payload\'+$bank.name)
        if (-not (Test-Path -LiteralPath $source)) { throw 'Audio is missing. Download the release ZIP, not GitHub Source code.' }
        if ((Hash $source) -ne $bank.patched_sha256) { throw "Damaged release file: $($bank.name)" }
        $desired=$bank.patched_sha256
    } else {
        $source=Join-Path $backup $bank.name
        $desired=$bank.original_sha256
        if ($current -ne $desired -and (-not (Test-Path -LiteralPath $source) -or (Hash $source) -ne $desired)) { throw 'Original backup is missing or damaged. Restore the game using Steam file verification.' }
    }
    if ((Test-Path -LiteralPath (Join-Path $backup $bank.name)) -and (Hash (Join-Path $backup $bank.name)) -ne $bank.original_sha256) { throw "Damaged original backup: $($bank.name)" }
    if ($current -ne $desired) { $operations += [PSCustomObject]@{ Bank=$bank; Target=$target; Source=$source; Desired=$desired; Current=$current } }
}
if ($Action -eq 'Check') { Write-Host 'Compatible sound banks. No changes made.'; exit 0 }
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$lock=Join-Path $state 'lock'
New-Item -ItemType Directory -Path $lock -ErrorAction Stop | Out-Null
$stage=Join-Path $state ('transaction-'+[guid]::NewGuid().ToString('N'))
$changed=@()
try {
    New-Item -ItemType Directory -Path $stage | Out-Null
    foreach ($op in $operations) {
        if ((Hash $op.Target) -ne $op.Current) { throw 'Game files changed while preparing installation.' }
        if ($Action -eq 'Install') {
            $saved=Join-Path $backup $op.Bank.name
            if (-not (Test-Path -LiteralPath $saved)) {
                Copy-Item -LiteralPath $op.Target -Destination $saved
                if ((Hash $saved) -ne $op.Bank.original_sha256) { throw 'Original backup checksum mismatch.' }
            }
        }
        Copy-Item -LiteralPath $op.Target -Destination (Join-Path $stage ($op.Bank.name+'.old'))
        $next=Join-Path $stage ($op.Bank.name+'.new')
        Copy-Item -LiteralPath $op.Source -Destination $next
        if ((Hash $next) -ne $op.Desired) { throw 'Staged file checksum mismatch.' }
    }
    foreach ($op in $operations) {
        if ((Hash $op.Target) -ne $op.Current) { throw 'Game files changed during installation.' }
        $changed += $op
        Move-Item -LiteralPath (Join-Path $stage ($op.Bank.name+'.new')) -Destination $op.Target -Force
        if ((Hash $op.Target) -ne $op.Desired) { throw 'Installed file checksum mismatch.' }
    }
    foreach ($bank in $banks) {
        $expected=if ($Action -eq 'Install') { $bank.patched_sha256 } else { $bank.original_sha256 }
        if ((Hash (Join-Path $audio $bank.name)) -ne $expected) { throw 'Final verification failed.' }
    }
    @{action=$Action;version=$packageVersion;verified=$true;time=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $state 'status.json') -Encoding UTF8
    foreach ($file in @(Get-ChildItem -LiteralPath $stage -File)) { Remove-Item -LiteralPath $file.FullName }
    Remove-Item -LiteralPath $stage
    if ($Action -eq 'Install') { Write-Host 'Russian voices installed. Start Bugsnax through Steam. Select Russian in Steam game properties for subtitles.' }
    else { Write-Host 'Original voices restored.' }
} catch {
    foreach ($op in $changed) {
        if ((Hash $op.Target) -ne $op.Current) { Copy-Item -LiteralPath (Join-Path $stage ($op.Bank.name+'.old')) -Destination $op.Target -Force }
        if ((Hash $op.Target) -ne $op.Current) { throw "Rollback failed. Recovery files: $stage" }
    }
    throw
} finally { Remove-Item -LiteralPath $lock -ErrorAction SilentlyContinue }
