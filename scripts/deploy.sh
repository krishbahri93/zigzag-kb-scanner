#!/usr/bin/env bash
# deploy.sh — the ONLY way code reaches the server (see AGENTS.md invariants). Run as root:
#   sudo /opt/pinescan/scripts/deploy.sh              deploy latest origin/main
#   sudo /opt/pinescan/scripts/deploy.sh --rollback   return to the last good commit
#
# Flow: remember current commit -> update to origin/main -> reinstall deps only if
# pyproject.toml changed -> restart web -> smoke test -> on failure, automatic rollback.
set -euo pipefail
APP_DIR="/opt/pinescan"
APP_USER="pinescan"
cd "$APP_DIR"

[ "$(id -u)" -eq 0 ] || { echo "ERROR: run with sudo."; exit 1; }

as_app() { sudo -u "$APP_USER" "$@"; }

restart_and_smoke() {
    systemctl restart pinescan-web
    sleep 4
    as_app "$APP_DIR/venv/bin/python" "$APP_DIR/scripts/smoke_test.py"
}

install_if_needed() {   # $1 = old sha (deps reinstalled when pyproject.toml differs from it)
    if ! as_app git diff --quiet "$1" HEAD -- pyproject.toml; then
        echo "== pyproject.toml changed: reinstalling dependencies =="
        as_app "$APP_DIR/venv/bin/pip" install --quiet -e "$APP_DIR[india,app]"
    fi
}

MODE="${1:-deploy}"

if [ "$MODE" = "--rollback" ]; then
    [ -f .last_good ] || { echo "ERROR: no .last_good recorded — nothing to roll back to."; exit 1; }
    TARGET="$(cat .last_good)"
    echo "== rolling back to $TARGET =="
    OLD="$(as_app git rev-parse HEAD)"
    as_app git reset --hard "$TARGET"
    install_if_needed "$OLD"
    restart_and_smoke
    echo "== rollback OK: now at $(as_app git rev-parse --short HEAD) =="
    exit 0
fi

echo "== deploying origin/main =="
as_app git fetch origin
CURRENT="$(as_app git rev-parse HEAD)"
echo "$CURRENT" > .last_good && chown "$APP_USER:$APP_USER" .last_good
as_app git reset --hard origin/main
install_if_needed "$CURRENT"

if restart_and_smoke; then
    echo "== deploy OK: $CURRENT -> $(as_app git rev-parse --short HEAD) =="
else
    echo "== SMOKE TEST FAILED — rolling back automatically =="
    as_app git reset --hard "$CURRENT"
    install_if_needed "$(as_app git rev-parse HEAD)"
    systemctl restart pinescan-web
    echo "== rolled back to $CURRENT — investigate before redeploying =="
    exit 1
fi
