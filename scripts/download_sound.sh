#!/bin/bash
set -euo pipefail
ROOT="$1"
fail() { printf '%s\n' "$*" >&2; exit 1; }
hash() { shasum -a 256 "$1" | awk '{print $1}'; }
TAB=$'\t'
missing=0
while IFS="$TAB" read -r name original patched bytes; do
    [ "$name" = name ] && continue
    [ -f "$ROOT/payload/$name" ] || missing=1
done < "$ROOT/manifest.tsv"
[ "$missing" != 0 ] || exit 0
[ -f "$ROOT/sound-pack.tsv" ] || fail 'Sound pack configuration missing. Download the installer release ZIP.'
count=0
while IFS="$TAB" read -r filename url sha256; do
    [ "$filename" = filename ] && continue
    count=$((count+1)); FILE="$filename"; URL="$url"; SHA="${sha256%$'\r'}"
done < "$ROOT/sound-pack.tsv"
[ "$count" = 1 ] || fail 'Invalid sound pack configuration.'
[[ "$FILE" =~ ^Bugsnax-Sound-Pack-v[0-9.]+\.zip$ && "$SHA" =~ ^[a-f0-9]{64}$ ]] || fail 'Invalid sound pack configuration.'
mkdir "$ROOT/.sound-pack-lock" || fail 'Another sound pack download is running, or a stale lock remains.'
cleanup() { rmdir "$ROOT/.sound-pack-lock" || true; }
trap cleanup EXIT
archive=''
for folder in "$ROOT" "$(dirname "$ROOT")"; do
    if [ -f "$folder/$FILE" ]; then archive="$folder/$FILE"; break; fi
done
if [ -z "$archive" ]; then
    [[ "$URL" =~ ^https://github\.com/EugeneMarkeev/bugsnax_ru/releases/download/v[0-9.]+/Bugsnax-Sound-Pack-v[0-9.]+\.zip$ ]] || fail 'Untrusted sound pack download URL.'
    archive="$ROOT/$FILE"
    echo 'Downloading Russian voices (about 1.3 GB). An interrupted download can be resumed.'
    curl --fail --location --retry 3 --continue-at - --output "$archive.partial" "$URL" || fail 'Download failed. Run Install again to resume, or download the sound pack ZIP manually beside the installer.'
    if [ "$(hash "$archive.partial")" != "$SHA" ]; then rm "$archive.partial"; fail 'Downloaded sound pack checksum mismatch. Run Install again.'; fi
    mv "$archive.partial" "$archive"
fi
[ "$(hash "$archive")" = "$SHA" ] || fail 'Sound pack ZIP is damaged or has the wrong version. Download it again.'
while IFS= read -r entry; do
    [[ "$entry" = payload/ || "$entry" =~ ^payload/[A-Za-z0-9_]+\.bank$ ]] || fail 'Unexpected file path in sound pack.'
done < <(unzip -Z -1 "$archive")
echo 'Unpacking Russian voices...'
stage="$(mktemp -d "$ROOT/.sound-unpack.XXXXXX")"
unzip -q "$archive" -d "$stage"
while IFS="$TAB" read -r name original patched bytes; do
    [ "$name" = name ] && continue
    [ "$(hash "$stage/payload/$name")" = "$patched" ] || fail 'Unpacked sound bank checksum mismatch.'
done < "$ROOT/manifest.tsv"
mkdir -p "$ROOT/payload"
while IFS="$TAB" read -r name original patched bytes; do
    [ "$name" = name ] && continue
    mv -f "$stage/payload/$name" "$ROOT/payload/$name"
done < "$ROOT/manifest.tsv"
rmdir "$stage/payload" "$stage"
