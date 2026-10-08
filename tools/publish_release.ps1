param([string]$Repository='EugeneMarkeev/bugsnax_ru',[string]$Version='0.2.0',[string]$SoundVersion='0.2.0')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$assets=@((Join-Path $root "dist\Bugsnax-Installer-v$Version.zip"),(Join-Path $root "dist\Bugsnax-Sound-Pack-v$SoundVersion.zip"),(Join-Path $root "dist\SHA256SUMS-v$Version.txt"))
$notes=Join-Path $root "docs\RELEASE_NOTES_v$Version.md"
foreach ($asset in $assets) { if (-not (Test-Path -LiteralPath $asset)) { throw 'Build the split release first.' } }
& gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Complete gh auth login before publishing.' }
$metadata=Get-Content -LiteralPath (Join-Path $root 'release.json') -Raw -Encoding UTF8 | ConvertFrom-Json
& gh repo edit $Repository --description "Russian Bugsnax voices: $($metadata.fragments) clips, $($metadata.voices) voices; Windows/macOS installers" --enable-issues --enable-wiki=false
if ($LASTEXITCODE -ne 0) { throw 'Could not update repository settings.' }
$releases=& gh release list --repo $Repository --limit 100 --json tagName
if ($LASTEXITCODE -ne 0) { throw 'Could not list existing releases.' }
$present=@(($releases | ConvertFrom-Json) | Where-Object { $_.tagName -eq "v$Version" }).Count -gt 0
if (-not $present) {
    & gh release create "v$Version" --repo $Repository --verify-tag --draft --title "v$Version - Russian voices: separate installer and sound pack" --notes-file $notes
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the draft release.' }
}
& gh release upload "v$Version" @assets --repo $Repository --clobber
if ($LASTEXITCODE -ne 0) { throw 'Asset upload failed; release remains unpublished until upload succeeds.' }
& gh release edit "v$Version" --repo $Repository --draft=false --latest --title "v$Version - Russian voices: separate installer and sound pack" --notes-file $notes
if ($LASTEXITCODE -ne 0) { throw 'Could not publish the release.' }
& gh release view "v$Version" --repo $Repository --json url,assets,isDraft
if ($LASTEXITCODE -ne 0) { throw 'Could not verify the published release.' }
