#!/usr/bin/env bash
set -euo pipefail
APP_ID="solopaw-controller-map-studio"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP_DIR="$DATA_HOME/$APP_ID/app"
fail=0
check_file() { if [[ -e "$1" ]]; then printf 'PASS: %s\n' "$2"; else printf 'FAIL: %s (%s)\n' "$2" "$1"; fail=1; fi; }
check_file "$APP_DIR/main.py" "installed application"
check_file "$BIN_HOME/$APP_ID" "command wrapper"
check_file "$DATA_HOME/applications/$APP_ID.desktop" "desktop launcher"
check_file "$DATA_HOME/icons/hicolor/256x256/apps/$APP_ID.png" "PNG app icon"
check_file "$DATA_HOME/mime/packages/$APP_ID.xml" "UDATA MIME registration"
if [[ -x "$BIN_HOME/$APP_ID" ]]; then
  if version="$($BIN_HOME/$APP_ID --version 2>/dev/null)"; then
    printf 'PASS: launcher runtime — %s\n' "$version"
  else
    printf 'FAIL: launcher runtime (see %s)\n' "${XDG_STATE_HOME:-$HOME/.local/state}/$APP_ID/launch.log"
    fail=1
  fi
fi
if command -v xdg-mime >/dev/null 2>&1; then
  assoc="$(xdg-mime query default application/x-solopaw-udata 2>/dev/null || true)"
  if [[ "$assoc" == "$APP_ID.desktop" ]]; then printf 'PASS: .udata default association\n'; else printf 'INFO: .udata association is %s\n' "${assoc:-unset}"; fi
fi
exit "$fail"
