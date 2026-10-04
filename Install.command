#!/bin/bash
ROOT="$(cd "$(dirname "$0")" && pwd)"
/bin/bash "$ROOT/scripts/macos.sh" install "$@"
result=$?
printf '\nPress Enter to close...'
read -r ignored
exit "$result"
