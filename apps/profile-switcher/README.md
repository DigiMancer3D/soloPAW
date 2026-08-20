# 🐾 soloPAW Profile Switcher

![Linux](https://img.shields.io/badge/Linux-X11%20%7C%20Wayland-2ea44f)
![Python](https://img.shields.io/badge/Python-3.x-3776ab)
![GUI](https://img.shields.io/badge/GUI-Tk-7952b3)
![Input Remapper](https://img.shields.io/badge/Input%20Remapper-2.x-orange)
![Local only](https://img.shields.io/badge/network-local--only-blue)
![Stream safe](https://img.shields.io/badge/design-stream--safe-ff69b4)

**soloPAW Profile Switcher** is a small local Linux GUI for people who use a gaming mouse as a dense control surface — including single-handed play, accessibility layouts, editing shortcuts, and advanced per-game mouse maps.

It does **not replace Input Remapper**. It gives Input Remapper a faster, friendlier profile-switching front end.

> **v0.2.1 integration update:** latest Cyberpunk v2.8 starter profile and 1230×870 default window, while retaining the v0.2.0 privacy/import/export features.

> **v0.2.0 highlights:** Stream Mode, public-safe profile export/import, distro-aware dependency setup, public example G502 profiles, and stronger privacy checks.

---

## ✨ What it does

```text
┌─────────────────────────────────────────────────────────────────┐
│  Quick Preset 1        Quick Preset 2        Quick Preset 3    │
│  [ Cyberpunk 2077 ]    [ Megabonk ]          [ Editing ]       │
├──────────────────────────────┬──────────────────────────────────┤
│ Available profiles           │ Current State                    │
│                              │                                  │
│ Cyberpunk 2077 — soloPAW     │ ACTIVE NOW                       │
│ Megabonk — Direct Keys       │ Megabonk — Direct Keys           │
│ Krita Editing                │                                  │
│ ...                          │ AUTO-RELOAD                      │
│                              │ Cyberpunk 2077 — soloPAW         │
│ [Activate] [Auto-Reload]     │                                  │
│ [Export] [Import]            │ [Service Doctor]                 │
└──────────────────────────────┴──────────────────────────────────┘
```

- 📚 Lists Input Remapper profiles for the configured G502 device.
- ⚡ Three editable quick-preset buttons for fast game/app changes.
- 🏷️ Adds a **Common Name** without renaming or touching the real preset file.
- 🎮 Activates a selected Input Remapper preset immediately.
- 🔁 Sets a selected preset as Input Remapper **Auto-Reload**.
- 👁️ Shows **Active Now** and **Auto-Reload** separately.
- 🩺 Includes a sanitized **Service Doctor**.
- 📦 Imports shared `.json` Input Remapper profiles.
- 🛡️ Exports **public-safe copies** of profiles for GitHub/community sharing.
- 📁 Can open the real preset folder explicitly when you are off-stream.

---

## 🔒 Privacy & livestream design

The source code uses standard per-user locations such as:

```text
~/.config/input-remapper-2/
~/.config/solopaw-profile-switcher/
~/.local/share/solopaw-profile-switcher/
```

Internally Python resolves those with `Path.home()` at runtime. The repository does **not** hardcode a personal username, home directory, hostname, or `/home/<person>/...` path.

### Stream Mode

**Stream Mode is ON by default.** It hides profile filenames from the main interface and shows Common Names instead.

The main window intentionally does not display:

- your home-directory path;
- local username;
- hostname;
- `/dev/input/eventXX` paths;
- raw Input Remapper journal output;
- tokens, credentials, or network/account information.

Controls that can naturally reveal local filesystem locations are explicitly marked **off-stream**:

- `Export Public-Safe Copy`
- `Import Profile`
- `Open Profile Folder`

The operating-system file dialog/file manager may show your real folders, so use those controls when they are safe to display.

### Installed launchers are privacy-safe too

The generated KDE `.desktop` file uses:

```text
Exec=solopaw-profile-switcher
```

and the launcher resolves `$HOME` at runtime. It does not embed `/home/<username>` into the generated launcher.

See [PROFILE_SHARING.md](docs/PROFILE_SHARING.md) for the public-profile workflow.

---

## 🎯 Included starter profiles

The release includes public/reference copies of the two G502 profiles used while developing the switcher:

| Profile | Purpose |
|---|---|
| `soloPAW-Cyberpunk2077-v2.8-JDirect-ScanH-QuickW.json` | Dense Cyberpunk 2077 G502 map using G-Shift, tap/double/hold states, native vertical wheel behavior, driving, BrainDance, and UI actions |
| `soloPAW-Megabonk-v1.1-DirectKeys-Esc.json` | Simpler direct-key G502 map intended for games that need ordinary press/hold behavior rather than timing macros |

They live in:

```text
profiles/public/
```

These are **reference profiles**, not universal G502 presets. Input event codes can differ if your mouse onboard configuration differs. Test safely before enabling autoload.

The public copies contain no `origin_hash`, username, home path, or machine hostname.

---

## 🚀 Quick start

### 1. Extract

```bash
unzip soloPAW_Profile_Switcher_v0.2.1_Public_Release.zip
cd soloPAW_Profile_Switcher_v0.2.1
```

### 2. Check/install dependencies

```bash
./setup_dependencies.sh
```

The helper identifies common Linux families and **asks before installing anything**.

Supported guided paths:

| Linux family | Input Remapper path used by helper |
|---|---|
| Arch / CachyOS / Manjaro / EndeavourOS | AUR `input-remapper-git` via existing `yay` or `paru` |
| Debian / Ubuntu family | `apt install input-remapper` |
| Fedora family | `dnf install input-remapper` |
| Void | `xbps-install input-remapper` |

If an Arch-family machine has no AUR helper, soloPAW does **not** silently bootstrap one. It prints the upstream installation path so the user can make that choice themselves.

Input Remapper upstream installation documentation: [sezanzeb/input-remapper](https://github.com/sezanzeb/input-remapper#installation)

### 3. Install the switcher

```bash
chmod +x install.sh
./install.sh
```

Then start it from your desktop application menu:

```text
soloPAW Profile Switcher
```

or from a terminal:

```bash
solopaw-profile-switcher
```

### Portable mode

```bash
./run.sh
```

---

## 🧰 How profile switching works

The switcher uses Input Remapper's normal CLI operation:

```bash
input-remapper-control \
  --command start \
  --device "Logitech G502 HERO Gaming Mouse" \
  --preset "PROFILE_NAME"
```

It does **not** rewrite a preset just to activate it.

Input Remapper documents the preset storage/config layout under `~/.config/input-remapper-2/` and supports named preset activation through `input-remapper-control`.

---

## 🔁 Active profile vs Auto-Reload

They are intentionally separate.

Example:

```text
ACTIVE NOW
Megabonk — Direct Keys

AUTO-RELOAD
Cyberpunk 2077 — soloPAW
```

That means you can temporarily switch games without changing the profile that returns automatically later.

`Set Auto-Reload` updates only this device's entry in Input Remapper's `config.json` and creates a timestamped backup first.

---

## 🏷️ Common Names

Input Remapper preset filenames often become descriptive/technical:

```text
soloPAW-Cyberpunk2077-v2.5-ContextSafe-RaceCameraMenus
```

soloPAW can display that as:

```text
Cyberpunk Main
```

The Common Name is stored only in:

```text
~/.config/solopaw-profile-switcher/config.json
```

Changing it does **not** rename the actual Input Remapper file and therefore does not invalidate a tested preset or its autoload entry.

---

## 📤 Share a profile without sharing your identity

Select a profile and choose:

```text
Export Public-Safe Copy (off-stream)
```

The exporter:

1. validates that the file looks like an Input Remapper preset;
2. removes `origin_hash` values from the public copy;
3. checks string values for the current home path, username, hostname, and common local-path patterns;
4. blocks the export if suspicious local identity/path data remains;
5. exports **only the mapping JSON** — not your app aliases, Input Remapper autoload config, journal, or system information.

Why remove `origin_hash`? Input Remapper describes it as an internally computed identifier used to associate an input with a particular `/dev/input/eventXX` device. Removing it makes a shared copy less machine-specific and avoids publishing an unnecessary device-specific identifier.

> Some complex multi-interface presets genuinely need `origin_hash` to distinguish similar event devices. A stripped public copy may need the recipient to re-record those particular inputs locally.

The included `tools/privacy_audit.py` can also scan a profile or project tree before publishing.

---

## 📥 Import a shared profile

Click:

```text
Import Profile (off-stream)
```

Choose a downloaded `.json` preset, pick its local filename, and soloPAW copies it into the configured G502 preset directory.

Existing files are backed up before replacement.

Always test a downloaded mapping manually before setting it as Auto-Reload.

---

## 🩺 Service Doctor

Service Doctor reports only sanitized status:

- detected Linux family;
- whether `input-remapper-control` exists;
- whether the service is active;
- whether the service is enabled;
- whether the CLI/service handshake works;
- visible profile count;
- active **Common Name**;
- auto-reload **Common Name**.

It intentionally does not dump raw logs into the stream-facing UI.

---

## 🧩 Missing Input Remapper?

From the repository:

```bash
./setup_dependencies.sh
```

Or use **Install / Repair Dependencies…** inside the GUI. It opens the same helper in a terminal and still requires confirmation before package installation.

The helper follows current upstream installation recommendations where practical; it does not download unknown binaries or silently install an AUR helper.

---

## 🐭 Why a G502?

A mouse such as the Logitech G502 exposes enough physical controls to act as a compact control surface:

```text
left/right click
wheel click
wheel tilt left/right
G4/G5/G6/G7/G8/G9
wheel up/down
```

Input Remapper can then layer combinations, ordinary direct-key mappings, and optional macros over those controls.

That can be useful for:

- single-handed gameplay;
- reducing keyboard reach;
- per-game accessibility layouts;
- video/image editing shortcuts;
- streaming controls;
- context-heavy games with driving/UI/combat modes;
- people who simply prefer dense mouse-first controls.

soloPAW does not assume every user wants the same map. The profile switcher exists specifically so each game/application can have its own layout.

---

## ⚠️ Input behavior notes

Not every game accepts every kind of injected input equally.

Some games behave best with ordinary direct key mappings, while others work well with Input Remapper macros such as tap/double/hold classifiers. Keep separate profiles when a game needs stricter direct press/release behavior.

If an autoload mapping makes a device difficult to use, Input Remapper's own troubleshooting documentation recommends stopping injection/unplugging-replugging the device as appropriate before repairing the preset.

---

## 💤 Suspend/resume

Some USB/input devices can disappear and re-enumerate across suspend. If your Input Remapper injector loses the device during wake, ordinary autoload may race the device's return.

soloPAW Profile Switcher does not silently install a system sleep hook. Keep resume recovery as a deliberate system-level setup because it affects device handling outside the GUI.

If you already use a resume helper that hardcodes one preset, remember that it can override a different profile selected in the switcher after waking.

---

## 🧪 Development checks

From the project root:

```bash
python3 -m py_compile solopaw_profile_switcher.py
python3 -m unittest discover -s tests -v
bash -n install.sh setup_dependencies.sh run.sh uninstall.sh
python3 tools/privacy_audit.py .
xvfb-run -a python3 solopaw_profile_switcher.py --smoke-test
```

---

## 📂 Repository layout

```text
soloPAW_Profile_Switcher_v0.2.1/
├── solopaw_profile_switcher.py
├── install.sh
├── setup_dependencies.sh
├── run.sh
├── uninstall.sh
├── README.md
├── CHANGELOG.md
├── docs/
│   └── PROFILE_SHARING.md
├── profiles/
│   └── public/
│       ├── soloPAW-Cyberpunk2077-v2.8-JDirect-ScanH-QuickW.json
│       └── soloPAW-Megabonk-v1.1-DirectKeys-Esc.json
├── tools/
│   └── privacy_audit.py
└── tests/
    ├── test_core.py
    └── test_public_profiles.py
```

---

## 🌐 Upstream project

soloPAW Profile Switcher is an independent companion utility for [Input Remapper](https://github.com/sezanzeb/input-remapper).

Useful upstream references:

- [Input Remapper installation](https://github.com/sezanzeb/input-remapper#installation)
- [Input Remapper usage](https://github.com/sezanzeb/input-remapper/blob/main/readme/usage.md)
- [Input Remapper releases](https://github.com/sezanzeb/input-remapper/releases)

Input Remapper is a separate project and is not bundled into this repository.

---

## 🎮 Project/game trademarks

Logitech, G502, Cyberpunk 2077, Megabonk, Krita, and other referenced product/game names belong to their respective owners. This project is an independent profile-management/accessibility utility and is not endorsed by those projects or companies.

---

## 🐾 Project idea

**soloPAW:** one mouse, many contexts, fast profile switching.

Keep the profile that fits the game. Keep the controls that fit the player.
