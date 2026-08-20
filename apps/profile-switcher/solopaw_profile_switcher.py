#!/usr/bin/env python3
from __future__ import annotations

import getpass
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

APP_NAME = "soloPAW Profile Switcher"
APP_VERSION = "0.2.1"
DEFAULT_DEVICE = "Logitech G502 HERO Gaming Mouse"
REMAPPER_ROOT = Path.home() / ".config" / "input-remapper-2"
APP_CONFIG_DIR = Path.home() / ".config" / "solopaw-profile-switcher"
APP_CONFIG_FILE = APP_CONFIG_DIR / "config.json"
CYBERPUNK_PROFILE = "soloPAW-Cyberpunk2077-v2.8-JDirect-ScanH-QuickW"
MEGABONK_PROFILE = "soloPAW-Megabonk-v1.1-DirectKeys-Esc"

DEFAULT_CONFIG = {
    "version": 2,
    "device": DEFAULT_DEVICE,
    "common_names": {
        CYBERPUNK_PROFILE: "Cyberpunk 2077 — v2.8 soloPAW",
        MEGABONK_PROFILE: "Megabonk — Direct Keys",
    },
    "slots": [
        {"profile": CYBERPUNK_PROFILE, "label": "Cyberpunk 2077"},
        {"profile": MEGABONK_PROFILE, "label": "Megabonk"},
        {"profile": "", "label": "Preset 3"},
    ],
    "last_active_profile": "",
    "stream_mode": True,
}


# -----------------------------
# Generic helpers
# -----------------------------

def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return deepcopy(default)


def save_json_atomic(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    temp.replace(path)


def load_app_config():
    cfg = load_json(APP_CONFIG_FILE, DEFAULT_CONFIG)
    cfg.setdefault("version", 2)
    cfg["version"] = 2
    cfg.setdefault("device", DEFAULT_DEVICE)
    cfg.setdefault("common_names", {})
    cfg.setdefault("slots", [])
    cfg.setdefault("last_active_profile", "")
    cfg.setdefault("stream_mode", True)

    while len(cfg["slots"]) < 3:
        cfg["slots"].append(DEFAULT_CONFIG["slots"][len(cfg["slots"])].copy())
    cfg["slots"] = cfg["slots"][:3]

    for profile, name in DEFAULT_CONFIG["common_names"].items():
        cfg["common_names"].setdefault(profile, name)

    save_json_atomic(APP_CONFIG_FILE, cfg)
    return cfg


def friendly_name(profile: str) -> str:
    if not profile:
        return "—"
    text = profile[len("soloPAW-"):] if profile.startswith("soloPAW-") else profile
    text = re.sub(r"\s+", " ", text.replace("_", " ").replace("-", " ")).strip()
    return text or profile


def validate_profile_data(data) -> tuple[bool, str]:
    if not isinstance(data, list):
        return False, "An Input Remapper preset must be a JSON list of mappings."
    for index, mapping in enumerate(data):
        if not isinstance(mapping, dict):
            return False, f"Mapping {index} is not a JSON object."
        combination = mapping.get("input_combination")
        if not isinstance(combination, list) or not combination:
            return False, f"Mapping {index} has no valid input_combination list."
        for event in combination:
            if not isinstance(event, dict) or "type" not in event or "code" not in event:
                return False, f"Mapping {index} contains an invalid input event."
    return True, "Preset JSON structure looks valid."


def _walk_values(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_values(child, f"{path}[{index}]")
    else:
        yield path, value


def privacy_audit_profile_data(data) -> list[str]:
    """Find strings that look like local identity/path leakage.

    Preset files normally contain only input definitions and output symbols, so
    a filesystem path or local account name is suspicious enough to block a
    public export until the user reviews it.
    """
    issues: list[str] = []
    home = str(Path.home())
    username = getpass.getuser()
    hostname = socket.gethostname()

    path_patterns = (
        re.compile(r"/(?:home|Users)/[^/\s]+/"),
        re.compile(r"/run/user/\d+/"),
        re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\"),
        re.compile(r"file://", re.IGNORECASE),
    )

    for where, value in _walk_values(data):
        if not isinstance(value, str):
            continue
        if home and home in value:
            issues.append(f"{where}: contains the current home-directory path")
        if username and len(username) >= 3 and re.search(rf"(?<![A-Za-z0-9_]){re.escape(username)}(?![A-Za-z0-9_])", value):
            issues.append(f"{where}: contains the current account name")
        if hostname and len(hostname) >= 3 and re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(hostname)}(?![A-Za-z0-9_.-])", value):
            issues.append(f"{where}: contains the current hostname")
        for pattern in path_patterns:
            if pattern.search(value):
                issues.append(f"{where}: contains a local-looking filesystem location")
                break
    return sorted(set(issues))


def sanitize_profile_data(data, strip_origin_hash=True):
    sanitized = deepcopy(data)
    stripped = 0

    def clean(value):
        nonlocal stripped
        if isinstance(value, dict):
            if strip_origin_hash and "origin_hash" in value:
                value.pop("origin_hash", None)
                stripped += 1
            for child in list(value.values()):
                clean(child)
        elif isinstance(value, list):
            for child in value:
                clean(child)

    clean(sanitized)
    issues = privacy_audit_profile_data(sanitized)
    return sanitized, stripped, issues


def detect_linux_family() -> tuple[str, str]:
    """Return (family, display_name) using /etc/os-release without exposing host data."""
    data = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key] = value.strip().strip('"')
    except OSError:
        return "unknown", "Unknown Linux"

    ident = data.get("ID", "").lower()
    like = data.get("ID_LIKE", "").lower().split()
    candidates = [ident, *like]
    pretty = data.get("PRETTY_NAME") or ident or "Unknown Linux"

    if any(x in candidates for x in ("arch", "cachyos", "manjaro", "endeavouros")):
        return "arch", pretty
    if any(x in candidates for x in ("debian", "ubuntu", "linuxmint", "pop")):
        return "debian", pretty
    if any(x in candidates for x in ("fedora", "rhel")):
        return "fedora", pretty
    if ident == "void" or "void" in candidates:
        return "void", pretty
    return "unknown", pretty


def dependency_helper_path() -> Path | None:
    candidates = [
        Path(__file__).resolve().with_name("setup_dependencies.sh"),
        Path.home() / ".local" / "share" / "solopaw-profile-switcher" / "setup_dependencies.sh",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


# -----------------------------
# Input Remapper core
# -----------------------------

class SwitcherCore:
    def __init__(self):
        self.cfg = load_app_config()

    @property
    def device(self):
        return self.cfg.get("device", DEFAULT_DEVICE)

    @property
    def profile_dir(self):
        return REMAPPER_ROOT / "presets" / self.device

    @property
    def stream_mode(self):
        return bool(self.cfg.get("stream_mode", True))

    def set_stream_mode(self, value: bool):
        self.cfg["stream_mode"] = bool(value)
        self.save()

    def save(self):
        save_json_atomic(APP_CONFIG_FILE, self.cfg)

    def profiles(self):
        if not self.profile_dir.is_dir():
            return []
        return sorted(p.stem for p in self.profile_dir.glob("*.json") if p.is_file())

    def exists(self, profile):
        return bool(profile) and (self.profile_dir / f"{profile}.json").is_file()

    def common_name(self, profile):
        if not profile:
            return "—"
        return self.cfg["common_names"].get(profile) or friendly_name(profile)

    def set_common_name(self, profile, name):
        if not profile:
            return
        name = name.strip()
        if name:
            self.cfg["common_names"][profile] = name
        else:
            self.cfg["common_names"].pop(profile, None)
        self.save()

    def service_active(self):
        if not command_exists("systemctl"):
            return False
        return subprocess.run(
            ["systemctl", "is-active", "--quiet", "input-remapper"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0

    def service_enabled(self):
        if not command_exists("systemctl"):
            return False
        return subprocess.run(
            ["systemctl", "is-enabled", "--quiet", "input-remapper"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0

    def hello(self):
        if not command_exists("input-remapper-control"):
            return False, "Input Remapper is not installed or input-remapper-control is not in PATH."
        try:
            proc = subprocess.run(
                ["input-remapper-control", "--command", "hello"],
                text=True,
                capture_output=True,
                timeout=8,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, "Input Remapper service handshake timed out."
        return (
            (True, "Input Remapper service answered.")
            if proc.returncode == 0
            else (False, "Input Remapper service did not answer.")
        )

    def activate(self, profile):
        if not self.exists(profile):
            return False, "The selected profile file is missing."
        ok, msg = self.hello()
        if not ok:
            return False, msg
        try:
            proc = subprocess.run(
                [
                    "input-remapper-control", "--command", "start",
                    "--device", self.device, "--preset", profile,
                ],
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, "Input Remapper profile switch timed out."
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            suffix = f" ({detail[-1]})" if detail else ""
            return False, "Input Remapper rejected the profile switch" + suffix
        self.cfg["last_active_profile"] = profile
        self.save()
        return True, f"Activated {self.common_name(profile)}"

    def detect_active_profile(self):
        # Never display the journal; only extract the final preset filename.
        if command_exists("journalctl"):
            try:
                proc = subprocess.run(
                    ["journalctl", "-u", "input-remapper", "-b", "--no-pager", "-n", "600"],
                    text=True,
                    capture_output=True,
                    timeout=8,
                    check=False,
                )
                if proc.returncode == 0:
                    found = re.findall(r'Loading preset from ".*?/([^"/]+)\.json"', proc.stdout)
                    if found:
                        return found[-1], "journal"
            except subprocess.TimeoutExpired:
                pass
        return self.cfg.get("last_active_profile", ""), "app"

    def remapper_config(self):
        return load_json(REMAPPER_ROOT / "config.json", {"version": "2.2.1", "autoload": {}})

    def autoload_profile(self):
        return self.remapper_config().get("autoload", {}).get(self.device, "")

    def set_autoload(self, profile):
        if not self.exists(profile):
            return False, "The selected profile file is missing.", None
        cfg_file = REMAPPER_ROOT / "config.json"
        cfg = self.remapper_config()
        cfg.setdefault("autoload", {})
        backup = None
        if cfg_file.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = cfg_file.with_name(f"config.json.switcher-backup-{stamp}")
            shutil.copy2(cfg_file, backup)
        cfg["autoload"][self.device] = profile
        save_json_atomic(cfg_file, cfg)
        return True, f"Auto-reload set to {self.common_name(profile)}", backup

    def set_slot(self, index, profile, label=None):
        if index not in (0, 1, 2):
            return
        if profile and not self.exists(profile):
            raise ValueError("Selected profile does not exist.")
        slot = self.cfg["slots"][index]
        slot["profile"] = profile
        slot["label"] = (label or "").strip() or (
            self.common_name(profile) if profile else f"Preset {index + 1}"
        )
        self.save()

    def slot(self, index):
        return self.cfg["slots"][index]

    def open_profile_folder(self):
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        if command_exists("xdg-open"):
            subprocess.Popen(
                ["xdg-open", str(self.profile_dir)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        return False

    def restart_service(self):
        if not command_exists("pkexec"):
            return False, "pkexec is unavailable."
        try:
            proc = subprocess.run(
                ["pkexec", "systemctl", "restart", "input-remapper"],
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, "Service restart timed out."
        if proc.returncode == 0:
            time.sleep(1.5)
            return True, "Input Remapper restarted."
        return False, "Service restart was cancelled or failed."

    def public_export(self, profile: str, destination: Path):
        source = self.profile_dir / f"{profile}.json"
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"Could not read profile JSON: {exc}", 0

        valid, message = validate_profile_data(data)
        if not valid:
            return False, message, 0

        sanitized, stripped, issues = sanitize_profile_data(data, strip_origin_hash=True)
        if issues:
            return False, "Public export blocked by privacy audit:\n" + "\n".join(issues), stripped

        save_json_atomic(destination, sanitized)
        return True, f"Public-safe copy exported. Removed {stripped} origin_hash field(s).", stripped

    def import_profile(self, source: Path, target_stem: str):
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"Could not read profile JSON: {exc}", None
        valid, message = validate_profile_data(data)
        if not valid:
            return False, message, None

        safe_stem = re.sub(r"[^A-Za-z0-9._+()\[\] -]+", "_", target_stem).strip(" .")
        if not safe_stem:
            return False, "The profile filename is empty after safety filtering.", None

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        destination = self.profile_dir / f"{safe_stem}.json"
        backup = None
        if destination.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = destination.with_name(f"{destination.name}.backup-{stamp}")
            shutil.copy2(destination, backup)
        save_json_atomic(destination, data)
        return True, f"Imported profile {safe_stem}", backup


# -----------------------------
# GUI
# -----------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.core = SwitcherCore()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1230x870")
        self.minsize(1020, 620)
        self.selected_profile = ""

        self.status_message = tk.StringVar(value="Ready")
        self.active_name_var = tk.StringVar(value="—")
        self.active_file_var = tk.StringVar(value="—")
        self.autoload_name_var = tk.StringVar(value="—")
        self.autoload_file_var = tk.StringVar(value="—")
        self.service_var = tk.StringVar(value="Checking…")
        self.selected_common_var = tk.StringVar()
        self.selected_file_var = tk.StringVar()
        self.stream_mode_var = tk.BooleanVar(value=self.core.stream_mode)

        self._build()
        self.refresh_all()

    def _build(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self, padding=(12, 10))
        top.grid(row=0, column=0, sticky="ew")
        for column in range(3):
            top.columnconfigure(column, weight=1)

        for index in range(3):
            frame = ttk.LabelFrame(top, text=f"Quick Preset {index + 1}", padding=8)
            frame.grid(row=0, column=index, padx=5, sticky="ew")
            frame.columnconfigure(0, weight=1)
            button = ttk.Button(
                frame,
                text=f"Preset {index + 1}",
                command=lambda idx=index: self.activate_slot(idx),
            )
            button.grid(row=0, column=0, sticky="ew")
            setattr(self, f"slot_button_{index}", button)
            ttk.Button(
                frame,
                text="Edit",
                width=8,
                command=lambda idx=index: self.edit_slot(idx),
            ).grid(row=0, column=1, padx=(6, 0))

        banner = ttk.Frame(self, padding=(12, 0, 12, 8))
        banner.grid(row=1, column=0, sticky="ew")
        banner.columnconfigure(1, weight=1)
        ttk.Label(
            banner,
            text="STREAM-SAFE VIEW",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            banner,
            text="No home path, username, hostname, or raw journal is shown in the main UI.",
        ).grid(row=0, column=1, padx=(12, 0), sticky="w")
        ttk.Checkbutton(
            banner,
            text="Stream Mode — hide filenames",
            variable=self.stream_mode_var,
            command=self.toggle_stream_mode,
        ).grid(row=0, column=2, padx=(8, 8))
        ttk.Button(banner, text="Refresh", command=self.refresh_all).grid(row=0, column=3)

        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 10))

        left = ttk.Frame(body, padding=8)
        body.add(left, weight=3)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        ttk.Label(
            left,
            text="Available Input Remapper Profiles",
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        tree_frame = ttk.Frame(left)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("common", "file"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("common", text="Common Name")
        self.tree.heading("file", text="Profile Filename")
        self.tree.column("common", width=260, minwidth=180)
        self.tree.column("file", width=390, minwidth=100)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda _event: self.activate_selected())

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        selected = ttk.LabelFrame(left, text="Selected Profile", padding=8)
        selected.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        selected.columnconfigure(1, weight=1)
        ttk.Label(selected, text="Common name:").grid(row=0, column=0, sticky="w")
        ttk.Entry(selected, textvariable=self.selected_common_var).grid(
            row=0, column=1, sticky="ew", padx=(8, 4)
        )
        ttk.Button(selected, text="Save Common Name", command=self.save_common_name).grid(
            row=0, column=2
        )
        ttk.Label(selected, text="Filename:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(selected, textvariable=self.selected_file_var, state="readonly").grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=(6, 0)
        )

        slot_row = ttk.Frame(left)
        slot_row.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(slot_row, text="Assign selected to quick preset:").pack(side="left")
        for index in range(3):
            ttk.Button(
                slot_row,
                text=str(index + 1),
                width=4,
                command=lambda idx=index: self.assign_selected_slot(idx),
            ).pack(side="left", padx=(6, 0))

        right = ttk.Frame(body, padding=8)
        body.add(right, weight=2)
        right.columnconfigure(0, weight=1)

        ttk.Label(
            right,
            text="Current State",
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")

        active = ttk.LabelFrame(right, text="Active Now", padding=10)
        active.grid(row=1, column=0, sticky="ew", pady=(8, 6))
        active.columnconfigure(0, weight=1)
        ttk.Label(active, textvariable=self.active_name_var, font=("TkDefaultFont", 12, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(active, textvariable=self.active_file_var).grid(row=1, column=0, sticky="w", pady=(3, 0))

        autoload = ttk.LabelFrame(right, text="Auto-Reload / Input Remapper Autoload", padding=10)
        autoload.grid(row=2, column=0, sticky="ew", pady=6)
        autoload.columnconfigure(0, weight=1)
        ttk.Label(autoload, textvariable=self.autoload_name_var, font=("TkDefaultFont", 12, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(autoload, textvariable=self.autoload_file_var).grid(
            row=1, column=0, sticky="w", pady=(3, 0)
        )

        actions = ttk.LabelFrame(right, text="Selected Profile Actions", padding=10)
        actions.grid(row=3, column=0, sticky="ew", pady=6)
        actions.columnconfigure((0, 1), weight=1)
        ttk.Button(actions, text="Activate Selected Now", command=self.activate_selected).grid(
            row=0, column=0, padx=(0, 3), sticky="ew"
        )
        ttk.Button(actions, text="Set Auto-Reload", command=self.set_autoload_selected).grid(
            row=0, column=1, padx=(3, 0), sticky="ew"
        )
        ttk.Button(actions, text="Active + Auto-Reload", command=self.activate_and_autoload).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )
        ttk.Button(actions, text="Export Public-Safe Copy (off-stream)", command=self.export_selected).grid(
            row=2, column=0, sticky="ew", pady=(6, 0), padx=(0, 3)
        )
        ttk.Button(actions, text="Import Profile (off-stream)", command=self.import_profile).grid(
            row=2, column=1, sticky="ew", pady=(6, 0), padx=(3, 0)
        )
        ttk.Button(actions, text="Open Profile Folder (off-stream)", command=self.open_folder).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )

        service = ttk.LabelFrame(right, text="Input Remapper Service", padding=10)
        service.grid(row=4, column=0, sticky="ew", pady=6)
        service.columnconfigure(0, weight=1)
        ttk.Label(service, textvariable=self.service_var).grid(row=0, column=0, sticky="w")
        ttk.Button(service, text="Service Doctor", command=self.show_doctor).grid(
            row=1, column=0, sticky="ew", pady=(8, 0)
        )
        ttk.Button(service, text="Install / Repair Dependencies…", command=self.launch_dependency_helper).grid(
            row=2, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Button(service, text="Restart Input Remapper…", command=self.restart_service).grid(
            row=3, column=0, sticky="ew", pady=(6, 0)
        )

        notes = ttk.LabelFrame(right, text="Streamer Notes", padding=10)
        notes.grid(row=5, column=0, sticky="ew", pady=6)
        ttk.Label(
            notes,
            justify="left",
            wraplength=380,
            text=(
                "Stream Mode hides profile filenames and keeps the main view to common names/status. "
                "File dialogs and the profile-folder button can reveal local paths, so those controls are marked off-stream."
            ),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(self, textvariable=self.status_message, anchor="w", padding=(12, 6)).grid(
            row=3, column=0, sticky="ew"
        )

    def _display_filename(self, profile: str, suffix=""):
        if self.core.stream_mode:
            return "Filename hidden in Stream Mode" + suffix
        return (profile or "—") + suffix

    def refresh_all(self):
        keep = self.selected_profile
        for item in self.tree.get_children():
            self.tree.delete(item)

        profiles = self.core.profiles()
        for profile in profiles:
            shown = "Hidden in Stream Mode" if self.core.stream_mode else profile
            self.tree.insert("", "end", iid=profile, values=(self.core.common_name(profile), shown))

        if keep in profiles:
            self.tree.selection_set(keep)
            self.tree.see(keep)
        elif profiles:
            self.tree.selection_set(profiles[0])

        self.refresh_slots()
        self.refresh_status()
        self.on_select()

    def refresh_slots(self):
        for index in range(3):
            slot = self.core.slot(index)
            profile = slot.get("profile", "")
            label = slot.get("label") or f"Preset {index + 1}"
            button = getattr(self, f"slot_button_{index}")
            if profile and self.core.exists(profile):
                button.configure(text=label, state="normal")
            elif profile:
                button.configure(text=f"{label} (missing)", state="disabled")
            else:
                button.configure(text=f"Preset {index + 1} — empty", state="disabled")

    def refresh_status(self):
        active, source = self.core.detect_active_profile()
        if self.core.service_active():
            self.service_var.set(
                "Active · system service enabled"
                if self.core.service_enabled()
                else "Active · system service not enabled"
            )
        else:
            self.service_var.set("Inactive")

        if active:
            self.active_name_var.set(self.core.common_name(active))
            self.active_file_var.set(self._display_filename(active, f" · detected via {source}"))
        else:
            self.active_name_var.set("No active profile detected")
            self.active_file_var.set("—")

        auto = self.core.autoload_profile()
        if auto:
            self.autoload_name_var.set(self.core.common_name(auto))
            suffix = " · FILE MISSING" if not self.core.exists(auto) else ""
            self.autoload_file_var.set(self._display_filename(auto, suffix))
        else:
            self.autoload_name_var.set("No auto-reload profile configured")
            self.autoload_file_var.set("—")

    def on_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            self.selected_profile = ""
            self.selected_common_var.set("")
            self.selected_file_var.set("")
            return
        self.selected_profile = selection[0]
        self.selected_common_var.set(self.core.common_name(self.selected_profile))
        self.selected_file_var.set(
            "Hidden in Stream Mode" if self.core.stream_mode else self.selected_profile
        )

    def toggle_stream_mode(self):
        self.core.set_stream_mode(self.stream_mode_var.get())
        self.refresh_all()
        self.status_message.set(
            "Stream Mode enabled — filenames hidden."
            if self.core.stream_mode
            else "Stream Mode disabled — filenames visible; filesystem paths are still hidden."
        )

    def activate_selected(self):
        if not self.selected_profile:
            messagebox.showinfo(APP_NAME, "Select a profile first.")
            return
        ok, msg = self.core.activate(self.selected_profile)
        self.status_message.set(msg)
        if not ok:
            messagebox.showerror(APP_NAME, msg)
        self.refresh_status()

    def set_autoload_selected(self):
        if not self.selected_profile:
            messagebox.showinfo(APP_NAME, "Select a profile first.")
            return
        ok, msg, backup = self.core.set_autoload(self.selected_profile)
        self.status_message.set(msg)
        if ok:
            note = msg + ("\n\nA backup of the previous Input Remapper config was created." if backup else "")
            messagebox.showinfo(APP_NAME, note)
        else:
            messagebox.showerror(APP_NAME, msg)
        self.refresh_status()

    def activate_and_autoload(self):
        if not self.selected_profile:
            messagebox.showinfo(APP_NAME, "Select a profile first.")
            return
        ok, msg = self.core.activate(self.selected_profile)
        if not ok:
            messagebox.showerror(APP_NAME, msg)
            return
        ok2, msg2, _backup = self.core.set_autoload(self.selected_profile)
        if not ok2:
            messagebox.showwarning(APP_NAME, f"Activated, but auto-reload failed:\n{msg2}")
        self.status_message.set(f"{msg}; {msg2}")
        self.refresh_status()

    def activate_slot(self, index):
        profile = self.core.slot(index).get("profile", "")
        if not profile or not self.core.exists(profile):
            messagebox.showerror(APP_NAME, "That quick preset is empty or missing.")
            return
        ok, msg = self.core.activate(profile)
        self.status_message.set(msg)
        if not ok:
            messagebox.showerror(APP_NAME, msg)
        self.refresh_status()

    def edit_slot(self, index):
        slot = self.core.slot(index)
        profiles = self.core.profiles()
        win = tk.Toplevel(self)
        win.title(f"Edit Quick Preset {index + 1}")
        win.transient(self)
        win.grab_set()
        win.resizable(False, False)

        profile_var = tk.StringVar(value=slot.get("profile", ""))
        label_var = tk.StringVar(value=slot.get("label", f"Preset {index + 1}"))
        frame = ttk.Frame(win, padding=14)
        frame.grid()
        ttk.Label(frame, text="Profile:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            frame,
            textvariable=profile_var,
            values=[""] + profiles,
            width=58,
            state="readonly",
        ).grid(row=0, column=1, padx=(8, 0), sticky="ew")
        ttk.Label(frame, text="Button label:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=label_var, width=44).grid(
            row=1, column=1, padx=(8, 0), pady=(8, 0), sticky="ew"
        )

        def save_slot():
            try:
                self.core.set_slot(index, profile_var.get().strip(), label_var.get().strip())
            except ValueError as exc:
                messagebox.showerror(APP_NAME, str(exc), parent=win)
                return
            win.destroy()
            self.refresh_slots()
            self.status_message.set(f"Quick Preset {index + 1} updated.")

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Clear", command=lambda: profile_var.set("")).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Save", command=save_slot).pack(side="left")

    def assign_selected_slot(self, index):
        if not self.selected_profile:
            messagebox.showinfo(APP_NAME, "Select a profile first.")
            return
        label = simpledialog.askstring(
            APP_NAME,
            f"Quick Preset {index + 1} button label:",
            initialvalue=self.core.common_name(self.selected_profile),
            parent=self,
        )
        if label is None:
            return
        self.core.set_slot(index, self.selected_profile, label)
        self.refresh_slots()
        self.status_message.set(f"Assigned selected profile to Quick Preset {index + 1}.")

    def save_common_name(self):
        if self.selected_profile:
            self.core.set_common_name(self.selected_profile, self.selected_common_var.get())
            self.refresh_all()
            self.status_message.set("Common name saved locally.")

    def export_selected(self):
        if not self.selected_profile:
            messagebox.showinfo(APP_NAME, "Select a profile first.")
            return
        destination = filedialog.asksaveasfilename(
            parent=self,
            title="Export public-safe Input Remapper profile",
            initialfile=f"{self.selected_profile}.json",
            defaultextension=".json",
            filetypes=[("Input Remapper JSON", "*.json"), ("All files", "*")],
        )
        if not destination:
            return
        ok, msg, _stripped = self.core.public_export(self.selected_profile, Path(destination))
        self.status_message.set(msg.splitlines()[0])
        if ok:
            messagebox.showinfo(
                APP_NAME,
                msg + "\n\nThe exported file contains the mapping only — no common-name config, autoload config, username, or home path.",
            )
        else:
            messagebox.showerror(APP_NAME, msg)

    def import_profile(self):
        source_name = filedialog.askopenfilename(
            parent=self,
            title="Import Input Remapper profile",
            filetypes=[("Input Remapper JSON", "*.json"), ("All files", "*")],
        )
        if not source_name:
            return
        source = Path(source_name)
        target = simpledialog.askstring(
            APP_NAME,
            "Profile filename (without .json):",
            initialvalue=source.stem,
            parent=self,
        )
        if target is None:
            return
        ok, msg, backup = self.core.import_profile(source, target)
        self.status_message.set(msg)
        if ok:
            extra = "\n\nAn older file with the same name was backed up first." if backup else ""
            messagebox.showinfo(APP_NAME, msg + extra)
            self.refresh_all()
        else:
            messagebox.showerror(APP_NAME, msg)

    def open_folder(self):
        if not self.core.open_profile_folder():
            messagebox.showerror(APP_NAME, "Could not find xdg-open.")

    def restart_service(self):
        if not messagebox.askyesno(
            APP_NAME,
            "Restart Input Remapper now?\n\nThis may show an authorization prompt and briefly stop remapping.",
        ):
            return
        ok, msg = self.core.restart_service()
        messagebox.showinfo(APP_NAME, msg) if ok else messagebox.showerror(APP_NAME, msg)
        self.refresh_status()

    def launch_dependency_helper(self):
        helper = dependency_helper_path()
        if helper is None:
            messagebox.showerror(
                APP_NAME,
                "The dependency helper is not installed beside the application. See README.md for the official Input Remapper installation commands.",
            )
            return

        terminal_commands = []
        if command_exists("konsole"):
            terminal_commands.append(["konsole", "-e", "bash", str(helper)])
        if command_exists("x-terminal-emulator"):
            terminal_commands.append(["x-terminal-emulator", "-e", "bash", str(helper)])
        if command_exists("gnome-terminal"):
            terminal_commands.append(["gnome-terminal", "--", "bash", str(helper)])
        if command_exists("xfce4-terminal"):
            terminal_commands.append(["xfce4-terminal", "-e", f"bash {shlex_quote(str(helper))}"])
        if command_exists("xterm"):
            terminal_commands.append(["xterm", "-e", "bash", str(helper)])

        for command in terminal_commands:
            try:
                subprocess.Popen(command)
                self.status_message.set("Dependency helper opened in a terminal.")
                return
            except OSError:
                continue

        messagebox.showinfo(
            APP_NAME,
            "No supported terminal launcher was found. Run setup_dependencies.sh from the project folder.",
        )

    def show_doctor(self):
        hello_ok, _ = self.core.hello()
        active, source = self.core.detect_active_profile()
        auto = self.core.autoload_profile()
        family, pretty = detect_linux_family()
        lines = [
            f"Linux family: {family} ({pretty})",
            f"Input Remapper command: {'FOUND' if command_exists('input-remapper-control') else 'MISSING'}",
            f"System service: {'ACTIVE' if self.core.service_active() else 'INACTIVE'}",
            f"Service enabled: {'YES' if self.core.service_enabled() else 'NO'}",
            f"Service handshake: {'PASS' if hello_ok else 'FAIL'}",
            f"Profiles visible: {len(self.core.profiles())}",
            f"Active detection: {self.core.common_name(active) if active else 'none'} ({source})",
            f"Auto-reload: {self.core.common_name(auto) if auto else 'none'}",
            "",
            "Privacy: no home path, username, hostname, or raw journal text is displayed here.",
            "If Input Remapper is missing, use Install / Repair Dependencies… or setup_dependencies.sh.",
        ]
        messagebox.showinfo("Service Doctor", "\n".join(lines))


def shlex_quote(text: str) -> str:
    # Small POSIX shell quote helper to avoid importing a larger module solely
    # for the xfce4-terminal fallback.
    return "'" + text.replace("'", "'\\''") + "'"


def main():
    if "--version" in sys.argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    if "--privacy-audit-selftest" in sys.argv:
        sample = [{"input_combination": [{"type": 1, "code": 1}], "target_uinput": "keyboard", "output_symbol": "f"}]
        assert not privacy_audit_profile_data(sample)
        sanitized, stripped, issues = sanitize_profile_data(sample)
        assert sanitized == sample and stripped == 0 and not issues
        print("privacy self-test PASS")
        return 0
    if "--smoke-test" in sys.argv:
        app = App()
        app.update_idletasks()
        app.destroy()
        print("GUI smoke PASS")
        return 0
    App().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
