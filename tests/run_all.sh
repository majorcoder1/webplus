#!/bin/bash
# Runs every test. Each must print ALL GOOD (the PHP one prints SKIPPED without php).
# Tests get their own empty settings folder so they never touch your real program settings.
cd "$(dirname "$0")/.." || exit 1
export QT_QPA_PLATFORM=offscreen
export XDG_CONFIG_HOME="$(mktemp -d)"
export WEBSITE_DEFAULTS="$XDG_CONFIG_HOME/defaults.json"
status=0
for t in tests/test_*.py; do
    printf '%-30s ' "$t"
    out="$(timeout 300 python3 -u "$t" 2>&1 | grep -v propagateSizeHints | tail -1)"
    echo "$out"
    case "$out" in "ALL GOOD"|SKIPPED*) ;; *) status=1;; esac
done
rm -rf "$XDG_CONFIG_HOME"
[ $status -eq 0 ] && echo "EVERYTHING PASSED" || echo "SOMETHING FAILED"
exit $status
