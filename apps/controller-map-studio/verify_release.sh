#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export PYTHONDONTWRITEBYTECODE=1

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
pass() { printf 'PASS: %s\n' "$*"; }

[[ -f RELEASE_MANIFEST.json ]] || fail "RELEASE_MANIFEST.json missing"
[[ -f SOURCE_FILE_SHA256SUMS.txt ]] || fail "SOURCE_FILE_SHA256SUMS.txt missing"
sha256sum -c SOURCE_FILE_SHA256SUMS.txt >/dev/null || fail "release file checksum mismatch"
pass "release file checksums"

[[ ! -d tests ]] || fail "development tests directory present in runtime release"
[[ ! -d docs ]] || fail "development docs directory present in runtime release"
[[ ! -e ROADMAP.md ]] || fail "development roadmap present in runtime release"
[[ ! -e run_selftests.sh ]] || fail "development self-test runner present in runtime release"
if find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*~' -o -name '*.bak' -o -name '*.tmp' \) -print -quit | grep -q .; then
  fail "temporary/development bytecode or backup file present"
fi
if find . -type d -name '__pycache__' -print -quit | grep -q .; then
  fail "__pycache__ directory present"
fi
pass "runtime tree excludes development-only material"

python3 -m compileall -q main.py solopaw_studio || fail "Python source compilation"
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
pass "Python source compilation"

python3 - <<'PY'
from pathlib import Path
import json
from solopaw_studio import __version__
from solopaw_studio.core import SCHEMA_VERSION, load_project, validate_project
root=Path('.')
assert __version__ == '0.1.0-rc.1', __version__
manifest=json.loads((root/'RELEASE_MANIFEST.json').read_text())
assert manifest['version'] == __version__
assert manifest['schema_version'] == SCHEMA_VERSION == 5
p=load_project(root/'defaults'/'soloPAW_Cyberpunk2077_v2.0_Core.udata')
validate_project(p)
assert p['schema_version'] == 5
assert len(p.get('cards', [])) >= 10
assert len(p.get('bindings', [])) >= 60
assert len(p.get('remapper_profile', {}).get('mappings', [])) == 11
print('PASS: version, release manifest, and default schema-v5 project')
PY

for f in launch.sh setup_cachyos.sh install_desktop.sh desktop_check.sh uninstall_desktop.sh verify_release.sh; do
  [[ -x "$f" ]] || fail "$f is not executable"
done
[[ -f desktop/solopaw-controller-map-studio.desktop.in ]] || fail "desktop entry template missing"
[[ -f desktop/solopaw-controller-map-studio.xml ]] || fail "MIME definition missing"
[[ -f assets/solopaw-controller-map-studio.png ]] || fail "PNG application icon missing"
[[ -f assets/solopaw-controller-map-studio.svg ]] || fail "SVG application icon missing"
pass "desktop release surface"

printf '\nRELEASE SEAL PASS — soloPAW Controller Map Studio v0.1.0-rc.1\n'
