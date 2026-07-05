#!/usr/bin/env bash
# job_wrapper.sh <job-name> <command...> — run a scheduled job with the house rules:
#   - single-flight: skip silently if the same job is already running (flock)
#   - log to data/forward/logs/<job>.log
#   - record the outcome in data/status/last_runs.json (the dashboard + smoke test read it)
#   - ping healthchecks.io if a URL for this job exists in .healthchecks (JOB=url lines, optional)
set -uo pipefail
cd /opt/pinescan
JOB="$1"; shift

mkdir -p data/locks data/status data/forward/logs
exec 9>"data/locks/${JOB}.lock"
flock -n 9 || { echo "$(date -Is) ${JOB}: already running, skipped" >> "data/forward/logs/${JOB}.log"; exit 0; }

HC_URL=""
[ -f .healthchecks ] && HC_URL="$(grep -E "^${JOB}=" .healthchecks | head -1 | cut -d= -f2- || true)"
[ -n "$HC_URL" ] && curl -fsS -m 10 --retry 3 "${HC_URL}/start" >/dev/null 2>&1 || true

STARTED="$(date -Is)"
echo "=== $STARTED ${JOB}: start ===" >> "data/forward/logs/${JOB}.log"
"$@" >> "data/forward/logs/${JOB}.log" 2>&1
RC=$?
FINISHED="$(date -Is)"
echo "=== $FINISHED ${JOB}: exit $RC ===" >> "data/forward/logs/${JOB}.log"

venv/bin/python scripts/record_run.py "$JOB" "$STARTED" "$FINISHED" "$RC" || true

if [ -n "$HC_URL" ]; then
    if [ "$RC" -eq 0 ]; then curl -fsS -m 10 --retry 3 "$HC_URL" >/dev/null 2>&1 || true
    else curl -fsS -m 10 --retry 3 "${HC_URL}/fail" >/dev/null 2>&1 || true; fi
fi
exit "$RC"
