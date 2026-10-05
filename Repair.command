#!/bin/bash
cd "$(dirname "$0")" || exit 1
/bin/bash scripts/macos.sh repair "$@"
result=$?
echo
read -r -p 'Press Enter to close...'
exit "$result"
