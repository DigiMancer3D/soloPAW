#!/usr/bin/env bash
set -euo pipefail
WID="org.digimancer3d.solopaw.quickwidget"
if command -v kpackagetool6 >/dev/null 2>&1; then
  kpackagetool6 --type Plasma/Applet --remove "$WID" || true
fi
for size in 128 256; do
  rm -f "$HOME/.local/share/icons/hicolor/${size}x${size}/apps/solopaw-quick-switch.png"
done
rm -f "$HOME/.local/bin/solopaw-widget-helper"
rm -f "$HOME/.local/share/solopaw-profile-switcher-widget/solopaw_widget_helper.py"
rmdir "$HOME/.local/share/solopaw-profile-switcher-widget" 2>/dev/null || true
printf 'Removed widget and helper. soloPAW app, config, presets, and widget logs were preserved.\n'
