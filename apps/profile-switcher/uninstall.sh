#!/usr/bin/env bash
set -euo pipefail
rm -f "$HOME/.local/bin/solopaw-profile-switcher"
rm -f "$HOME/.local/share/applications/solopaw-profile-switcher.desktop"
rm -rf "$HOME/.local/share/solopaw-profile-switcher"
echo "Program files removed."
echo "Preserved: ~/.config/solopaw-profile-switcher/"
echo "Preserved: all Input Remapper profiles and configuration."
