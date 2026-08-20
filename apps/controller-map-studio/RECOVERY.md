# soloPAW Controller Map Studio — Recovery & Backup Guide

## What to preserve first

The most important files are your authored `*.udata` projects. They are the source of truth for visual layout, embedded assets, Binding Table data, and the Studio-side G502 remapper/dependency model.

Also keep any Complete Export Bundle ZIPs you created. A bundle contains a snapshot of the `.udata`, rendered PNG, G502 Remapper JSON, Binding Table JSON/CSV, manifest, and checksums.

## Recommended backup set

Before an OS reinstall or major update, back up:

1. every `*.udata` project you care about;
2. recent Complete Export Bundle ZIPs;
3. any standalone `G502 Remapper.json` profiles you exported;
4. any Binding Table JSON/CSV exports you want independently;
5. optional Studio UI preferences at `~/.config/solopaw-controller-map-studio/`;
6. optional launch diagnostics at `~/.local/state/solopaw-controller-map-studio/`.

The installed application under `~/.local/share/solopaw-controller-map-studio/` can be recreated from the release archive and does not need to be treated as project data.

## Restore after reinstall

1. Extract the RC/release archive.
2. Run `./setup_cachyos.sh`.
3. Run `./verify_release.sh`.
4. Run `./install_desktop.sh`.
5. Open your saved `.udata` project from Dolphin or with `solopaw-controller-map-studio /path/to/project.udata`.
6. Export a fresh PNG, G502 profile, or Binding Table if needed.

Older Studio project schemas are migrated when loaded by the current runtime. Save to a new filename first if you want to retain an untouched historical copy.

## Input Remapper recovery

A Studio `.udata` may contain the remapper model, and a Complete Export Bundle contains `G502 Remapper.json`. Keep the `.udata` or bundle even if an Input Remapper preset is lost from `~/.config/input-remapper-2/`.

The Studio's remapper export is intended to be the portable profile artifact. Keep the matching Binding Table with it when context-multiplexed macros are involved.

## Desktop launcher recovery

If the KDE launcher disappears but the app files remain, rerun:

```bash
./install_desktop.sh
./desktop_check.sh
```

The installer is user-local and may safely replace an older installed application copy without deleting `.udata` projects stored elsewhere.

## Launch failure

Check:

```text
~/.local/state/solopaw-controller-map-studio/launch.log
```

Then run the extracted build from a terminal with `./launch.sh` to see errors directly.

## Release integrity

Run `./verify_release.sh`. If a checksum fails, restore the affected file from the original release archive rather than hand-editing the installed copy.
