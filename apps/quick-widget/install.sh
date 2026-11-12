#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WID="org.digimancer3d.solopaw.quickwidget"
DATA="$HOME/.local/share/solopaw-profile-switcher-widget"
BIN="$HOME/.local/bin"

if ! command -v python3 >/dev/null 2>&1; then
  echo 'ERROR: python3 is required.' >&2; exit 2
fi
if ! command -v kpackagetool6 >/dev/null 2>&1; then
  echo 'ERROR: kpackagetool6 (KDE Plasma 6) is required. No files were installed.' >&2; exit 2
fi
if ! command -v busctl >/dev/null 2>&1; then
  echo 'WARNING: busctl not found; running-preset verification cannot currently succeed.' >&2
fi
if ! command -v input-remapper-control >/dev/null 2>&1; then
  echo 'WARNING: input-remapper-control not found; widget can install but cannot switch profiles yet.' >&2
fi

mkdir -p "$DATA" "$BIN"
install -m 755 "$ROOT/helper/solopaw_widget_helper.py" "$DATA/solopaw_widget_helper.py"
cat > "$BIN/solopaw-widget-helper" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec python3 "$HOME/.local/share/solopaw-profile-switcher-widget/solopaw_widget_helper.py" "$@"
EOF
chmod 755 "$BIN/solopaw-widget-helper"

# Install our user-scoped icon into the icon-theme search path. Plasma's
# "Add Widgets" browser uses KPlugin.Icon, not contents/images/logo.png.
for size in 128 256; do
  ICON_DIR="$HOME/.local/share/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$ICON_DIR"
  install -m 644 "$ROOT/icon-theme/hicolor/${size}x${size}/apps/solopaw-quick-switch.png" "$ICON_DIR/solopaw-quick-switch.png"
done
THEME_DIR="$HOME/.local/share/icons/hicolor"
if [[ ! -e "$THEME_DIR/index.theme" && -f /usr/share/icons/hicolor/index.theme ]]; then
  cp /usr/share/icons/hicolor/index.theme "$THEME_DIR/index.theme"
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1 && [[ -f "$THEME_DIR/index.theme" ]]; then
  gtk-update-icon-cache -f "$THEME_DIR" >/dev/null 2>&1 || true
fi
if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi

if kpackagetool6 --type Plasma/Applet --show "$WID" >/dev/null 2>&1; then
  kpackagetool6 --type Plasma/Applet --upgrade "$ROOT/widget"
else
  kpackagetool6 --type Plasma/Applet --install "$ROOT/widget"
fi

echo
echo 'Installed: soloPAW Quick Presets 1·2·3 (Plasma 6 widget)'
echo 'Your existing Profile Switcher and presets were NOT modified by this installer.'
echo 'NEXT: right-click KDE panel → Enter Edit Mode → Add Widgets → search soloPAW → drag it to your panel.'
echo 'Check: ~/.local/bin/solopaw-widget-helper doctor'
echo 'The optional native CLI is only used if the installed source visibly supports --activate-slot.'
echo 'A Plasma shell refresh is required to display the new artwork and sizing.'
if [[ -t 0 && -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  printf 'Refresh your KDE panel now (brief panel blink)? [Y/n] '
  read -r reply || reply=n
  if [[ ! "$reply" =~ ^[Nn] ]]; then
    bash "$ROOT/refresh-panel.sh"
  else
    echo 'Run bash ./refresh-panel.sh later, or log out and back in.'
  fi
else
  echo 'Run bash ./refresh-panel.sh inside your KDE desktop to reload the widget.'
fi
