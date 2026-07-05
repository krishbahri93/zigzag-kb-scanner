#!/usr/bin/env bash
# status.sh — one-screen health check. Run on the server: bash ops/status.sh
cd /opt/pinescan 2>/dev/null || cd "$(dirname "$0")/.."

echo "== services =="
systemctl is-active pinescan-web  | sed 's/^/  pinescan-web:  /'
systemctl is-active caddy         | sed 's/^/  caddy:         /'

echo "== timers (next runs) =="
systemctl list-timers 'pinescan-*' --no-pager | sed 's/^/  /'

echo "== last job runs (data/status/last_runs.json) =="
if [ -f data/status/last_runs.json ]; then
    venv/bin/python - <<'EOF'
import json
runs = json.load(open("data/status/last_runs.json"))
latest = {}
for r in runs:
    latest[r["job"]] = r
for job, r in sorted(latest.items()):
    print(f'  {job:12s} {"OK " if r["ok"] else "FAIL"} finished {r["finished"]} ({r.get("msg","")})')
EOF
else
    echo "  (no runs recorded yet)"
fi

echo "== disk / memory =="
df -h / | tail -1 | awk '{print "  disk: " $3 " used of " $2 " (" $5 ")"}'
free -m | awk '/^Mem:/ {print "  mem:  " $3 " MB used of " $2 " MB"}'
