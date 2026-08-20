from __future__ import annotations

import base64
import csv
import io
import json
import os
import re
import uuid
import hashlib
import tempfile
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

APP_NAME = "soloPAW Controller Map Studio"
SCHEMA_NAME = "solopaw-controller-map"
SCHEMA_VERSION = 5
LAYERS = ("normal", "shift")
GESTURES = ("tap", "double", "hold")

DEFAULT_CANVAS = {"width": 1920, "height": 1080}
DEFAULT_THEME = {
    "background": "#090708",
    "panel_fill": "#11090b",
    "panel_border": "#e54843",
    "normal": "#ff5a52",
    "shift": "#8bd43f",
    "cyan": "#26d7ed",
    "text": "#f0ece8",
    "muted": "#a69c9c",
    "connector": "#2bd8ec",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_content() -> Dict[str, Dict[str, str]]:
    return {layer: {gesture: "" for gesture in GESTURES} for layer in LAYERS}


def new_project(name: str = "Untitled soloPAW Map") -> Dict[str, Any]:
    now = utc_now()
    return {
        "format": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "project": {
            "id": str(uuid.uuid4()),
            "name": name,
            "created": now,
            "updated": now,
            "revision": 1,
        },
        "canvas": deepcopy(DEFAULT_CANVAS),
        "theme": deepcopy(DEFAULT_THEME),
        "background": {
            "asset": None,
            "x": 0,
            "y": 0,
            "width": DEFAULT_CANVAS["width"],
            "height": DEFAULT_CANVAS["height"],
        },
        "controller": {
            "asset": None,
            "x": 650,
            "y": 280,
            "width": 760,
            "height": 540,
        },
        "cards": [],
        "bindings": [],
        "asset_library": [],
        "remapper_profile": {
            "name": "G502 Remapper",
            "device": "Logitech G502 HERO Gaming Mouse",
            "mappings": [],
            "dependencies": [],
            "change_log": [],
        },
        "metadata": {
            "notes": "",
            "source": "",
        },
    }


def _parse_prefixed_gestures(text: str) -> Dict[str, str]:
    """Migrate alpha.1 compact 'Tap:/Double:/Hold:' card text into fields."""
    result = {g: "" for g in GESTURES}
    current = "tap"
    buckets: Dict[str, List[str]] = {g: [] for g in GESTURES}
    for raw in (text or "").splitlines():
        m = re.match(r"^\s*(Tap|Double|Hold)\s*:?[ \t]*(.*)$", raw, flags=re.I)
        if m:
            current = m.group(1).lower()
            if m.group(2).strip():
                buckets[current].append(m.group(2).strip())
        else:
            buckets[current].append(raw)
    for g in GESTURES:
        result[g] = "\n".join(buckets[g]).strip()
    return result


def ensure_card_content(card: Dict[str, Any]) -> None:
    content = card.get("content")
    if not isinstance(content, dict):
        content = empty_content()
        title = str(card.get("title", ""))
        normal = str(card.get("normal", ""))
        shift = str(card.get("shift", ""))
        if title == "G9" and ("Tap" in normal or "Hold" in normal):
            content["normal"].update(_parse_prefixed_gestures(normal))
        else:
            content["normal"]["tap"] = normal
        if title in ("G8", "G9") and any(k in shift for k in ("Tap", "Double", "Hold")):
            content["shift"].update(_parse_prefixed_gestures(shift))
        else:
            content["shift"]["tap"] = shift
        card["content"] = content
    else:
        for layer in LAYERS:
            layer_data = content.setdefault(layer, {})
            for gesture in GESTURES:
                layer_data.setdefault(gesture, "")
    card.setdefault("icon_id", None)
    card.setdefault("icon_tint", "normal")
    # Keep typography independent from box geometry after the first migration.
    if "text_size" not in card:
        h = int(card.get("height", 220) or 220)
        card["text_size"] = max(10, min(16, int(h * .058)))
        card["_needs_text_fit"] = True
    try:
        card["text_size"] = max(8, min(34, int(card.get("text_size", 13))))
    except Exception:
        card["text_size"] = 13
    # Persist an authored connector midpoint.  Older projects recreate the old
    # elbow position once; moving the midpoint later keeps card-edge start auto.
    if "mid_x" not in card or "mid_y" not in card:
        x = int(card.get("x", 0)); y = int(card.get("y", 0))
        w = int(card.get("width", 320)); h = int(card.get("height", 210))
        ax = int(card.get("anchor_x", x + w // 2)); ay = int(card.get("anchor_y", y + h // 2))
        sx, sy = connector_start_point(card, ax, ay)
        card["mid_x"] = int(round(sx + (ax - sx) * .45))
        card["mid_y"] = int(round(sy))
    # Schema v5 has one authoritative routed connector per card.  Alpha.4
    # accidentally rendered this authored route *and* the pre-midpoint legacy
    # elbow.  The legacy route was never project data, so migration only needs
    # to mark the card as using the single routed connector.
    card["connector_mode"] = "routed-midpoint"
    sync_card_legacy_text(card)


def sync_card_legacy_text(card: Dict[str, Any]) -> None:
    """Keep alpha.1 readers useful without making the legacy fields authoritative."""
    content = card.get("content") or empty_content()
    card["normal"] = str(content.get("normal", {}).get("tap", ""))
    card["shift"] = str(content.get("shift", {}).get("tap", ""))


def ensure_binding_ids(data: Dict[str, Any]) -> None:
    seen = set()
    for row in data.setdefault("bindings", []):
        rid = str(row.get("id", "")).strip()
        if not rid or rid in seen:
            rid = str(uuid.uuid4())
            row["id"] = rid
        seen.add(rid)
        for key in ("section", "action", "primary", "secondary", "context", "notes"):
            row.setdefault(key, "")



# ---------- Remapper mapping intelligence ----------

_MACRO_FUNCTIONS = {
    "set", "hold", "if_eq", "if_tap", "key", "key_down", "key_up", "wait",
    "hold_keys", "repeat", "event", "mouse", "wheel", "sleep", "release",
}
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def ensure_remapper_metadata(data: Dict[str, Any]) -> None:
    profile = data.setdefault("remapper_profile", {})
    profile.setdefault("name", "G502 Remapper")
    profile.setdefault("device", "Logitech G502 HERO Gaming Mouse")
    mappings = profile.setdefault("mappings", [])
    seen = set()
    for mapping in mappings:
        mid = str(mapping.get("_studio_id", "")).strip()
        if not mid or mid in seen:
            mid = str(uuid.uuid4())
            mapping["_studio_id"] = mid
        seen.add(mid)
    deps = profile.setdefault("dependencies", [])
    dep_seen = set()
    valid_mapping_ids = {m.get("_studio_id") for m in mappings}
    cleaned = []
    for dep in deps:
        did = str(dep.get("id", "")).strip()
        if not did or did in dep_seen:
            did = str(uuid.uuid4())
            dep["id"] = did
        dep_seen.add(did)
        dep.setdefault("mapping_id", "")
        dep.setdefault("symbol", "")
        dep.setdefault("binding_ids", [])
        dep.setdefault("binding_field", "primary")
        dep.setdefault("label", "")
        dep.setdefault("accepted_expected", [])
        # Keep orphaned deps for diagnostics; do not silently delete user metadata.
        dep["binding_ids"] = [str(x) for x in dep.get("binding_ids", []) if x]
        cleaned.append(dep)
    profile["dependencies"] = cleaned
    profile.setdefault("change_log", [])


def find_mapping_by_id(data: Dict[str, Any], mapping_id: str) -> Optional[Dict[str, Any]]:
    ensure_remapper_metadata(data)
    for mapping in data.get("remapper_profile", {}).get("mappings", []):
        if mapping.get("_studio_id") == mapping_id:
            return mapping
    return None


def find_binding_by_id(data: Dict[str, Any], binding_id: str) -> Optional[Dict[str, Any]]:
    ensure_binding_ids(data)
    for row in data.get("bindings", []):
        if row.get("id") == binding_id:
            return row
    return None


def mapping_input_label(mapping: Dict[str, Any]) -> str:
    studio_label = str(mapping.get("_studio_label", "")).strip()
    parts = []
    for item in mapping.get("input_combination", []):
        t, c = item.get("type"), item.get("code")
        if t == 1:
            parts.append(f"KEY:{c}")
        elif t == 2:
            direction = "+" if float(item.get("analog_threshold", 0)) >= 0 else "-"
            parts.append(f"REL:{c}{direction}")
        else:
            parts.append(f"{t}:{c}")
    raw = " + ".join(parts) if parts else "(no input)"
    return f"{studio_label} [{raw}]" if studio_label else raw


def binding_key_to_symbol(value: str) -> str:
    """Convert a Cyberpunk-facing key label into Input Remapper macro syntax."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    # Parenthetical tap/hold qualifiers describe game semantics, not the key identity.
    raw = re.sub(r"\s*\((?:tap|hold)\)\s*$", "", raw, flags=re.I).strip()
    aliases = {
        "lmb": "BTN_LEFT", "left mouse": "BTN_LEFT", "left mouse button": "BTN_LEFT",
        "rmb": "BTN_RIGHT", "right mouse": "BTN_RIGHT", "right mouse button": "BTN_RIGHT",
        "mmb": "BTN_MIDDLE", "middle mouse": "BTN_MIDDLE", "middle mouse button": "BTN_MIDDLE",
        "right shift": "Shift_R", "left shift": "Shift_L",
        "left ctrl": "Control_L", "left control": "Control_L",
        "right ctrl": "Control_R", "right control": "Control_R",
        "caps lock": "Caps_Lock", "capslock": "Caps_Lock",
        "esc": "Escape", "escape": "Escape", "space": "space",
        "tab": "Tab", "enter": "Return", "return": "Return",
    }
    low = raw.casefold()
    if low in aliases:
        return aliases[low]
    if re.fullmatch(r"F\d{1,2}", raw, flags=re.I):
        return raw.upper()
    if len(raw) == 1 and raw.isalpha():
        return raw.lower()
    if len(raw) == 1 and raw.isdigit():
        return raw
    # Arrow/wheel labels are intentionally left readable; not every one is emitted by macros.
    generic = {
        "up": "Up", "down": "Down", "left": "Left", "right": "Right",
        "wheel up": "Wheel_Up", "wheel down": "Wheel_Down",
    }
    return generic.get(low, raw.replace(" ", "_"))


def extract_macro_symbols(output_symbol: str) -> List[str]:
    """Return likely emitted key/button identifiers from an Input Remapper macro."""
    text = str(output_symbol or "")
    out: List[str] = []
    for match in _IDENTIFIER_RE.finditer(text):
        ident = match.group(0)
        if ident in _MACRO_FUNCTIONS or ident.startswith("soloPAW_"):
            continue
        if match.start() > 0 and text[match.start()-1] == "$":
            continue
        if ident not in out:
            out.append(ident)
    return out


def macro_contains_symbol(output_symbol: str, symbol: str) -> bool:
    if not symbol:
        return False
    return bool(re.search(r"(?<![A-Za-z0-9_])" + re.escape(symbol) + r"(?![A-Za-z0-9_])", str(output_symbol or "")))


def replace_macro_symbol(output_symbol: str, old: str, new: str) -> Tuple[str, int]:
    if not old or not new:
        return str(output_symbol or ""), 0
    pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(old) + r"(?![A-Za-z0-9_])")
    return pat.subn(new, str(output_symbol or ""))


def validate_macro_expression(text: str) -> Tuple[bool, str]:
    """Conservative editor-side validation; Input Remapper remains the runtime authority."""
    s = str(text or "").strip()
    if not s:
        return False, "Macro/output is empty"
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    for ch in s:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack.pop() != pairs[ch]:
                return False, "Unbalanced brackets/parentheses"
    if stack:
        return False, "Unbalanced brackets/parentheses"
    return True, "Structure looks balanced"


def describe_macro(output_symbol: str) -> List[str]:
    s = str(output_symbol or "")
    desc = []
    if "if_eq(" in s and "$soloPAW_shift" in s:
        desc.append("G-Shift conditional")
    if "if_tap(" in s:
        n = s.count("if_tap(")
        desc.append("tap/hold" if n == 1 else "tap/double/hold")
    waits = re.findall(r"wait\((\d+)\)", s)
    if waits:
        desc.append("timed hold: " + ", ".join(f"{w}ms" for w in waits))
    if "hold_keys(" in s:
        desc.append("physical-duration hold")
    if "set(soloPAW_shift" in s:
        desc.append("G-Shift state controller")
    symbols = extract_macro_symbols(s)
    if symbols:
        desc.append("symbols: " + ", ".join(symbols))
    return desc or ["direct output"]


def add_remapper_dependency(
    data: Dict[str, Any], mapping_id: str, symbol: str, binding_ids: Iterable[str],
    *, binding_field: str = "primary", label: str = ""
) -> Dict[str, Any]:
    ensure_remapper_metadata(data)
    if not find_mapping_by_id(data, mapping_id):
        raise ValueError("Unknown remapper mapping")
    binding_ids = [str(x) for x in binding_ids if x]
    if not binding_ids:
        raise ValueError("Dependency needs at least one binding")
    dep = {
        "id": str(uuid.uuid4()), "mapping_id": mapping_id, "symbol": str(symbol),
        "binding_ids": binding_ids, "binding_field": binding_field,
        "label": label or "Linked remapper key", "accepted_expected": [],
    }
    data["remapper_profile"]["dependencies"].append(dep)
    return dep


def dependency_state(data: Dict[str, Any], dep: Dict[str, Any]) -> Dict[str, Any]:
    mapping = find_mapping_by_id(data, str(dep.get("mapping_id", "")))
    rows = [find_binding_by_id(data, bid) for bid in dep.get("binding_ids", [])]
    rows = [r for r in rows if r]
    field = dep.get("binding_field", "primary")
    expected_pairs = []
    for row in rows:
        raw = str(row.get(field, ""))
        sym = binding_key_to_symbol(raw)
        if sym:
            expected_pairs.append((row, sym))
    expected_symbols = sorted({sym for _, sym in expected_pairs})
    current = str(dep.get("symbol", ""))
    macro = str(mapping.get("output_symbol", "")) if mapping else ""
    present = bool(mapping and macro_contains_symbol(macro, current))
    accepted = sorted(str(x) for x in dep.get("accepted_expected", []))
    if not mapping:
        status = "orphaned"
    elif not rows or not expected_symbols:
        status = "unresolved"
    elif len(expected_symbols) > 1:
        status = "conflict"
    elif not present:
        status = "missing"
    elif expected_symbols[0] == current:
        status = "ok"
    elif accepted == expected_symbols:
        status = "kept"
    else:
        status = "stale"
    return {
        "id": dep.get("id"), "status": status, "current": current,
        "expected": expected_symbols[0] if len(expected_symbols) == 1 else " / ".join(expected_symbols),
        "expected_symbols": expected_symbols, "mapping": mapping,
        "mapping_input": mapping_input_label(mapping) if mapping else "(missing mapping)",
        "rows": rows, "label": dep.get("label", ""), "present": present,
    }


def dependency_diagnostics(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    ensure_remapper_metadata(data)
    return [dependency_state(data, dep) for dep in data.get("remapper_profile", {}).get("dependencies", [])]


def dependency_counts(data: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in dependency_diagnostics(data):
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


def apply_dependency_update(data: Dict[str, Any], dependency_id: str) -> Dict[str, Any]:
    ensure_remapper_metadata(data)
    dep = next((d for d in data["remapper_profile"]["dependencies"] if d.get("id") == dependency_id), None)
    if not dep:
        raise ValueError("Unknown dependency")
    state = dependency_state(data, dep)
    if state["status"] not in ("stale", "kept"):
        raise ValueError(f"Dependency is not safely updatable ({state['status']})")
    if len(state["expected_symbols"]) != 1:
        raise ValueError("Linked bindings do not agree on one replacement key")
    mapping = state["mapping"]
    old, new = state["current"], state["expected_symbols"][0]
    updated, count = replace_macro_symbol(mapping.get("output_symbol", ""), old, new)
    if count < 1:
        raise ValueError(f"Macro no longer contains linked symbol {old}")
    before = mapping.get("output_symbol", "")
    mapping["output_symbol"] = updated
    dep["symbol"] = new
    dep["accepted_expected"] = []
    data["remapper_profile"].setdefault("change_log", []).append({
        "time": utc_now(), "dependency_id": dependency_id, "label": dep.get("label", ""),
        "old_symbol": old, "new_symbol": new, "before": before, "after": updated,
    })
    return dependency_state(data, dep)


def accept_dependency_current(data: Dict[str, Any], dependency_id: str) -> Dict[str, Any]:
    ensure_remapper_metadata(data)
    dep = next((d for d in data["remapper_profile"]["dependencies"] if d.get("id") == dependency_id), None)
    if not dep:
        raise ValueError("Unknown dependency")
    state = dependency_state(data, dep)
    dep["accepted_expected"] = list(state.get("expected_symbols", []))
    return dependency_state(data, dep)


def clean_remapper_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Studio-only metadata before Input Remapper JSON export."""
    return {k: deepcopy(v) for k, v in mapping.items() if not str(k).startswith("_studio_")}

def connector_start_point(card: Dict[str, Any], target_x: float, target_y: float) -> Tuple[int, int]:
    """Return the point on the card edge facing the connector midpoint."""
    x = float(card.get("x", 0)); y = float(card.get("y", 0))
    w = max(1.0, float(card.get("width", 320))); h = max(1.0, float(card.get("height", 210)))
    cx, cy = x + w / 2.0, y + h / 2.0
    dx, dy = float(target_x) - cx, float(target_y) - cy
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return int(round(x + w)), int(round(cy))
    tx = (w / 2.0) / abs(dx) if abs(dx) > 1e-9 else float("inf")
    ty = (h / 2.0) / abs(dy) if abs(dy) > 1e-9 else float("inf")
    t = min(tx, ty)
    return int(round(cx + dx * t)), int(round(cy + dy * t))


def sync_card_z_indices(data: Dict[str, Any]) -> None:
    for idx, card in enumerate(data.setdefault("cards", [])):
        card["z_index"] = idx


def ensure_extension(path: os.PathLike[str] | str, ext: str) -> Path:
    """Append an extension; never eat version suffixes such as name_v2.2."""
    p = Path(path)
    ext = ext if ext.startswith(".") else "." + ext
    if not str(p).lower().endswith(ext.lower()):
        p = Path(str(p) + ext)
    return p


def _card_font_sizes(card: Dict[str, Any]) -> Tuple[int, int, int]:
    body = max(8, min(34, int(card.get("text_size", 13))))
    title = max(14, min(46, body + 9))
    label = max(8, min(30, body - 2))
    return title, label, body


def card_required_size(data: Dict[str, Any], card: Dict[str, Any]) -> Tuple[int, int]:
    """Measure content using the independent card text size."""
    ensure_card_content(card)
    dummy = Image.new("RGB", (8, 8), "#000")
    draw = ImageDraw.Draw(dummy)
    title_sz, label_sz, body_sz = _card_font_sizes(card)
    title_f = _load_font(title_sz, bold=True)
    body_f = _load_font(body_sz)
    pad = 16
    icon_reserved = 54 if find_asset(data, card.get("icon_id")) else 0
    title = str(card.get("title", "Mapping"))
    required_w = max(130, draw.textbbox((0, 0), title, font=title_f)[2] + 2 * pad + icon_reserved)
    for _layer, _gesture, text in _card_sections(card, data):
        for raw in text.splitlines():
            for word in raw.split() or [""]:
                required_w = max(required_w, draw.textbbox((0, 0), word, font=body_f)[2] + 2 * pad)
    width = max(int(card.get("width", 320)), int(required_w))
    max_text_width = max(40, width - 2 * pad)
    yy = pad + title_sz + 10
    last_layer = None
    for layer, _gesture, text in _card_sections(card, data):
        if last_layer is not None and layer != last_layer:
            yy += 6
        yy += label_sz + 5
        yy += max(1, len(_wrap_text(draw, text, body_f, max_text_width))) * (body_sz + 5)
        last_layer = layer
    return int(width), int(max(90, yy + pad))


def ensure_card_fits_content(data: Dict[str, Any], card: Dict[str, Any]) -> Tuple[bool, bool]:
    """Grow only the right/bottom side if text no longer fits."""
    need_w, need_h = card_required_size(data, card)
    grew_w = need_w > int(card.get("width", 0))
    grew_h = need_h > int(card.get("height", 0))
    if grew_w: card["width"] = need_w
    if grew_h: card["height"] = need_h
    return grew_w, grew_h


def normalize_project(data: Dict[str, Any]) -> Dict[str, Any]:
    """Upgrade old projects in memory while preserving all existing data."""
    if data.get("format") != SCHEMA_NAME:
        raise ValueError(f"Not a {SCHEMA_NAME} project")
    version = int(data.get("schema_version", 0))
    if version > SCHEMA_VERSION:
        raise ValueError("Project schema is newer than this editor")
    data.setdefault("asset_library", [])
    data.setdefault("metadata", {})
    canvas = data.setdefault("canvas", deepcopy(DEFAULT_CANVAS))
    bg = data.setdefault("background", {})
    bg.setdefault("asset", None); bg.setdefault("x", 0); bg.setdefault("y", 0)
    bg.setdefault("width", int(canvas.get("width", DEFAULT_CANVAS["width"])))
    bg.setdefault("height", int(canvas.get("height", DEFAULT_CANVAS["height"])))
    for card in data.setdefault("cards", []):
        ensure_card_content(card)
    # Alpha.1-3 used dynamic line compression.  On the first schema-v4 migration,
    # choose the largest independent font size that still fits the existing box
    # so opening an older map does not suddenly clip its text or move its layout.
    for card in data.get("cards", []):
        if card.pop("_needs_text_fit", False):
            while int(card.get("text_size", 13)) > 8:
                need_w, need_h = card_required_size(data, card)
                if need_w <= int(card.get("width", 320)) and need_h <= int(card.get("height", 220)):
                    break
                card["text_size"] = int(card.get("text_size", 13)) - 1
    sync_card_z_indices(data)
    ensure_binding_ids(data)
    ensure_remapper_metadata(data)
    data["schema_version"] = SCHEMA_VERSION
    return data


def validate_project(data: Dict[str, Any]) -> None:
    normalize_project(data)
    for required in ("project", "canvas", "theme", "background", "controller", "cards", "bindings", "remapper_profile", "asset_library"):
        if required not in data:
            raise ValueError(f"Missing required field: {required}")


def load_project(path: os.PathLike[str] | str) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_project(data)
    return data


def save_project(path: os.PathLike[str] | str, data: Dict[str, Any], backup: bool = True) -> Path:
    path = ensure_extension(path, ".udata")
    validate_project(data)
    data["project"]["updated"] = utc_now()
    data["project"]["revision"] = int(data["project"].get("revision", 0)) + 1
    sync_card_z_indices(data)
    out = deepcopy(data)
    for card in out.get("cards", []):
        sync_card_legacy_text(card)
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        path.with_suffix(path.suffix + ".bak").write_bytes(path.read_bytes())
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def encode_asset(path: os.PathLike[str] | str) -> Dict[str, Any]:
    p = Path(path)
    raw = p.read_bytes()
    ext = p.suffix.lower().lstrip(".")
    media = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "svg": "image/svg+xml",
    }.get(ext, "application/octet-stream")
    return {
        "name": p.name,
        "media_type": media,
        "data_b64": base64.b64encode(raw).decode("ascii"),
    }


def decode_asset(asset: Optional[Dict[str, Any]]) -> Optional[bytes]:
    if not asset or not asset.get("data_b64"):
        return None
    return base64.b64decode(asset["data_b64"])


def add_asset(data: Dict[str, Any], path: os.PathLike[str] | str, *, asset_id: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:
    asset = encode_asset(path)
    asset["id"] = asset_id or str(uuid.uuid4())
    if name:
        asset["name"] = name
    library = data.setdefault("asset_library", [])
    library[:] = [a for a in library if a.get("id") != asset["id"]]
    library.append(asset)
    return asset


def find_asset(data: Dict[str, Any], asset_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not asset_id:
        return None
    for asset in data.get("asset_library", []):
        if asset.get("id") == asset_id:
            return asset
    return None


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates: List[str] = []
    if bold:
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_background(width: int, height: int, theme: Dict[str, str]) -> Image.Image:
    bg = Image.new("RGB", (width, height), theme.get("background", "#090708"))
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-width * .15, height * .05, width * .45, height * .95), fill=(120, 18, 22, 45))
    gd.ellipse((width * .55, -height * .15, width * 1.15, height * .65), fill=(100, 10, 18, 35))
    glow = glow.filter(ImageFilter.GaussianBlur(max(20, int(width * .025))))
    bg = Image.alpha_composite(bg.convert("RGBA"), glow)
    d = ImageDraw.Draw(bg)
    for y in range(0, height, 8):
        d.line((0, y, width, y), fill=(26, 9, 11, 255), width=1)
    for x in range(18, width, 86):
        d.line((x, 0, x, 10), fill=(18, 82, 90, 255), width=1)
    for y in range(20, height, 64):
        d.line((0, y, 12, y), fill=(82, 22, 24, 255), width=1)
    return bg


def asset_to_image(asset: Optional[Dict[str, Any]], size: Optional[Tuple[int, int]] = None) -> Optional[Image.Image]:
    raw = decode_asset(asset)
    if not raw:
        return None
    media = asset.get("media_type", "") if asset else ""
    if media == "image/svg+xml":
        try:
            import cairosvg  # type: ignore
            kwargs: Dict[str, Any] = {"bytestring": raw}
            if size:
                kwargs["output_width"], kwargs["output_height"] = size
            png = cairosvg.svg2png(**kwargs)
            im = Image.open(io.BytesIO(png)).convert("RGBA")
        except Exception:
            return None
    else:
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
    if size:
        im.thumbnail(size, Image.Resampling.LANCZOS)
    return im


# compatibility name used internally by alpha.1 code/extensions
_image_from_asset = asset_to_image


def tint_icon(im: Image.Image, color: str) -> Image.Image:
    im = im.convert("RGBA")
    alpha = im.getchannel("A")
    solid = Image.new("RGBA", im.size, color)
    solid.putalpha(alpha)
    return solid


def _draw_panel(draw: ImageDraw.ImageDraw, xy: Tuple[int, int, int, int], theme: Dict[str, str], selected: bool = False) -> None:
    x1, y1, x2, y2 = xy
    fill = theme.get("panel_fill", "#11090b")
    border = theme.get("cyan", "#26d7ed") if selected else theme.get("panel_border", "#e54843")
    draw.rounded_rectangle(xy, radius=12, fill=fill, outline=border, width=3)
    cut = 14
    draw.line((x1, y1 + cut, x1 + cut, y1), fill=border, width=3)
    draw.line((x2 - cut, y2, x2, y2 - cut), fill=border, width=3)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    out: List[str] = []
    for raw_line in text.splitlines() or [""]:
        if not raw_line:
            out.append("")
            continue
        words = raw_line.split()
        line = ""
        for word in words:
            candidate = word if not line else line + " " + word
            if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                line = candidate
            else:
                if line:
                    out.append(line)
                line = word
        out.append(line)
    return out


def _find_binding(data: Dict[str, Any], section: str, action: str) -> Optional[Dict[str, Any]]:
    section_l, action_l = section.strip().casefold(), action.strip().casefold()
    exact_action: List[Dict[str, Any]] = []
    for row in data.get("bindings", []):
        if str(row.get("action", "")).strip().casefold() == action_l:
            if not section_l or str(row.get("section", "")).strip().casefold() == section_l:
                return row
            exact_action.append(row)
    return exact_action[0] if len(exact_action) == 1 else None


_TOKEN_RE = re.compile(r"\{\{(key|secondary|action):([^{}]+)\}\}")


def resolve_binding_tokens(text: str, data: Dict[str, Any]) -> str:
    """Resolve {{key:Section::Action}} references at render/export time."""
    def repl(match: re.Match[str]) -> str:
        kind = match.group(1)
        target = match.group(2).strip()
        if "::" in target:
            section, action = target.split("::", 1)
        else:
            section, action = "", target
        row = _find_binding(data, section, action)
        if not row:
            return f"[UNLINKED: {target}]"
        if kind == "action":
            return str(row.get("action", ""))
        if kind == "secondary":
            return str(row.get("secondary", ""))
        return str(row.get("primary", ""))
    return _TOKEN_RE.sub(repl, text or "")


def make_binding_token(section: str, action: str, kind: str = "key") -> str:
    if kind not in ("key", "secondary", "action"):
        raise ValueError("Unsupported binding token kind")
    return "{{%s:%s::%s}}" % (kind, section, action)


def count_binding_links(data: Dict[str, Any]) -> int:
    count = 0
    for card in data.get("cards", []):
        ensure_card_content(card)
        for layer in LAYERS:
            for gesture in GESTURES:
                count += len(_TOKEN_RE.findall(str(card["content"][layer][gesture])))
    return count


def _card_sections(card: Dict[str, Any], data: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """Return (layer label, gesture label, resolved text) for nonempty card slots."""
    ensure_card_content(card)
    sections: List[Tuple[str, str, str]] = []
    for layer in LAYERS:
        populated = [(g, resolve_binding_tokens(card["content"][layer].get(g, ""), data)) for g in GESTURES]
        populated = [(g, t) for g, t in populated if t.strip()]
        for g, text in populated:
            sections.append((layer, g, text))
    return sections


def render_project(data: Dict[str, Any], selected_card_id: Optional[str] = None) -> Image.Image:
    validate_project(data)
    width = int(data["canvas"].get("width", 1920))
    height = int(data["canvas"].get("height", 1080))
    theme = {**DEFAULT_THEME, **data.get("theme", {})}
    img = make_background(width, height, theme)
    bg_cfg = data.get("background", {})
    if bg_cfg.get("asset"):
        bg_im = asset_to_image(bg_cfg.get("asset"))
        if bg_im:
            bw = max(1, int(bg_cfg.get("width", width))); bh = max(1, int(bg_cfg.get("height", height)))
            bg_im = bg_im.resize((bw, bh), Image.Resampling.LANCZOS)
            img.alpha_composite(bg_im, (int(bg_cfg.get("x", 0)), int(bg_cfg.get("y", 0))))
    draw = ImageDraw.Draw(img)

    title_font = _load_font(max(18, int(height * .035)), bold=True)
    sub_font = _load_font(max(12, int(height * .018)), bold=True)
    draw.text((42, 26), data["project"].get("name", "soloPAW Controller Map"), font=title_font, fill=theme["normal"])
    draw.text((44, 70), "WYSIWYG CONTROL MAP // .UDATA", font=sub_font, fill=theme["cyan"])

    ctrl = data.get("controller", {})
    controller = asset_to_image(ctrl.get("asset"), (int(ctrl.get("width", 760)), int(ctrl.get("height", 540))))
    if controller:
        cx, cy = int(ctrl.get("x", 650)), int(ctrl.get("y", 280))
        img.alpha_composite(controller, (cx, cy))

    # Connectors are drawn under cards. Midpoint and endpoint are authorable.
    for card in data.get("cards", []):
        ensure_card_content(card)
        ax = int(card.get("anchor_x", 0)); ay = int(card.get("anchor_y", 0))
        mx = int(card.get("mid_x", ax)); my = int(card.get("mid_y", ay))
        sx, sy = connector_start_point(card, mx, my)
        draw.line((sx, sy, mx, my, ax, ay), fill=theme["connector"], width=3)
        draw.ellipse((mx - 3, my - 3, mx + 3, my + 3), fill=theme["connector"])
        draw.ellipse((ax - 4, ay - 4, ax + 4, ay + 4), fill=theme["cyan"])

    for card in data.get("cards", []):
        ensure_card_content(card)
        x = int(card.get("x", 0)); y = int(card.get("y", 0)); w = int(card.get("width", 320)); h = int(card.get("height", 210))
        _draw_panel(draw, (x, y, x + w, y + h), theme, card.get("id") == selected_card_id)
        pad = 16
        title = str(card.get("title", "Mapping"))
        title_sz, label_sz, body_sz = _card_font_sizes(card)
        title_f = _load_font(title_sz, bold=True)
        label_f = _load_font(label_sz, bold=True)
        body_f = _load_font(body_sz)
        yy = y + pad
        icon_reserved = 0
        asset = find_asset(data, card.get("icon_id"))
        if asset:
            icon = asset_to_image(asset, (46, 46))
            if icon:
                tint = str(card.get("icon_tint", "normal"))
                if tint in theme:
                    icon = tint_icon(icon, theme[tint])
                img.alpha_composite(icon, (x + w - pad - icon.width, y + pad))
                draw = ImageDraw.Draw(img)
                icon_reserved = icon.width + 8
        draw.text((x + pad, yy), title, font=title_f, fill=theme["normal"])
        yy += title_sz + 10

        sections = _card_sections(card, data)
        first_layer = True
        last_layer = None
        layer_counts = {layer: sum(1 for l, _, _ in sections if l == layer) for layer in LAYERS}
        for layer, gesture, text in sections:
            if yy > y + h - 18:
                break
            if last_layer is not None and layer != last_layer:
                draw.line((x + pad, yy, x + w - pad, yy), fill=theme["panel_border"], width=1)
                yy += 5
            color = theme["normal"] if layer == "normal" else theme["shift"]
            layer_label = "NORMAL" if layer == "normal" else "G-SHIFT"
            if layer_counts[layer] > 1 or gesture != "tap":
                layer_label += " " + gesture.upper()
            draw.text((x + pad, yy), layer_label, font=label_f, fill=color)
            yy += label_sz + 5
            max_text_width = max(40, w - 2 * pad - (icon_reserved if first_layer else 0))
            for line in _wrap_text(draw, text, body_f, max_text_width):
                if yy > y + h - 16:
                    break
                draw.text((x + pad, yy), line, font=body_f, fill=theme["text"])
                yy += body_sz + 5
            last_layer = layer
            first_layer = False

    footer_f = _load_font(max(10, int(height * .014)), bold=True)
    draw.text((42, height - 34), "soloPAW // Single-Handed Mapping Studio", font=footer_f, fill=theme["cyan"])
    return img.convert("RGB")


def export_png(path: os.PathLike[str] | str, data: Dict[str, Any]) -> Path:
    path = ensure_extension(path, ".png")
    image = render_project(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")
    return path


def export_remapper(path: os.PathLike[str] | str, data: Dict[str, Any]) -> Path:
    validate_project(data)
    path = ensure_extension(path, ".json")
    mappings = [clean_remapper_mapping(m) for m in data.get("remapper_profile", {}).get("mappings", [])]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mappings, indent=4) + "\n", encoding="utf-8")
    return path


def export_binding_table(base_path: os.PathLike[str] | str, data: Dict[str, Any]) -> Tuple[Path, Path]:
    validate_project(data)
    base = Path(base_path)
    if str(base).lower().endswith(".json") or str(base).lower().endswith(".csv"):
        base = Path(str(base).rsplit(".", 1)[0])
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    rows = data.get("bindings", [])
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    fields = ["section", "action", "primary", "secondary", "context", "notes"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})
    return json_path, csv_path


def export_bundle(path: os.PathLike[str] | str, data: Dict[str, Any], *, project_source: Optional[os.PathLike[str] | str] = None) -> Path:
    """Export a portable regeneration bundle with manifest and SHA256 sums.

    The .udata inside the bundle is a snapshot of the in-memory project, so the
    bundle remains useful even when the current project was opened as a template.
    """
    validate_project(data)
    out = ensure_extension(path, ".zip")
    out.parent.mkdir(parents=True, exist_ok=True)
    stem = out.stem
    with tempfile.TemporaryDirectory(prefix="solopaw-bundle-") as td_raw:
        td = Path(td_raw)
        udata = save_project(td / f"{stem}.udata", deepcopy(data), backup=False)
        png = export_png(td / f"{stem}.png", data)
        rem = export_remapper(td / "G502 Remapper.json", data)
        bj, bc = export_binding_table(td / "Binding Table.json", data)
        files = [udata, png, rem, bj, bc]
        sums = {}
        for f in files:
            sums[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
        manifest = {
            "format": "solopaw-export-bundle",
            "version": 1,
            "created": utc_now(),
            "project": {
                "name": data.get("project", {}).get("name", ""),
                "id": data.get("project", {}).get("id", ""),
                "schema_version": data.get("schema_version"),
                "source_path": str(project_source) if project_source else "",
            },
            "files": [{"name": name, "sha256": digest} for name, digest in sums.items()],
        }
        mp = td / "manifest.json"
        mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        sums[mp.name] = hashlib.sha256(mp.read_bytes()).hexdigest()
        sp = td / "SHA256SUMS.txt"
        sp.write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(sums.items())), encoding="utf-8")
        files += [mp, sp]
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for f in files:
                zf.write(f, arcname=f.name)
    return out


def import_binding_table(path: os.PathLike[str] | str) -> List[Dict[str, str]]:
    p = Path(path)
    if p.suffix.lower() == ".json":
        rows = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(rows, dict):
            rows = rows.get("bindings", [])
        if not isinstance(rows, list):
            raise ValueError("Binding JSON must be a list or contain a bindings list")
        out = [dict(r) for r in rows]
    elif p.suffix.lower() == ".csv":
        with p.open("r", newline="", encoding="utf-8-sig") as f:
            out = [dict(r) for r in csv.DictReader(f)]
    else:
        raise ValueError("Binding import supports .json or .csv")
    # Preserve any imported IDs; callers can reconcile IDs with existing rows.
    temp = {"bindings": out}
    ensure_binding_ids(temp)
    return temp["bindings"]


def reconcile_binding_ids(existing: Iterable[Dict[str, Any]], incoming: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    old = {(str(r.get("section", "")).casefold(), str(r.get("action", "")).casefold()): r.get("id") for r in existing}
    rows: List[Dict[str, Any]] = []
    for raw in incoming:
        r = dict(raw)
        key = (str(r.get("section", "")).casefold(), str(r.get("action", "")).casefold())
        if old.get(key):
            r["id"] = old[key]
        rows.append(r)
    temp = {"bindings": rows}
    ensure_binding_ids(temp)
    return temp["bindings"]


def add_card(data: Dict[str, Any], title: str = "New Control", normal: str = "", shift: str = "", x: int = 80, y: int = 120, width: int = 320, height: int = 220, anchor_x: int = 960, anchor_y: int = 540) -> Dict[str, Any]:
    content = empty_content()
    content["normal"]["tap"] = normal
    content["shift"]["tap"] = shift
    card = {
        "id": str(uuid.uuid4()),
        "title": title,
        "normal": normal,
        "shift": shift,
        "content": content,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "anchor_x": anchor_x,
        "anchor_y": anchor_y,
        "mid_x": int((x + width + anchor_x) / 2),
        "mid_y": int(y + height / 2),
        "connector_mode": "routed-midpoint",
        "text_size": max(10, min(16, int(height * .058))),
        "icon_id": None,
        "icon_tint": "normal",
    }
    data.setdefault("cards", []).append(card)
    sync_card_z_indices(data)
    return card
