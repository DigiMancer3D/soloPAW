#!/usr/bin/env python3
from __future__ import annotations

import getpass
import json
import re
import socket
import sys
from pathlib import Path

TEXT_SUFFIXES = {".py", ".md", ".txt", ".sh", ".json", ".desktop", ".yml", ".yaml", ".toml", ".ini"}
GENERIC_PATTERNS = [
    (re.compile(r"/home/([A-Za-z0-9._-]+)/"), "absolute Linux home path"),
    (re.compile(r"/Users/([A-Za-z0-9._-]+)/"), "absolute macOS home path"),
    (re.compile(r"[A-Za-z]:\\\\Users\\\\([A-Za-z0-9._-]+)\\\\"), "absolute Windows user path"),
    (re.compile(r"/run/user/(\d+)/"), "runtime user path"),
]
SECRET_PATTERNS = [
    (re.compile(r"(?i)(token|api[_-]?key|secret|password)\s*[:=]\s*['\"][^'\"]{8,}"), "possible embedded secret"),
]
PLACEHOLDER_NAMES = {"example", "user", "username", "person", "name", "someone", "test", "demo"}


def scan_text(text: str, rel: str):
    issues = []
    for pattern, label in GENERIC_PATTERNS:
        for match in pattern.finditer(text):
            captured = match.group(1) if match.lastindex else ""
            if captured.lower() in PLACEHOLDER_NAMES:
                continue
            issues.append(f"{rel}: {label}: {match.group(0)[:120]}")
    for pattern, label in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            issues.append(f"{rel}: {label}: {match.group(0)[:120]}")
    return issues


def scan_json_profile(path: Path, rel: str):
    issues = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return issues

    def walk(v, where="$"):
        if isinstance(v, dict):
            if "origin_hash" in v:
                issues.append(f"{rel}:{where}: origin_hash present in public JSON")
            for k, child in v.items():
                walk(child, f"{where}.{k}")
        elif isinstance(v, list):
            for i, child in enumerate(v):
                walk(child, f"{where}[{i}]")

    if "profiles/public" in rel.replace("\\", "/"):
        walk(data)
    return issues


def main(argv):
    target = Path(argv[1] if len(argv) > 1 else ".").resolve()
    if not target.exists():
        print(f"ERROR: not found: {target}", file=sys.stderr)
        return 2

    files = [target] if target.is_file() else [p for p in target.rglob("*") if p.is_file()]
    issues = []
    checked = 0
    current_home = str(Path.home())
    current_user = getpass.getuser()
    current_host = socket.gethostname()

    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        checked += 1
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = str(path.relative_to(target.parent if target.is_file() else target))
        issues.extend(scan_text(text, rel))
        if current_home and current_home in text:
            issues.append(f"{rel}: contains current home path")
        if current_user not in {"root", "oai"} and len(current_user) >= 3 and re.search(rf"(?<![A-Za-z0-9_]){re.escape(current_user)}(?![A-Za-z0-9_])", text):
            issues.append(f"{rel}: contains current username")
        if current_host and len(current_host) >= 3 and re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(current_host)}(?![A-Za-z0-9_.-])", text):
            issues.append(f"{rel}: contains current hostname")
        if path.suffix.lower() == ".json":
            issues.extend(scan_json_profile(path, rel))

    if issues:
        print("PRIVACY AUDIT FAIL")
        for issue in sorted(set(issues)):
            print(" -", issue)
        return 1

    print(f"PRIVACY AUDIT PASS — {checked} text files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
