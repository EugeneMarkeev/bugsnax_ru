param([string]$Repository='EugeneMarkeev/bugsnax_ru')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$asset=Join-Path $root 'dist\Bugsnax-Russian-Voice-v0.1.0.zip'
$checksum=$asset+'.sha256'
$notes=Join-Path $root 'docs\RELEASE_NOTES_v0.1.0.md'
if (-not (Test-Path -LiteralPath $asset) -or -not (Test-Path -LiteralPath $checksum)) { throw 'Build the release first.' }
& gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Complete gh auth login before publishing.' }
& gh repo edit $Repository --description 'Русская озвучка Bugsnax: 2469 фрагментов, 14 голосов, установка для Windows и macOS' --enable-issues --enable-wiki=false
if ($LASTEXITCODE -ne 0) { throw 'Could not update repository settings.' }
& gh release view v0.1.0 --repo $Repository *> $null
if ($LASTEXITCODE -ne 0) {
    & gh release create v0.1.0 --repo $Repository --verify-tag --draft --title 'v0.1.0 — Русская озвучка: Windows и macOS' --notes-file $notes
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the draft release.' }
}
& gh release upload v0.1.0 $asset $checksum --repo $Repository --clobber
if ($LASTEXITCODE -ne 0) { throw 'Asset upload failed; release remains unpublished until upload succeeds.' }
& gh release edit v0.1.0 --repo $Repository --draft=false --latest --title 'v0.1.0 — Русская озвучка: Windows и macOS' --notes-file $notes
if ($LASTEXITCODE -ne 0) { throw 'Could not publish the release.' }
& gh release view v0.1.0 --repo $Repository --json url,assets,isDraft
if ($LASTEXITCODE -ne 0) { throw 'Could not verify the published release.' }
