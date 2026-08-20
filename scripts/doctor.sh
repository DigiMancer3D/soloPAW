#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
pass=0
fail=0
ok(){ printf 'PASS: %s\n' "$1"; pass=$((pass+1)); }
bad(){ printf 'FAIL: %s\n' "$1"; fail=$((fail+1)); }

echo "soloPAW public repository doctor"
echo "Root: <REPOSITORY_ROOT>"
echo
for path in README.md apps/profile-switcher apps/controller-map-studio profiles/cyberpunk2077 profiles/megabonk docs; do
  if [[ -e "$path" ]]; then ok "present: $path"; else bad "missing: $path"; fi
done
if python3 -m py_compile apps/profile-switcher/solopaw_profile_switcher.py; then ok "Profile Switcher Python compile"; else bad "Profile Switcher Python compile"; fi
if (cd apps/profile-switcher && python3 -m unittest discover -s tests -v); then ok "Profile Switcher tests"; else bad "Profile Switcher tests"; fi
if (cd apps/profile-switcher && python3 tools/privacy_audit.py .); then ok "Profile Switcher privacy audit"; else bad "Profile Switcher privacy audit"; fi
if (cd apps/controller-map-studio && bash ./verify_release.sh); then ok "Controller Map Studio release verifier"; else bad "Controller Map Studio release verifier"; fi

if python3 - <<'PY'
from pathlib import Path
import json, hashlib, re
root=Path('.')
cp=root/'profiles/cyberpunk2077/soloPAW-Cyberpunk2077-v2.8-JDirect-ScanH-QuickW.json'
mb=root/'profiles/megabonk/soloPAW-Megabonk-v1.1-DirectKeys-Esc.json'
sw=root/'apps/profile-switcher/profiles/public'
for p in (cp,mb,sw/cp.name,sw/mb.name):
    data=json.loads(p.read_text())
    assert isinstance(data,list) and data
    text=p.read_text()
    assert 'origin_hash' not in text
    assert not re.search(r'/home/[^/\s]+/', text)
assert hashlib.sha256(cp.read_bytes()).digest()==hashlib.sha256((sw/cp.name).read_bytes()).digest()
assert hashlib.sha256(mb.read_bytes()).digest()==hashlib.sha256((sw/mb.name).read_bytes()).digest()
print('public profiles valid, sanitized, synchronized')
PY
then ok "Public profile validation/synchronization"; else bad "Public profile validation/synchronization"; fi

if grep -RInE --exclude-dir=.git --exclude='*.png' --exclude='SOURCE_FILE_SHA256SUMS.txt' --exclude='doctor.sh' --exclude='test_core.py' \
  '(/home/[A-Za-z0-9._-]+/|mobile-stone|d_3d_d|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)' . > /tmp/solopaw_privacy_hits.txt; then
  echo "Potential private-value hits:"; cat /tmp/solopaw_privacy_hits.txt; bad "Repository privacy/secret scan"
else ok "Repository privacy/secret scan"; fi
rm -f /tmp/solopaw_privacy_hits.txt

echo
echo "PASS checks: $pass"
echo "FAIL checks: $fail"
if (( fail > 0 )); then echo "OVERALL: FAIL"; exit 1; fi
echo "OVERALL: PASS"
