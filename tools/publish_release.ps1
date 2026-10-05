param([string]$Repository='EugeneMarkeev/bugsnax_ru',[string]$Version='0.1.1')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$assets=@((Join-Path $root "dist\Bugsnax-Installer-v$Version.zip"),(Join-Path $root 'dist\Bugsnax-Sound-Pack-v0.1.0.zip'),(Join-Path $root "dist\SHA256SUMS-v$Version.txt"))
$notes=Join-Path $root "docs\RELEASE_NOTES_v$Version.md"
foreach ($asset in $assets) { if (-not (Test-Path -LiteralPath $asset)) { throw 'Build the split release first.' } }
& gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Complete gh auth login before publishing.' }
& gh repo edit $Repository --description 'Русская озвучка Bugsnax: 2469 фрагментов, 14 голосов, установка для Windows и macOS' --enable-issues --enable-wiki=false
if ($LASTEXITCODE -ne 0) { throw 'Could not update repository settings.' }
& gh release view "v$Version" --repo $Repository *> $null
if ($LASTEXITCODE -ne 0) {
    & gh release create "v$Version" --repo $Repository --verify-tag --draft --title "v$Version - Russian voices: separate installer and sound pack" --notes-file $notes
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the draft release.' }
}
& gh release upload "v$Version" @assets --repo $Repository --clobber
if ($LASTEXITCODE -ne 0) { throw 'Asset upload failed; release remains unpublished until upload succeeds.' }
& gh release edit "v$Version" --repo $Repository --draft=false --latest --title "v$Version - Russian voices: separate installer and sound pack" --notes-file $notes
if ($LASTEXITCODE -ne 0) { throw 'Could not publish the release.' }
& gh release view "v$Version" --repo $Repository --json url,assets,isDraft
if ($LASTEXITCODE -ne 0) { throw 'Could not verify the published release.' }
