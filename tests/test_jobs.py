"""
Acceptance for the single-flight background-jobs helper (T4.3).

While a job runs, a second start() is a no-op (returns False), so two refreshes never race on the
cache; status transitions running -> idle with the job's final message.
"""
import time

from app.jobs import Jobs


def test_single_flight_and_status():
    jobs = Jobs()
    assert jobs.status() == {"running": False, "msg": "idle", "ok": None}

    release = {"go": False}

    def slow(progress):
        progress("step 1")
        while not release["go"]:
            time.sleep(0.005)
        return {"ok": True, "msg": "finished"}

    assert jobs.start(slow, label="working") is True
    time.sleep(0.05)
    assert jobs.status()["running"] is True
    assert jobs.start(slow) is False            # single-flight: second start refused while running

    release["go"] = True
    for _ in range(200):                        # wait for completion
        if not jobs.status()["running"]:
            break
        time.sleep(0.01)
    st = jobs.status()
    assert st == {"running": False, "msg": "finished", "ok": True}
