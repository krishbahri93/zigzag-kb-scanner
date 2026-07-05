#!/usr/bin/env bash
# provision.sh — take a blank Ubuntu 24.04 server to a fully-working scanner host. Idempotent:
# safe to re-run any time; it only changes what's missing. Run as root:
#
#   curl -fsSL https://raw.githubusercontent.com/krishbahri93/zigzag-kb-scanner/main/ops/provision.sh | sudo bash -s -- [branch]
#
# What it sets up (see AGENTS.md for the full path map):
#   /opt/pinescan            git checkout (user: pinescan), venv, data/, secrets
#   pinescan-web.service     uvicorn on 127.0.0.1:8000, Restart=always
#   pinescan-token.timer     08:30 IST daily  — mint fresh Dhan token (headless TOTP)
#   pinescan-close-india.timer  15:45 IST Mon-Fri — refresh data + forward test
#   Caddy                    HTTPS for kwmscanner.com + per-user basic auth (ops/add_user.sh)
#   UFW 22/80/443, journald cap, logrotate, unattended security upgrades
set -euo pipefail

BRANCH="${1:-main}"
REPO_URL="https://github.com/krishbahri93/zigzag-kb-scanner.git"
APP_DIR="/opt/pinescan"
APP_USER="pinescan"

[ "$(id -u)" -eq 0 ] || { echo "ERROR: run as root (sudo)."; exit 1; }
echo "== provision: branch=$BRANCH =="

echo "== timezone: Asia/Kolkata =="
timedatectl set-timezone Asia/Kolkata

echo "== apt packages =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -yq git python3-venv python3-pip curl ufw logrotate \
    unattended-upgrades age debian-keyring debian-archive-keyring apt-transport-https

echo "== caddy (web server with automatic HTTPS) =="
if ! command -v caddy >/dev/null 2>&1; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -q && apt-get install -yq caddy
fi

echo "== app user + checkout =="
id -u "$APP_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$APP_USER"
mkdir -p "$APP_DIR" && chown "$APP_USER:$APP_USER" "$APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
    sudo -u "$APP_USER" git clone -b "$BRANCH" "$REPO_URL" "$APP_DIR"
else
    sudo -u "$APP_USER" git -C "$APP_DIR" fetch origin
    sudo -u "$APP_USER" git -C "$APP_DIR" checkout "$BRANCH"
    sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard "origin/$BRANCH"
fi

echo "== python venv + install =="
# run from APP_DIR: pip scans the CWD, and the ubuntu home dir is unreadable to the app user
cd "$APP_DIR"
[ -x "$APP_DIR/venv/bin/python" ] || sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet -e "$APP_DIR[india,app]"

echo "== runtime directories =="
sudo -u "$APP_USER" mkdir -p "$APP_DIR/data/status" "$APP_DIR/data/locks" "$APP_DIR/data/forward/logs"
chmod +x "$APP_DIR"/scripts/*.sh "$APP_DIR"/ops/*.sh 2>/dev/null || true

echo "== systemd units =="
cp "$APP_DIR"/ops/systemd/*.service "$APP_DIR"/ops/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now pinescan-web.service
systemctl enable --now pinescan-token.timer pinescan-close-india.timer \
    pinescan-scan-india.timer pinescan-close-us.timer pinescan-backup.timer

echo "== dashboard logins =="
touch /etc/caddy/users.caddy && chmod 640 /etc/caddy/users.caddy && chgrp caddy /etc/caddy/users.caddy
if ! grep -q . /etc/caddy/users.caddy; then
    # bounded read first: piping /dev/urandom straight into head trips pipefail (SIGPIPE on tr)
    BOOTSTRAP_PW="$(head -c 400 /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 20)"
    HASH="$(caddy hash-password --plaintext "$BOOTSTRAP_PW")"
    echo "krish $HASH" >> /etc/caddy/users.caddy
    echo ""
    echo "  ============================================================"
    echo "  FIRST LOGIN CREATED  —  username: krish"
    echo "  password: $BOOTSTRAP_PW"
    echo "  (save it in a password manager; add more people or change"
    echo "   passwords any time with: sudo bash ops/add_user.sh <name>)"
    echo "  ============================================================"
    echo ""
fi

echo "== caddy config (HTTPS + auth for kwmscanner.com) =="
cp "$APP_DIR/ops/Caddyfile" /etc/caddy/Caddyfile
systemctl enable caddy >/dev/null 2>&1 || true
systemctl reload caddy 2>/dev/null || systemctl restart caddy

echo "== firewall =="
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp  >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

echo "== log hygiene =="
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=200M\n' > /etc/systemd/journald.conf.d/pinescan.conf
systemctl restart systemd-journald
cat > /etc/logrotate.d/pinescan <<'EOF'
/opt/pinescan/data/forward/logs/*.log {
    weekly
    rotate 8
    compress
    missingok
    notifempty
    copytruncate
}
EOF

echo "== automatic security updates =="
dpkg-reconfigure -f noninteractive unattended-upgrades >/dev/null 2>&1 || true

echo ""
echo "== provision complete =="
echo "   web:    systemctl status pinescan-web"
echo "   timers: systemctl list-timers 'pinescan-*'"
echo "   health: bash $APP_DIR/ops/status.sh"
echo "   NOTE: https://kwmscanner.com goes live once the domain's DNS points here."
