#!/usr/bin/env bash
set -euo pipefail
APP_ID="solopaw-controller-map-studio"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
PURGE=0
[[ "${1:-}" == "--purge-config" ]] && PURGE=1
rm -rf "$DATA_HOME/$APP_ID"
rm -f "$DATA_HOME/applications/$APP_ID.desktop"
rm -f "$DATA_HOME/icons/hicolor/256x256/apps/$APP_ID.png"
rm -f "$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg"
rm -f "$DATA_HOME/mime/packages/$APP_ID.xml"
rm -f "$BIN_HOME/$APP_ID"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DATA_HOME/applications" >/dev/null 2>&1 || true
command -v update-mime-database >/dev/null 2>&1 && update-mime-database "$DATA_HOME/mime" >/dev/null 2>&1 || true
if (( PURGE )); then
  rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/$APP_ID" "${XDG_STATE_HOME:-$HOME/.local/state}/$APP_ID"
  echo "Removed desktop installation plus UI configuration and launch logs."
else
  echo "Removed desktop installation. UI configuration and launch logs were preserved."
fi
