#!/usr/bin/env bash
set -euo pipefail

APP_ID="solopaw-controller-map-studio"
APP_NAME="soloPAW Controller Map Studio"
VERSION="0.1.0-rc.1"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP_DIR="$DATA_HOME/$APP_ID/app"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
SCALABLE_ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
MIME_DIR="$DATA_HOME/mime/packages"
DESKTOP_FILE="$DESKTOP_DIR/$APP_ID.desktop"
WRAPPER="$BIN_HOME/$APP_ID"
NO_CACHE=0

for arg in "$@"; do
  case "$arg" in
    --no-cache) NO_CACHE=1 ;;
    -h|--help)
      cat <<HELP
$APP_NAME desktop installer $VERSION
Usage: ./install_desktop.sh [--no-cache]
Installs only to the current user's XDG directories; sudo is not used.
HELP
      exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

python3 - <<'PY'
missing=[]
for mod in ('tkinter','PIL'):
    try: __import__(mod)
    except Exception: missing.append(mod)
if missing:
    raise SystemExit('Missing required Python modules: ' + ', '.join(missing))
PY

mkdir -p "$APP_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$SCALABLE_ICON_DIR" "$MIME_DIR" "$BIN_HOME"

# Upgrade safely: application files live separately from user projects/config.
if [[ "$(readlink -f "$SRC_DIR")" != "$(readlink -f "$APP_DIR" 2>/dev/null || printf '%s' "$APP_DIR")" ]]; then
  rm -rf "$APP_DIR"
  mkdir -p "$APP_DIR"
  cp -a "$SRC_DIR/." "$APP_DIR/"
fi

chmod +x "$APP_DIR/launch.sh" "$APP_DIR/main.py" "$APP_DIR/setup_cachyos.sh" "$APP_DIR/desktop_check.sh" "$APP_DIR/uninstall_desktop.sh" "$APP_DIR/verify_release.sh" || true

cat > "$WRAPPER" <<WRAP
#!/usr/bin/env bash
set -u
APP_DIR="$APP_DIR"
STATE_HOME="\${XDG_STATE_HOME:-\$HOME/.local/state}"
LOG_DIR="\$STATE_HOME/$APP_ID"
LOG_FILE="\$LOG_DIR/launch.log"
mkdir -p "\$LOG_DIR"
{
  printf '\n==== %s launch ====\n' "\$(date --iso-8601=seconds 2>/dev/null || date)"
  printf 'App: %s\n' "\$APP_DIR"
  printf 'Args:'; printf ' %q' "\$@"; printf '\n'
} >>"\$LOG_FILE" 2>&1
cd "\$APP_DIR" || exit 1
if [[ "\${1:-}" == "--version" ]]; then
  exec python3 ./main.py --version
fi
python3 ./main.py "\$@" >>"\$LOG_FILE" 2>&1
status=\$?
if (( status != 0 )); then
  if command -v kdialog >/dev/null 2>&1; then
    kdialog --error "$APP_NAME failed to launch (exit \$status).\n\nLog: \$LOG_FILE"
  elif command -v zenity >/dev/null 2>&1; then
    zenity --error --text="$APP_NAME failed to launch (exit \$status). Log: \$LOG_FILE"
  fi
fi
exit \$status
WRAP
chmod +x "$WRAPPER"

cp "$APP_DIR/assets/solopaw-controller-map-studio.png" "$ICON_DIR/$APP_ID.png"
cp "$APP_DIR/assets/solopaw-controller-map-studio.svg" "$SCALABLE_ICON_DIR/$APP_ID.svg"
cp "$APP_DIR/desktop/solopaw-controller-map-studio.xml" "$MIME_DIR/$APP_ID.xml"

python3 - "$APP_DIR/desktop/solopaw-controller-map-studio.desktop.in" "$DESKTOP_FILE" "$WRAPPER" <<'PY'
from pathlib import Path
import sys
src, dst, wrapper = map(Path, sys.argv[1:])
text = src.read_text(encoding='utf-8')
# Desktop Exec paths with spaces are quoted; wrapper normally has none, but be safe.
q = '"' + str(wrapper).replace('"', '\\"') + '"'
text = text.replace('@EXEC@', q).replace('@TRYEXEC@', str(wrapper))
dst.write_text(text, encoding='utf-8')
PY
chmod 0644 "$DESKTOP_FILE"

if (( ! NO_CACHE )); then
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
  command -v update-mime-database >/dev/null 2>&1 && update-mime-database "$DATA_HOME/mime" >/dev/null 2>&1 || true
  command -v xdg-mime >/dev/null 2>&1 && xdg-mime default "$APP_ID.desktop" application/x-solopaw-udata >/dev/null 2>&1 || true
fi

printf '%s\n' "Installed $APP_NAME $VERSION"
printf 'Application: %s\n' "$APP_DIR"
printf 'Launcher:    %s\n' "$DESKTOP_FILE"
printf 'Command:     %s\n' "$WRAPPER"
printf 'MIME:        %s\n' "application/x-solopaw-udata (*.udata)"
printf '\nKDE: open the Application Launcher, search for "soloPAW Controller Map Studio", then right-click it and choose Add to Panel / Pin to Task Manager.\n'
