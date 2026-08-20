#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="${HOME}/.local/share/solopaw-profile-switcher"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"

printf '%s\n' "soloPAW Profile Switcher installer" ""

command -v python3 >/dev/null 2>&1 || {
    echo "ERROR: python3 is required."
    exit 1
}

missing=0
python3 -c 'import tkinter' >/dev/null 2>&1 || missing=1
command -v input-remapper-control >/dev/null 2>&1 || missing=1

if (( missing )); then
    echo "One or more optional/runtime dependencies are missing."
    echo "The bundled dependency helper can identify your distro and offer official/recommended install commands."
    if [[ -t 0 ]]; then
        read -r -p "Run setup_dependencies.sh now? [y/N] " ans
        case "$ans" in y|Y|yes|YES) "$SOURCE_DIR/setup_dependencies.sh" ;; *) echo "Continuing install; Service Doctor can help later." ;; esac
    else
        echo "Run: $SOURCE_DIR/setup_dependencies.sh"
    fi
fi

mkdir -p "$APP_HOME" "$BIN_DIR" "$DESKTOP_DIR"
install -m 0755 "$SOURCE_DIR/solopaw_profile_switcher.py" "$APP_HOME/solopaw_profile_switcher.py"
install -m 0755 "$SOURCE_DIR/setup_dependencies.sh" "$APP_HOME/setup_dependencies.sh"
install -m 0644 "$SOURCE_DIR/README.md" "$APP_HOME/README.md"
install -m 0644 "$SOURCE_DIR/CHANGELOG.md" "$APP_HOME/CHANGELOG.md"

cat > "$BIN_DIR/solopaw-profile-switcher" <<'EOF'
#!/usr/bin/env bash
exec python3 "$HOME/.local/share/solopaw-profile-switcher/solopaw_profile_switcher.py" "$@"
EOF
chmod +x "$BIN_DIR/solopaw-profile-switcher"

cat > "$DESKTOP_DIR/solopaw-profile-switcher.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=soloPAW Profile Switcher
Comment=Stream-safe Input Remapper profile switcher
Exec=solopaw-profile-switcher
Icon=input-gaming
Terminal=false
Categories=Utility;Settings;Accessibility;
StartupNotify=true
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo "Installed."
echo "Launch from KDE as: soloPAW Profile Switcher"
echo "Terminal command:     solopaw-profile-switcher"
echo
echo "Privacy note: generated launcher files use \$HOME/PATH lookup and do not embed your username or absolute home path."
