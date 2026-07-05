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
    creds = _read_creds(CREDS_FILE)
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
    # wild with a synced clock. On failure, sleep into the NEXT code window and try a fresh code.
    for attempt in range(1, 4):
        resp = login.generate_token(vals["DHAN_PIN"], totp.now())
        token = _extract_token(resp)
        if token:
            break
        last = resp
        wait = 30 - (time.time() % 30) + 1
        print(f"  attempt {attempt} failed ({str(last)[:80]}); retrying with the next code in {wait:.0f}s …")
        time.sleep(wait)
    if not token:
        sys.exit(f"generate_token returned no recognizable access token after 3 attempts: {str(last)[:200]}")

    # Rewrite .dhan_creds: replace (or add) DHAN_ACCESS_TOKEN, keep the secrets so the file stays
    # self-contained for the next refresh. Known keys first (stable order), then any extras.
    creds["DHAN_CLIENT_ID"] = vals["DHAN_CLIENT_ID"]
    creds["DHAN_ACCESS_TOKEN"] = token
    creds.setdefault("DHAN_PIN", vals["DHAN_PIN"])
    creds.setdefault("DHAN_TOTP_SECRET", vals["DHAN_TOTP_SECRET"])
    order = ["DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN", "DHAN_PIN", "DHAN_TOTP_SECRET"]
    lines = [f"{k}={creds[k]}" for k in order if k in creds]
    lines += [f"{k}={v}" for k, v in creds.items() if k not in order]
    open(CREDS_FILE, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"  refreshed DHAN_ACCESS_TOKEN in {CREDS_FILE} (valid ~24h).")


if __name__ == "__main__":
    main()
