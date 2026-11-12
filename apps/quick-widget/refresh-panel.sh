#!/usr/bin/env bash
set -euo pipefail
# User-invoked refresh to make Plasma reload upgraded QML and metadata.
# Systemd-managed Plasma is standard on CachyOS KDE; do not kill the session.
if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  echo 'ERROR: run this from a terminal inside your KDE Plasma desktop session.' >&2
  exit 2
fi
if command -v systemctl >/dev/null 2>&1 && systemctl --user cat plasma-plasmashell.service >/dev/null 2>&1; then
  echo 'Reloading KDE Plasma shell through its user service…'
  systemctl --user restart plasma-plasmashell.service
  echo 'Plasma panel refresh requested.'
elif command -v kquitapp6 >/dev/null 2>&1 && command -v kstart >/dev/null 2>&1; then
  echo 'Reloading KDE Plasma shell…'
  kquitapp6 plasmashell || true
  kstart plasmashell
  echo 'Plasma panel refresh requested.'
else
  echo 'No safe automatic Plasma restart method found. Log out and back in.'
  exit 3
fi
