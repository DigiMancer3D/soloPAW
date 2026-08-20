# soloPAW Profile Switcher changelog

## v0.2.1

- Updated the bundled/default Cyberpunk profile to v2.8 (`JDirect-ScanH-QuickW`).
- Changed the default startup window to 1230×870.
- Preserved Stream Mode, public-safe export/import, dependency setup, aliases, and three quick slots.

## v0.2.0

- Added **Stream Mode** (enabled by default) to hide preset filenames in the main UI.
- Added public-safe profile export with recursive `origin_hash` removal and local identity/path audit.
- Added profile import with JSON validation and backup-before-replace behavior.
- Added distro-aware `setup_dependencies.sh` for Input Remapper and Tk detection/installation guidance.
- Added GUI `Install / Repair Dependencies…` launcher.
- Hardened generated desktop/command launchers so they do not embed the local username/home path.
- Added public/reference Cyberpunk 2077 v2.5 and Megabonk v1.1 G502 profiles.
- Added `tools/privacy_audit.py` for release/profile privacy checks.
- Added profile-sharing privacy documentation.
- Expanded GitHub README for single-handed gameplay, accessibility layouts, advanced mouse controls, streaming, installation, and troubleshooting.
- Preserved all v0.1 quick-preset, Common Name, activate, auto-reload, Service Doctor, and folder-opening behavior.

## v0.1.0

- Initial local Python/Tk profile switcher.
- Three editable quick-preset slots.
- Common Name aliases.
- Active/autoload status panel.
- Input Remapper preset activation and autoload management.
- Stream-conscious main UI.
