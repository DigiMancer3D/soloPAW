#!/usr/bin/env bash
set -euo pipefail

APP_NAME="soloPAW Profile Switcher"
ASSUME_YES=0
PRINT_ONLY=0

for arg in "$@"; do
    case "$arg" in
        --yes|-y) ASSUME_YES=1 ;;
        --print) PRINT_ONLY=1 ;;
        --help|-h)
            cat <<'EOF'
Usage: ./setup_dependencies.sh [--yes] [--print]

Detects the Linux family and offers distro-appropriate installation commands
for Python/Tk and Input Remapper. No package installation occurs without an
explicit yes answer unless --yes is supplied.
EOF
            exit 0
            ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

say() { printf '%s\n' "$*"; }

if [[ ! -r /etc/os-release ]]; then
    say "Could not identify this Linux distribution."
    say "Use the upstream Input Remapper installation guide:"
    say "  https://github.com/sezanzeb/input-remapper#installation"
    exit 3
fi

# shellcheck disable=SC1091
. /etc/os-release
ID_LOWER="${ID:-unknown}"
ID_LIKE_LOWER="${ID_LIKE:-}"
ID_LOWER="${ID_LOWER,,}"
ID_LIKE_LOWER="${ID_LIKE_LOWER,,}"
PRETTY="${PRETTY_NAME:-$ID_LOWER}"

family="unknown"
case " $ID_LOWER $ID_LIKE_LOWER " in
    *" arch "*|*" cachyos "*|*" manjaro "*|*" endeavouros "*) family="arch" ;;
    *" debian "*|*" ubuntu "*|*" linuxmint "*|*" pop "*) family="debian" ;;
    *" fedora "*|*" rhel "*) family="fedora" ;;
    *" void "*) family="void" ;;
esac

need_tk=0
need_remapper=0
python3 -c 'import tkinter' >/dev/null 2>&1 || need_tk=1
command -v input-remapper-control >/dev/null 2>&1 || need_remapper=1

say "$APP_NAME dependency helper"
say "Detected: $PRETTY"
say

if (( need_tk == 0 )); then say "PASS: Python Tkinter is available."; else say "MISSING: Python Tkinter."; fi
if (( need_remapper == 0 )); then say "PASS: Input Remapper command is available."; else say "MISSING: input-remapper-control."; fi
say

if (( need_tk == 0 && need_remapper == 0 )); then
    if command -v systemctl >/dev/null 2>&1; then
        say "Ensuring the Input Remapper service is enabled is recommended:"
        say "  sudo systemctl enable --now input-remapper"
    fi
    exit 0
fi

commands=()
case "$family" in
    arch)
        if (( need_tk )); then commands+=("sudo pacman -S --needed tk"); fi
        if (( need_remapper )); then
            if command -v yay >/dev/null 2>&1; then
                commands+=("yay -S --needed input-remapper-git")
            elif command -v paru >/dev/null 2>&1; then
                commands+=("paru -S --needed input-remapper-git")
            else
                say "Input Remapper upstream currently documents the Arch install through the AUR:"
                say "  yay -S input-remapper-git"
                say "No yay/paru AUR helper was found, so this helper will not auto-bootstrap one."
            fi
        fi
        ;;
    debian)
        if (( need_tk )); then commands+=("sudo apt install python3-tk"); fi
        if (( need_remapper )); then commands+=("sudo apt install input-remapper"); fi
        ;;
    fedora)
        if (( need_tk )); then commands+=("sudo dnf install python3-tkinter"); fi
        if (( need_remapper )); then commands+=("sudo dnf install input-remapper"); fi
        ;;
    void)
        if (( need_tk )); then commands+=("sudo xbps-install -S python3-tkinter"); fi
        if (( need_remapper )); then commands+=("sudo xbps-install -S input-remapper"); fi
        ;;
    *)
        say "This distro is not auto-installed by the helper."
        say "Use the official upstream instructions:"
        say "  https://github.com/sezanzeb/input-remapper#installation"
        exit 4
        ;;
esac

if ((${#commands[@]} == 0)); then
    say "No safe automatic install command is available for the missing component(s)."
    say "Official guide: https://github.com/sezanzeb/input-remapper#installation"
    exit 5
fi

say "Planned commands:"
for cmd in "${commands[@]}"; do say "  $cmd"; done
if [[ "$family" != "void" ]]; then say "  sudo systemctl enable --now input-remapper"; fi
say

if (( PRINT_ONLY )); then exit 0; fi

if (( ASSUME_YES == 0 )); then
    read -r -p "Run these dependency commands now? [y/N] " answer
    case "$answer" in y|Y|yes|YES) ;; *) say "Cancelled."; exit 0 ;; esac
fi

for cmd in "${commands[@]}"; do
    say "+ $cmd"
    bash -lc "$cmd"
done

if [[ "$family" == "void" ]]; then
    if (( need_remapper )); then
        say "Void service setup from upstream documentation:"
        say "  sudo ln -s /etc/sv/input-remapper /var/service"
        say "  sudo sv up input-remapper"
    fi
else
    if command -v systemctl >/dev/null 2>&1 && command -v input-remapper-control >/dev/null 2>&1; then
        sudo systemctl enable --now input-remapper
    fi
fi

say
say "Dependency setup finished."
