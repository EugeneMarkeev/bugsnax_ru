#!/bin/bash
# Uses only utilities shipped with macOS; compatible with Apple's Bash 3.2.
set -euo pipefail
ROOT="${BUGSNAX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
ACTION="${1:-install}"
GAME="${2:-}"
case "$ACTION" in install|uninstall|check) ;; *) echo 'Use install, uninstall or check.' >&2; exit 1;; esac
fail() { printf '%s\n' "$*" >&2; exit 1; }
hash() { shasum -a 256 "$1" | awk '{print $1}'; }
find_audio() {
    local base="$1" relative candidate
    for relative in 'Content/Audio/Build/Desktop' 'Bugsnax.app/Contents/Resources/Content/Audio/Build/Desktop' 'Contents/Resources/Content/Audio/Build/Desktop' ''; do
        candidate="$base${relative:+/$relative}"
        if [ -f "$candidate/GameAudio_Filbo.bank" ]; then (cd "$candidate" && pwd); return 0; fi
    done
    return 1
}
pgrep -x Bugsnax >/dev/null && fail 'Close Bugsnax and try again.'
[ -f "$ROOT/manifest.tsv" ] || fail 'manifest.tsv is missing. Extract the complete release ZIP.'
if [ -n "$GAME" ]; then
    AUDIO="$(find_audio "$GAME")" || fail 'Sound banks not found in the selected folder.'
else
    STEAM="${BUGSNAX_STEAM_ROOT:-$HOME/Library/Application Support/Steam}"
    LIBRARIES=("$STEAM")
    if [ -f "$STEAM/steamapps/libraryfolders.vdf" ]; then
        while IFS= read -r library; do LIBRARIES+=("$library"); done < <(awk -F '"' '$2=="path" {print $4}' "$STEAM/steamapps/libraryfolders.vdf")
    fi
    AUDIO=''
    for library in "${LIBRARIES[@]}"; do
        AUDIO="$(find_audio "$library/steamapps/common/Bugsnax")" || continue
        break
    done
    if [ -z "$AUDIO" ]; then
        GAME="$(osascript -e 'POSIX path of (choose folder with prompt "Select Bugsnax folder: Steam > Manage > Browse local files")')" || fail 'Cancelled.'
        AUDIO="$(find_audio "$GAME")" || fail 'Sound banks not found in the selected folder.'
    fi
fi
printf 'Game sound folder: %s\n' "$AUDIO"
STATE="$AUDIO/.bugsnax-russian-voice"
BACKUP="$STATE/backup"
TAB=$'\t'
COUNT=0
# Validate all files before modifying any game bank.
while IFS="$TAB" read -r name original patched bytes; do
    [ "$name" = name ] && continue
    COUNT=$((COUNT+1))
    [[ "$name" =~ ^[A-Za-z0-9_]+\.bank$ ]] || fail 'Invalid bank name.'
    [[ "$original" =~ ^[a-f0-9]{64}$ && "$patched" =~ ^[a-f0-9]{64}$ ]] || fail 'Invalid manifest checksum.'
    current="$(hash "$AUDIO/$name")"
    [ "$current" = "$original" ] || [ "$current" = "$patched" ] || fail "Unsupported game version or another audio mod: $name. No game files changed."
    if [ "$ACTION" = uninstall ] && [ "$current" != "$original" ]; then
        [ -f "$BACKUP/$name" ] && [ "$(hash "$BACKUP/$name")" = "$original" ] || fail 'Original backup is missing or damaged. Restore the game using Steam file verification.'
    fi
    if [ -f "$BACKUP/$name" ]; then [ "$(hash "$BACKUP/$name")" = "$original" ] || fail "Damaged backup: $name"; fi
done < "$ROOT/manifest.tsv"
[ "$COUNT" -gt 0 ] || fail 'Empty bank manifest.'
if [ "$ACTION" = install ]; then
    /bin/bash "$(dirname "$0")/download_sound.sh" "$ROOT"
    while IFS="$TAB" read -r name original patched bytes; do
        [ "$name" = name ] && continue
        [ "$(hash "$ROOT/payload/$name")" = "$patched" ] || fail "Damaged sound pack file: $name"
    done < "$ROOT/manifest.tsv"
fi
if [ "$ACTION" = check ]; then echo 'Compatible sound banks. No changes made.'; exit 0; fi
mkdir -p "$BACKUP"
mkdir "$STATE/lock" || fail 'Another installer is running, or a stale lock remains. Check before retrying.'
STAGE=''
CHANGED=()
COMMITTED=0
cleanup() {
    local code=$? name
    trap - EXIT
    if [ "$COMMITTED" != 1 ]; then
        for name in ${CHANGED[@]+"${CHANGED[@]}"}; do
            if ! cp "$STAGE/$name.old" "$AUDIO/$name" || [ "$(hash "$AUDIO/$name")" != "$(hash "$STAGE/$name.old")" ]; then
                printf 'Rollback failed. Recovery files: %s\n' "$STAGE" >&2
                code=1
            fi
        done
    elif [ -n "$STAGE" ]; then
        for name in "$STAGE"/*.old; do [ ! -f "$name" ] || rm "$name"; done
        rmdir "$STAGE" || true
    fi
    rmdir "$STATE/lock" || true
    exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
STAGE="$(mktemp -d "$STATE/transaction.XXXXXX")"
while IFS="$TAB" read -r name original patched bytes; do
    [ "$name" = name ] && continue
    current="$(hash "$AUDIO/$name")"
    if [ "$ACTION" = install ]; then desired="$patched"; source="$ROOT/payload/$name"; else desired="$original"; source="$BACKUP/$name"; fi
    [ "$current" != "$desired" ] || continue
    if [ "$ACTION" = install ] && [ ! -f "$BACKUP/$name" ]; then
        [ "$current" = "$original" ] || fail 'Game files changed during installation.'
        cp "$AUDIO/$name" "$BACKUP/$name"
        [ "$(hash "$BACKUP/$name")" = "$original" ] || fail 'Original backup checksum mismatch.'
    fi
    cp "$AUDIO/$name" "$STAGE/$name.old"
    cp "$source" "$STAGE/$name.new"
    [ "$(hash "$STAGE/$name.new")" = "$desired" ] || fail 'Staged file checksum mismatch.'
done < "$ROOT/manifest.tsv"
while IFS="$TAB" read -r name original patched bytes; do
    [ "$name" = name ] && continue
    if [ -f "$STAGE/$name.new" ]; then
        [ "$(hash "$AUDIO/$name")" = "$(hash "$STAGE/$name.old")" ] || fail 'Game files changed during installation.'
        CHANGED+=("$name")
        mv -f "$STAGE/$name.new" "$AUDIO/$name"
    fi
    if [ "$ACTION" = install ]; then desired="$patched"; else desired="$original"; fi
    [ "$(hash "$AUDIO/$name")" = "$desired" ] || fail 'Final verification failed.'
done < "$ROOT/manifest.tsv"
printf 'version=0.1.1\naction=%s\nverified=true\n' "$ACTION" > "$STATE/status.txt"
COMMITTED=1
if [ "$ACTION" = install ]; then
    echo 'Russian voices installed. Start Bugsnax through Steam. Select Russian in Steam game properties for subtitles.'
else echo 'Original voices restored.'; fi
