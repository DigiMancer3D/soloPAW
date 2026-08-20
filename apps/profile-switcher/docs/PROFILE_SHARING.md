# Public Profile Sharing & Privacy

## Short answer

Yes — an Input Remapper preset can normally be shared without publishing your home-directory path or account name because the preset JSON is primarily a collection of input event definitions and output mappings.

Use the switcher's **Export Public-Safe Copy** function rather than uploading your whole `~/.config/input-remapper-2/` directory.

## Do upload

A sanitized individual preset such as:

```text
soloPAW-Megabonk-v1.1-DirectKeys-Esc.json
```

## Do not upload as a convenience bundle

Avoid publishing the whole live configuration tree unless you have inspected it:

```text
~/.config/input-remapper-2/
```

That tree can include autoload choices, old backups, experimental presets, and other local device data that are unnecessary for sharing one map.

Also avoid publishing:

- raw `journalctl` dumps;
- screenshots of file pickers showing `/home/<username>/...`;
- generated debug logs captured while private keystrokes were entered;
- unrelated profile backups;
- shell history;
- system-info dumps containing hostnames or mount paths.

Input Remapper's own troubleshooting documentation warns that debug logs can be verbose and may contain private information entered with the device.

## What soloPAW strips/checks

The public exporter removes every `origin_hash` field from the exported copy and scans strings for:

- the current home path;
- the current username;
- the current hostname;
- `/home/<name>/...` and `/Users/<name>/...` patterns;
- `/run/user/<uid>/...`;
- Windows `C:\\Users\\<name>\\...` patterns;
- `file://` local-file references.

If a suspicious value remains, export is blocked instead of guessing what to redact inside a mapping command.

## `origin_hash` tradeoff

Input Remapper documents `origin_hash` as an internally computed identifier that associates an input with a specific `/dev/input/eventXX` source. It is useful when one physical device exposes multiple event devices with similar capabilities.

It is not a username or home path, but it is device-specific and generally unnecessary in a public example profile, so soloPAW removes it by default.

A recipient may need to re-record a particular mapping locally if that mapping depended on `origin_hash` to distinguish interfaces.

## Recommended GitHub structure

```text
profiles/
├── README.md
├── game-name/
│   └── profile-name.json
└── editing/
    └── krita-profile.json
```

For each profile, document:

- mouse/device model;
- Input Remapper version tested;
- Linux desktop/display server if relevant;
- expected in-game/app keybindings;
- whether the profile uses macros or only direct key mappings;
- whether vertical wheel handling is intentionally native;
- any required onboard mouse configuration assumptions.

## Command-line privacy audit

From this project:

```bash
python3 tools/privacy_audit.py profiles/public
```

A clean tree exits with status 0.
