#!/bin/sh
# Starts WebPlus inside its Flatpak sandbox.
export ASPELL_CONF="dict-dir /app/lib/aspell-0.60; data-dir /app/lib/aspell-0.60"
exec python3 /app/share/webplus/sitewright.py "$@"
