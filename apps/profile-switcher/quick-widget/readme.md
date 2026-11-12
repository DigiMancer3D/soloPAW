# soloPAW Quick Switch,  KDE Plasma 6 widget

**Widget version: 0.1.4** · For the [soloPAW Profile Switcher](https://github.com/DigiMancer3D/soloPAW/tree/main/apps/profile-switcher) · Linux / KDE Plasma 6

A three-button native Plasma panel widget for the **three Quick Presets already configured** in the soloPAW Profile Switcher. Works on horizontal and vertical panels, using the official soloPAW Quick Switch paw + mouse artwork. The main Profile Switcher is **not** replaced by this widget.

## Installation / upgrade

From `apps/profile-switcher/quick-widget` in a local checkout, or the extracted stand-alone ZIP:

```bash
bash ./install.sh
```

If this is your first installation, right-click the KDE panel → **Enter Edit Mode** → **Add Widgets** → search for **soloPAW** → drag **soloPAW · Quick Presets 1·2·3** onto your panel. If upgrading an existing widget, it uses the same Plasma widget ID and normally keeps its position. Accept the installer prompt to refresh Plasma if convenient, or run `bash ./refresh-panel.sh` inside your KDE session.

Run a read-only diagnostic if profile status is not reported correctly:

```bash
~/.local/bin/solopaw-widget-helper doctor
~/.local/bin/solopaw-widget-helper status
```

The `activate 1`, `activate 2`, or `activate 3` helper commands **actually switch** your input mapping. Only run those when ready to change mouse behavior.

### Controls

| Gesture / display | Behavior |
|---|---|
| **Single-click** 1, 2, or 3 | Start that Quick Preset (440 ms delay to distinguish a double click) |
| **Double-click** a button | Open the full soloPAW Profile Switcher app |
| **Busy spinner** | Wait while the switch request completes and the daemon is checked |
| **Red X** | Confirmed command/injector failure; click the same button to retry |
| **Amber ?** | Switch could not be verified; click to retry |
| **Amber active mark** | Input Remapper 2.2.1 reports injector RUNNING; *exact preset name is not exposed by this daemon* |
| **Green active mark** | On supporting daemon versions, exact preset identity is verified |


### How profile detection works

The small Python helper reads the *existing* soloPAW configuration and selects the assigned Input Remapper preset. On Input Remapper **2.2.1**, it checks the D-Bus injector state after the command and displays an amber **state-only** success when the injector becomes `RUNNING`. That establishes that remapping is running, not independently which preset is active. On daemon versions exposing `get_running_preset`, the helper tries stricter group-key / preset verification. The widget also re-reads status every 12 seconds; no separate always-on service is installed.

### Dependencies

- Linux with KDE Plasma 6, `kpackagetool6`, and Plasma 5 Support data engine on Plasma 6.
- Python 3 standard library, Bash, `busctl` (systemd), and `input-remapper-control` with a running Input Remapper service.
- Existing soloPAW Profile Switcher config (`~/.config/solopaw-profile-switcher/config.json`) and the three Quick Presets in it.
- Main application launcher (`~/.local/bin/solopaw-profile-switcher`) for double-click.

This release was tested against **simulated CLI and D-Bus environments**. 

### Privacy and uninstall

- User-scoped installation only. No sudo/root steps, network calls, or dependency reinstalls.
- The install script does **not** replace the main Profile Switcher, rewrite presets, or alter Input Remapper mappings or autoload settings.
- The helper may update only `last_active_profile` in the Profile Switcher config after a verified switch / state-only applied switch; other fields are preserved.
- Log file: `~/.local/state/solopaw-profile-switcher-widget/widget.log`.
- To remove the widget and its helper while preserving your profiles, run `bash ./uninstall.sh`.

### Repository integration

This subfolder is designed to be added at:

```text
soloPAW/apps/profile-switcher/quick-widget/
```

It is **not** a replacement for `apps/profile-switcher/` itself. It does not bundle an older reconstructed copy of the main Profile Switcher. See `RELEASE_NOTES.md`, and the external `GITHUB_UPLOAD_GUIDE.md` in the delivery archive for commit instructions.

