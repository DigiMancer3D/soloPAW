#!/usr/bin/env bash
set -euo pipefail
cat <<'EOF'
soloPAW setup

Profile Switcher:
  cd apps/profile-switcher && ./setup_dependencies.sh && ./install.sh

Controller Map Studio:
  cd apps/controller-map-studio && ./setup_cachyos.sh && ./verify_release.sh && ./install_desktop.sh

Verify repository:
  ./scripts/doctor.sh
EOF
