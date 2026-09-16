"""
refresh_dhan_token.py — mint a fresh 24h Dhan access token headlessly, and rewrite .dhan_creds.
===============================================================================================

Dhan access tokens expire every 24h (SEBI retail-algo rules, since 2025-10-01), so an always-on
India forward-tester MUST refresh daily with no human in the loop. The dhanhq SDK's `DhanLogin`
mints a token from a PIN + a time-based one-time code (TOTP), so given three LONG-LIVED secrets we
never touch the daily token by hand again.

SECRETS (in the git-ignored .dhan_creds, KEY=VALUE lines):
    DHAN_CLIENT_ID=1101507477
    DHAN_PIN=......            # account MPIN
    DHAN_TOTP_SECRET=......    # base32 TOTP seed, captured ONCE when you enable TOTP on Dhan

WHAT IT DOES
    1. Read the three secrets (env wins over .dhan_creds, like india.ensure_dhan_creds).
    2. token = DhanLogin(client_id).generate_token(pin, pyotp.TOTP(secret).now()).
    3. Rewrite the DHAN_ACCESS_TOKEN= line in .dhan_creds (keeping the other lines), so the existing
       india.ensure_dhan_creds() picks it up unchanged — zero change to the scanner/backtester.

ONE-TIME HUMAN STEP (before this can run): enable TOTP on the Dhan account (Profile -> DhanHQ
Trading API / Access / 2FA -> enable TOTP), and save the base32 secret into .dhan_creds.

USAGE (schedule pre-market, ~08:30 IST, via setup_schedule.ps1):
    python scripts/refresh_dhan_token.py
"""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

CREDS_FILE = ".dhan_creds"
_REQUIRED = ("DHAN_CLIENT_ID", "DHAN_PIN", "DHAN_TOTP_SECRET")


def _read_creds(path):
    """Parse a KEY=VALUE creds file into a dict (blank / '#' lines ignored). {} if absent."""
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def _extract_token(resp):
    """Pull the access token out of generate_token's response. The SDK doesn't document the exact
    shape, so try the known spellings, both top-level and nested under 'data'."""
    if not isinstance(resp, dict):
        return None
    candidates = [resp, resp.get("data") if isinstance(resp.get("data"), dict) else {}]
    for d in candidates:
        for k in ("accessToken", "access_token", "token"):
            if d.get(k):
                return d[k]
    return None


def main():
    import datetime as dt
    force = "--force" in sys.argv
    creds = _read_creds(CREDS_FILE)

    # Idempotent by design: the timer fires SEVERAL times across the morning (08:15,
    # 08:35, … 12:30) so one flaky 08:30 mint can't kill the whole trading day — the
    # 2026-09-15/16 outage, where a single "Invalid TOTP" at peak load left a dead
    # token for 3 sessions. Once a mint succeeds, DHAN_TOKEN_DATE records today's date
    # and every later fire that day is an instant no-op (0 API calls). `--force`
    # overrides, for a manual re-mint.
    today = str(dt.date.today())
    if not force and creds.get("DHAN_TOKEN_DATE") == today and creds.get("DHAN_ACCESS_TOKEN"):
        print(f"  token already minted today ({today}); nothing to do.")
        return

    vals = {k: os.environ.get(k, creds.get(k)) for k in _REQUIRED}   # env wins over file
    missing = [k for k in _REQUIRED if not vals[k]]
    if missing:
        sys.exit(f"Missing {', '.join(missing)} — put them in {CREDS_FILE} (enable TOTP on Dhan "
                 "once to get DHAN_TOTP_SECRET). See this script's header.")

    try:
        import pyotp
    except Exception:
        sys.exit("Missing dependency pyotp. Install: pip install pyotp")
    try:
        from dhanhq import DhanLogin
    except Exception:
        from dhanhq.auth import DhanLogin

    totp = pyotp.TOTP(vals["DHAN_TOTP_SECRET"])
    login = DhanLogin(vals["DHAN_CLIENT_ID"])
    token, last = None, None
    # TOTP codes live ~30s and Dhan rejects boundary/replayed codes ("Invalid TOTP") — seen in the
    # wild with a synced clock. It ALSO returns "Invalid TOTP" when its auth endpoint is overloaded
    # at the 08:30 cron peak even for a valid code (proven: same secret mints instantly off-peak).
    # So we try 6 fresh codes across ~3 min — long enough to ride out a transient load spike — and
    # the retry-timer's later fires cover a sustained one.
    for attempt in range(1, 7):
        resp = login.generate_token(vals["DHAN_PIN"], totp.now())
        token = _extract_token(resp)
        if token:
            break
        last = resp
        if "every 2 minutes" in str(last):           # Dhan's mint cooldown — wait it out
            wait = 125
        else:                                        # boundary/replayed/overloaded — next window
            wait = 30 - (time.time() % 30) + 1
        print(f"  attempt {attempt} failed ({str(last)[:80]}); retrying in {wait:.0f}s …")
        time.sleep(wait)
    if not token:
        sys.exit(f"generate_token returned no recognizable access token after 6 attempts: {str(last)[:200]}")

    # Rewrite .dhan_creds: replace (or add) DHAN_ACCESS_TOKEN, keep the secrets so the file stays
    # self-contained for the next refresh. Known keys first (stable order), then any extras.
    creds["DHAN_CLIENT_ID"] = vals["DHAN_CLIENT_ID"]
    creds["DHAN_ACCESS_TOKEN"] = token
    creds["DHAN_TOKEN_DATE"] = today            # marks today done -> later timer fires are no-ops
    creds.setdefault("DHAN_PIN", vals["DHAN_PIN"])
    creds.setdefault("DHAN_TOTP_SECRET", vals["DHAN_TOTP_SECRET"])
    order = ["DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN", "DHAN_TOKEN_DATE", "DHAN_PIN", "DHAN_TOTP_SECRET"]
    lines = [f"{k}={creds[k]}" for k in order if k in creds]
    lines += [f"{k}={v}" for k, v in creds.items() if k not in order]
    # Atomic write (temp -> fsync -> os.replace): the long-lived web process watches this file's
    # mtime to adopt the rotated token (india._reload_token_if_changed), so the mtime must flip
    # exactly ONCE on a complete file — a plain truncate+write leaves a window where that watcher
    # could read a half-written creds file.
    from pinescan import io_safe
    io_safe.atomic_write_text(CREDS_FILE, "\n".join(lines) + "\n")
    print(f"  refreshed DHAN_ACCESS_TOKEN in {CREDS_FILE} (valid ~24h).")


if __name__ == "__main__":
    main()
