"""
Acceptance for the token-mint idempotency guard (the 2026-09-15/16 outage fix).
==============================================================================

The refresh script now runs SEVERAL times a morning (retry timer), so the "already
minted today" short-circuit must be exact: skip when today's token exists, mint
otherwise, and honour --force. Run as a subprocess so we exercise the real CLI entry
without importing pyotp/dhanhq (the skip path returns before those imports).
"""
import subprocess
import sys
import datetime as dt
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "refresh_dhan_token.py"


def _run(cwd, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd,
                          capture_output=True, text=True)


def test_skips_when_already_minted_today(tmp_path):
    today = str(dt.date.today())
    (tmp_path / ".dhan_creds").write_text(
        f"DHAN_CLIENT_ID=x\nDHAN_ACCESS_TOKEN=live\nDHAN_TOKEN_DATE={today}\n"
        "DHAN_PIN=1111\nDHAN_TOTP_SECRET=BASE32SECRET\n")
    r = _run(tmp_path)
    assert r.returncode == 0
    assert "already minted today" in r.stdout
    # untouched — no mint attempt, so the token stays exactly as written
    assert "DHAN_ACCESS_TOKEN=live" in (tmp_path / ".dhan_creds").read_text()


def test_stale_date_does_not_skip(tmp_path, monkeypatch):
    # Yesterday's marker must NOT short-circuit — it should proceed to mint (and fail
    # fast here on the fake secret, proving it went past the guard, not that it skipped).
    yday = str(dt.date.today() - dt.timedelta(days=1))
    (tmp_path / ".dhan_creds").write_text(
        f"DHAN_CLIENT_ID=x\nDHAN_ACCESS_TOKEN=old\nDHAN_TOKEN_DATE={yday}\n"
        "DHAN_PIN=1111\nDHAN_TOTP_SECRET=not-valid-base32\n")
    r = _run(tmp_path)
    assert "already minted today" not in r.stdout


def test_force_overrides_the_skip(tmp_path):
    today = str(dt.date.today())
    (tmp_path / ".dhan_creds").write_text(
        f"DHAN_CLIENT_ID=x\nDHAN_ACCESS_TOKEN=live\nDHAN_TOKEN_DATE={today}\n"
        "DHAN_PIN=1111\nDHAN_TOTP_SECRET=not-valid-base32\n")
    r = _run(tmp_path, "--force")
    assert "already minted today" not in r.stdout
