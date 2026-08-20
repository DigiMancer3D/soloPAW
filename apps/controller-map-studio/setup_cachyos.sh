#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
missing=[]
for mod in ('tkinter','PIL'):
    try: __import__(mod)
    except Exception: missing.append(mod)
try: __import__('cairosvg')
except Exception: pass
if missing:
    print('Missing Python modules:', ', '.join(missing))
    print('On CachyOS/Arch, install Python/Tk/Pillow using your preferred package manager, then rerun.')
    raise SystemExit(1)
print('Core GUI dependencies found.')
try:
    import cairosvg
    print('SVG support: enabled (cairosvg found)')
except Exception:
    print('SVG support: optional dependency not found; PNG/JPEG still work.')
PY
