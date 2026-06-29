"""
jobs.py — a tiny single-flight background-job runner for the app.
=================================================================

ROLE IN THE FLOW
  Long actions (the data Refresh) can take minutes, so they run in ONE background thread: the HTTP
  request returns instantly and the page polls `/status` for progress. SINGLE-FLIGHT — while a job
  runs, `start()` returns False (a second Refresh click is a no-op), so two jobs never run at once
  and never race on the cache. This is the only mutable state in the app, and it lives in memory
  (a crash just loses the in-flight job; the cache itself is crash-safe via io_safe).
"""
import threading


class Jobs:
    """At most one background job at a time, with a pollable status dict."""

    def __init__(self):
        self._lock = threading.Lock()
        self._status = {"running": False, "msg": "idle", "ok": None}

    def start(self, fn, label="working"):
        """Run `fn(progress_cb)` in a background thread if none is running. Returns True if started,
        False if a job is already in flight. `fn` receives a callback to post progress messages and
        may return a {"ok", "msg"} dict."""
        with self._lock:
            if self._status["running"]:
                return False
            self._status = {"running": True, "msg": label, "ok": None}

        def _run():
            try:
                r = fn(self._set_msg)
                ok = bool(r.get("ok", True)) if isinstance(r, dict) else True
                msg = (r.get("msg") if isinstance(r, dict) else None) or "Done."
            except Exception as e:
                ok, msg = False, f"Error: {str(e)[:160]}"
            with self._lock:
                self._status = {"running": False, "msg": msg, "ok": ok}

        threading.Thread(target=_run, daemon=True).start()
        return True

    def _set_msg(self, msg):
        with self._lock:
            if self._status["running"]:
                self._status["msg"] = msg

    def status(self):
        with self._lock:
            return dict(self._status)
