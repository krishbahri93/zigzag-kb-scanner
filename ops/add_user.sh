#!/usr/bin/env bash
# add_user.sh — create/update a dashboard login (or remove one). Run as root on the server.
#   sudo bash ops/add_user.sh <username>              -> generates a strong password, prints it
#   sudo bash ops/add_user.sh <username> <password>   -> uses the given password
#   sudo bash ops/add_user.sh --remove <username>     -> revokes that person's access
set -euo pipefail
USERS_FILE="/etc/caddy/users.caddy"

[ "$(id -u)" -eq 0 ] || { echo "ERROR: run with sudo."; exit 1; }
[ $# -ge 1 ] || { echo "usage: add_user.sh <username> [password] | --remove <username>"; exit 1; }
touch "$USERS_FILE"

if [ "$1" = "--remove" ]; then
    [ $# -eq 2 ] || { echo "usage: add_user.sh --remove <username>"; exit 1; }
    sed -i "/^$2 /d" "$USERS_FILE"
    systemctl reload caddy
    echo "removed login: $2"
    exit 0
fi

USERNAME="$1"
# bounded read first: piping /dev/urandom straight into head trips pipefail (SIGPIPE on tr)
PASSWORD="${2:-$(head -c 400 /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 20)}"
HASH="$(caddy hash-password --plaintext "$PASSWORD")"
sed -i "/^$USERNAME /d" "$USERS_FILE"          # replace if the user already exists
echo "$USERNAME $HASH" >> "$USERS_FILE"
systemctl reload caddy
echo "login ready — username: $USERNAME   password: $PASSWORD"
echo "(share it privately; re-run this script any time to change it)"
