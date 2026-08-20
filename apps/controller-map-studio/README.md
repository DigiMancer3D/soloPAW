# soloPAW Controller Map Studio — v0.1.0-rc.1

A Linux-native WYSIWYG controller-map editor built around the soloPAW / Logitech G502 / Cyberpunk 2077 workflow.

RC1 is the first release-sealed build. It is based on the user-verified Alpha 6 desktop build and intentionally excludes development-only test suites, historical GUI screenshots, roadmap files, and unused authoring/reference artifacts from the distributed application.

## Install on CachyOS / KDE Plasma

Extract the archive and run:

```bash
./setup_cachyos.sh
./verify_release.sh
./install_desktop.sh
```

The desktop installer is user-local and does not use `sudo`. It installs to the current user's XDG directories:

- application: `~/.local/share/solopaw-controller-map-studio/app/`
- command: `~/.local/bin/solopaw-controller-map-studio`
- desktop launcher: `~/.local/share/applications/solopaw-controller-map-studio.desktop`
- icons: `~/.local/share/icons/hicolor/`
- `.udata` MIME registration: `~/.local/share/mime/packages/`

After installation, search KDE's Application Launcher for **soloPAW Controller Map Studio**, then pin it to the panel/task manager if desired.

## Launch

From the extracted folder:

```bash
./launch.sh
```

After desktop installation:

```bash
solopaw-controller-map-studio
```

Open a project directly:

```bash
solopaw-controller-map-studio "/path/to/project.udata"
```

Dolphin can also open registered `.udata` files directly into the Studio.

## Core workflow

The `.udata` project is the source of truth. A project can carry:

- WYSIWYG controller/card geometry and routed connectors;
- structured Normal / G-Shift Tap / Double / Hold content;
- embedded controller/background/icon assets;
- Cyberpunk Binding Table data and live visual key links;
- G502 Input Remapper mappings and dependency metadata.

Primary exports include:

- PNG map;
- `G502 Remapper.json`;
- `Binding Table.json` and CSV;
- Complete Export Bundle ZIP containing the project, rendered map, remapper profile, binding tables, manifest, and checksums.

## Release verification

Run:

```bash
./verify_release.sh
```

The verifier checks the release seal, per-file SHA256 values, Python source compilation, version stamp, default `.udata` schema, desktop integration files, and confirms that development-only directories were not shipped.

## Desktop diagnostics

```bash
./desktop_check.sh
```

Desktop launch output is written to:

```text
~/.local/state/solopaw-controller-map-studio/launch.log
```

## Uninstall

```bash
./uninstall_desktop.sh
```

To also remove Studio UI preferences and launch logs:

```bash
./uninstall_desktop.sh --purge-config
```

Saved `.udata` projects outside the installed application directory are not deleted.

## Recovery

See `RECOVERY.md` before moving systems, reinstalling the OS, or replacing an installed build.

## Release status

**v0.1.0-rc.1** is a release candidate. The application's major authoring feature set is sealed for RC testing; remaining changes before a final v0.1.0 release should be limited to verified defects, compatibility fixes, packaging corrections, and documentation/recovery improvements.
