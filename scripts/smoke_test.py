"""smoke_test.py — the deploy gate. Non-zero exit means "this deployment is broken" and
deploy.sh rolls back automatically.

HARD checks (fail the deploy):
  1. the pinescan package imports and the scanner registry is non-empty
  2. the web app answers on 127.0.0.1:8000 (/ and /status)
SOFT checks (warn only — normal on a brand-new server before keys/data exist):
  3. .dhan_creds present     4. India cache present     5. recent scheduled runs all OK
"""
import json
import os
import sys
import urllib.request

FAILURES = []


def hard(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(name)


def soft(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'warn'}  {name}" + (f"  ({detail})" if detail else ""))


def http_status(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "smoke-test"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def main():
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    print("smoke test:")

    # 1. package + registry
    try:
        import pinescan.scanners as scanners  # noqa: F401
        from pinescan.scanners.registry import list_scanners
        names = list_scanners()  # sorted list of registered scanner names
        hard("package imports, scanners registered", len(names) > 0, ", ".join(names))
    except Exception as e:
        hard("package imports, scanners registered", False, repr(e))

    # 2. web app answers
    for path in ("/", "/status"):
        code = http_status(f"http://127.0.0.1:8000{path}")
        hard(f"web app answers {path}", code is not None and code < 500,
             f"HTTP {code}" if code else "no response")

    # 3-5. soft checks
    soft(".dhan_creds present", os.path.exists(".dhan_creds"),
         "" if os.path.exists(".dhan_creds") else "enter Dhan secrets on the Settings page")
    cache = os.path.join("data", "cache", "india")
    has_cache = os.path.isdir(cache) and len(os.listdir(cache)) > 0
    soft("India price cache present", has_cache, "" if has_cache else "run a data refresh")
    runs_file = os.path.join("data", "status", "last_runs.json")
    if os.path.exists(runs_file):
        runs = json.load(open(runs_file, encoding="utf-8"))
        latest = {}
        for r in runs:
            latest[r["job"]] = r
        bad = [j for j, r in latest.items() if not r["ok"]]
        soft("latest scheduled runs all OK", not bad, "failing: " + ", ".join(bad) if bad else "")
    else:
        soft("latest scheduled runs all OK", True, "no runs recorded yet")

    if FAILURES:
        print(f"SMOKE TEST FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("smoke test passed")


if __name__ == "__main__":
    main()
