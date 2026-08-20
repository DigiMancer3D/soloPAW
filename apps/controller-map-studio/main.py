#!/usr/bin/env python3
from pathlib import Path
import argparse

from solopaw_studio import __version__
from solopaw_studio.app import run

ROOT = Path(__file__).resolve().parent
DEFAULT = ROOT / "defaults" / "soloPAW_Cyberpunk2077_v2.0_Core.udata"


def parse_args():
    parser = argparse.ArgumentParser(description="soloPAW Controller Map Studio")
    parser.add_argument("project", nargs="?", help="Optional .udata project to open")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.version:
        print(f"soloPAW Controller Map Studio {__version__}")
        return 0
    initial = Path(args.project).expanduser() if args.project else None
    if initial is not None and not initial.exists():
        raise SystemExit(f"Project does not exist: {initial}")
    run(DEFAULT if DEFAULT.exists() else None, initial_project=initial)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
