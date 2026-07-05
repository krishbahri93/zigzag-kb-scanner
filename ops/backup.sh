#!/usr/bin/env bash
# backup.sh — nightly snapshot of the SMALL, IRREPLACEABLE state (run as root via
# pinescan-backup.timer, 02:00 IST). The multi-GB price cache is deliberately excluded:
# it is re-downloadable from Dhan/Polygon at any time.
#
# What's saved: Dhan/Polygon secrets, dashboard logins, the forward-test (paper-money)
# history, job-run records. Kept 7 nights in /var/backups/pinescan (root-only).
# Restore: tar -xzf /var/backups/pinescan/<file> -C /opt/pinescan (then redo users.caddy).
# NOTE: local-only for now — protects against bad deploys/corruption, not server loss.
# Offsite (encrypted) copy is a planned follow-up once the forward history has real age.
set -euo pipefail
APP_DIR="/opt/pinescan"
DEST="/var/backups/pinescan"
STAMP="$(date +%F)"

mkdir -p "$DEST"
chmod 700 "$DEST"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/pinescan-$STAMP"
for f in .dhan_creds .polygon_key .healthchecks .telegram; do
    [ -f "$APP_DIR/$f" ] && cp -a "$APP_DIR/$f" "$TMP/pinescan-$STAMP/"
done
[ -d "$APP_DIR/data/forward" ] && cp -a "$APP_DIR/data/forward" "$TMP/pinescan-$STAMP/"
[ -d "$APP_DIR/data/status" ]  && cp -a "$APP_DIR/data/status"  "$TMP/pinescan-$STAMP/"
[ -f /etc/caddy/users.caddy ]  && cp -a /etc/caddy/users.caddy  "$TMP/pinescan-$STAMP/"

tar -czf "$DEST/pinescan-$STAMP.tgz" -C "$TMP" "pinescan-$STAMP"
chmod 600 "$DEST/pinescan-$STAMP.tgz"

# keep the newest 7
ls -1t "$DEST"/pinescan-*.tgz 2>/dev/null | tail -n +8 | xargs -r rm -f
echo "backup written: $DEST/pinescan-$STAMP.tgz ($(du -h "$DEST/pinescan-$STAMP.tgz" | cut -f1))"
