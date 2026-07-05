"""record_run.py JOB STARTED FINISHED EXITCODE — append a job outcome to data/status/last_runs.json.

Called by job_wrapper.sh after every scheduled run. Keeps the newest 50 records. Written
atomically (tmp + rename) so a crash mid-write can never corrupt the file. Standalone on
purpose: no imports from pinescan, so it works even if the package is broken.
"""
import json
import os
import sys

STATUS_FILE = os.path.join("data", "status", "last_runs.json")
KEEP = 50


def main():
    if len(sys.argv) != 5:
        sys.exit("usage: record_run.py JOB STARTED FINISHED EXITCODE")
    job, started, finished, exitcode = sys.argv[1:5]
    rc = int(exitcode)

    runs = []
    if os.path.exists(STATUS_FILE):
        try:
            runs = json.load(open(STATUS_FILE, encoding="utf-8"))
        except Exception:
            runs = []  # a corrupt file is replaced, never fatal

    runs.append({
        "job": job,
        "started": started,
        "finished": finished,
        "ok": rc == 0,
        "msg": "" if rc == 0 else f"exit code {rc} — see data/forward/logs/{job}.log",
    })
    runs = runs[-KEEP:]

    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=1)
    os.replace(tmp, STATUS_FILE)


if __name__ == "__main__":
    main()
