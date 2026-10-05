param([Parameter(Mandatory=$true)][string]$PackagePath)
$ErrorActionPreference='Stop'
function Digest($path) {
    $stream=[IO.File]::OpenRead($path); $sha=[Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}
$banks=@(Import-Csv -LiteralPath (Join-Path $PackagePath 'manifest.tsv') -Delimiter "`t")
$missing=@($banks | Where-Object { -not (Test-Path -LiteralPath (Join-Path $PackagePath ('payload\'+$_.name))) })
if (-not $missing.Count) { return }
$config=Join-Path $PackagePath 'sound-pack.tsv'
if (-not (Test-Path -LiteralPath $config)) { throw 'Sound pack configuration missing. Download the installer release ZIP.' }
$rows=@(Import-Csv -LiteralPath $config -Delimiter "`t")
if ($rows.Count -ne 1) { throw 'Invalid sound pack configuration.' }
$pack=$rows[0]
if ($pack.filename -notmatch '^Bugsnax-Sound-Pack-v[0-9.]+\.zip$' -or $pack.sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Invalid sound pack configuration.' }
$lock=Join-Path $PackagePath '.sound-pack-lock'
New-Item -ItemType Directory -Path $lock -ErrorAction Stop | Out-Null
$stage=Join-Path $PackagePath ('.sound-unpack-'+[guid]::NewGuid().ToString('N'))
try {
    $archive=$null
    foreach ($folder in @($PackagePath,(Split-Path $PackagePath -Parent))) {
        $candidate=Join-Path $folder $pack.filename
        if (Test-Path -LiteralPath $candidate) { $archive=$candidate; break }
    }
    if (-not $archive) {
        if ($pack.url -notmatch '^https://github\.com/EugeneMarkeev/bugsnax_ru/releases/download/v[0-9.]+/Bugsnax-Sound-Pack-v[0-9.]+\.zip$') { throw 'Untrusted sound pack download URL.' }
        $archive=Join-Path $PackagePath $pack.filename
        $partial=$archive+'.partial'
        Write-Host 'Downloading Russian voices (about 1.3 GB). An interrupted download can be resumed.'
        & curl.exe --fail --location --retry 3 --continue-at - --output $partial $pack.url
        if ($LASTEXITCODE -ne 0) { throw 'Download failed. Run Install again to resume, or download the sound pack ZIP manually beside the installer.' }
        if ((Digest $partial) -ne $pack.sha256) { Remove-Item -LiteralPath $partial; throw 'Downloaded sound pack checksum mismatch. Run Install again.' }
        Move-Item -LiteralPath $partial -Destination $archive
    }
    if ((Digest $archive) -ne $pack.sha256) { throw 'Sound pack ZIP is damaged or has the wrong version. Download it again.' }
    Write-Host 'Unpacking Russian voices...'
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach ($entry in $zip.Entries) {
            if ($entry.FullName -ne 'payload/' -and $entry.FullName -notmatch '^payload/[A-Za-z0-9_]+\.bank$') { throw 'Unexpected file path in sound pack.' }
        }
    } finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($archive,$stage)
    foreach ($bank in $banks) {
        $source=Join-Path $stage ('payload\'+$bank.name)
        if ((Digest $source) -ne $bank.patched_sha256) { throw 'Unpacked sound bank checksum mismatch.' }
    }
    $payload=Join-Path $PackagePath 'payload'
    New-Item -ItemType Directory -Path $payload -Force | Out-Null
    foreach ($bank in $banks) { Move-Item -LiteralPath (Join-Path $stage ('payload\'+$bank.name)) -Destination (Join-Path $payload $bank.name) -Force }
    Remove-Item -LiteralPath (Join-Path $stage 'payload')
    Remove-Item -LiteralPath $stage
} finally { Remove-Item -LiteralPath $lock -ErrorAction SilentlyContinue }
