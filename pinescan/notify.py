"""
notify.py — Telegram alerts for the scanner (Phase 4).
======================================================

DESIGN
  Alerts ride on the scan jobs: after every scan (15-min live tick or 15:55 close run),
  `process_scan_alerts(scan)` diffs the new state against what has already been announced
  (data/status/alerts_state.json) and sends AT MOST ONE batched Telegram message per run —
  never one ping per stock. Every event is announced exactly once per day per (symbol, trade).

EVENTS
  live tick:   ⚡ provisional trigger (trading above entry, not closed) · 🌅 first tick of the day
  close run:   ✅ confirmed entry (with entry/target/stop) · 🎯 target hit · 🛑 stopped out ·
               end-of-day summary
  both:        ⚠ open trade near its stop · 🎯 open trade near its target (once per day each)

CREDENTIALS
  .telegram (git-ignored KEY=VALUE: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID), entered via the
  Settings page. `detect_chat_id()` finds the group's chat id from the bot's recent messages.
  Missing credentials => everything degrades to a silent no-op (the scanner never breaks).
"""
import datetime as dt
import json
import os

import requests

from . import io_safe

CREDS_FILE = ".telegram"
STATE_FILE = "data/status/alerts_state.json"
LOG_FILE = "data/status/alerts_log.json"
LOG_KEEP = 300
API = "https://api.telegram.org"


def _creds():
    """{TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID} from env or .telegram ({} if unset)."""
    out = {}
    if os.path.exists(CREDS_FILE):
        for line in open(CREDS_FILE, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if os.environ.get(k):
            out[k] = os.environ[k]
    return out


def configured():
    c = _creds()
    return bool(c.get("TELEGRAM_BOT_TOKEN") and c.get("TELEGRAM_CHAT_ID"))


def write_creds(token="", chat_id=""):
    """Merge non-empty values into .telegram (same pattern as the Dhan creds file)."""
    c = {}
    if os.path.exists(CREDS_FILE):
        for line in open(CREDS_FILE, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                c[k.strip()] = v.strip()
    if token.strip():
        c["TELEGRAM_BOT_TOKEN"] = token.strip()
    if chat_id.strip():
        c["TELEGRAM_CHAT_ID"] = chat_id.strip()
    io_safe.atomic_write_text(CREDS_FILE, "".join(f"{k}={v}\n" for k, v in c.items()))
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        os.environ.pop(k, None)                       # the file is authoritative after a save


def detect_chat_id():
    """Find the chat the bot was most recently messaged in (group or DM) via getUpdates,
    save it, and send a hello. Returns {"ok", "msg"} — the Settings save shows this."""
    c = _creds()
    tok = c.get("TELEGRAM_BOT_TOKEN")
    if not tok:
        return {"ok": False, "msg": "No bot token saved yet."}
    try:
        r = requests.get(f"{API}/bot{tok}/getUpdates", timeout=15).json()
    except Exception as e:
        return {"ok": False, "msg": f"Telegram unreachable: {str(e)[:80]}"}
    if not r.get("ok"):
        return {"ok": False, "msg": f"Telegram rejected the token: {str(r)[:80]}"}
    chats = [u.get("message", {}).get("chat", {}) for u in r.get("result", [])]
    chats = [ch for ch in chats if ch.get("id")]
    if not chats:
        return {"ok": False, "msg": "No messages found — send any message in the group "
                                    "(with the bot added), then save again."}
    ch = chats[-1]
    write_creds(chat_id=str(ch["id"]))
    name = ch.get("title") or ch.get("first_name") or str(ch["id"])
    send(f"✅ KWM Scanner connected — alerts will arrive here ({name}).")
    return {"ok": True, "msg": f"Telegram connected to “{name}” ✓ — test message sent."}


def send(text):
    """Send one message (HTML mode). Returns True/False; never raises.

    Self-healing: when Telegram upgrades a group to a supergroup its chat id CHANGES and the
    old id starts bouncing ("migrate_to_chat_id" in the error) — follow the new id, persist
    it, and retry once, so a settings change in the group can never silently kill alerts."""
    c = _creds()
    tok, chat = c.get("TELEGRAM_BOT_TOKEN"), c.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return False

    def _post(chat_id):
        return requests.post(f"{API}/bot{tok}/sendMessage", timeout=15,
                             json={"chat_id": chat_id, "text": text[:4000],
                                   "parse_mode": "HTML",
                                   "disable_web_page_preview": True}).json()

    try:
        r = _post(chat)
        if r.get("ok"):
            return True
        new_id = (r.get("parameters") or {}).get("migrate_to_chat_id")
        if new_id:
            write_creds(chat_id=str(new_id))
            return bool(_post(str(new_id)).get("ok"))
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# the alert engine
# ---------------------------------------------------------------------------
def _nf(x, d=2):
    return "—" if x is None else f"{x:,.{d}f}"


def process_scan_alerts(scan, market="india", live=False):
    """Diff a fresh scan against the announced-state, send one batched message, log it.
    Called by intraday_tick (live=True) and the close run (live=False). Silent no-op
    without credentials. Never raises — alerting must not break scanning."""
    try:
        _process(scan, market, live)
    except Exception:
        pass


def _process(scan, market, live):
    if not configured():
        return
    today = str(dt.date.today())
    try:
        state = json.loads(open(STATE_FILE, encoding="utf-8").read())
    except Exception:
        state = {}
    state = {k: v for k, v in state.items() if k.startswith(today)}   # daily reset

    def once(kind, key):
        """True the FIRST time (kind,key) is seen today; records it."""
        k = f"{today}:{kind}:{key}"
        if k in state:
            return False
        state[k] = 1
        return True

    lines = []
    confirmed_today = []
    for r in scan.get("rows", []):
        sym = r["sym"]
        for s in r.get("swings", []):
            key = f"{sym}:{s['swing']}"
            tag = f"<b>{sym}</b> {s['swing']}"
            if s.get("state") == "IN" and s.get("bars_in_state", 99) <= 1 and not r.get("expired"):
                if live:
                    if once("prov", key):
                        lines.append(f"⚡ {tag} trading above entry {_nf(s.get('entry_hi'))} "
                                     f"(CMP {_nf(r.get('ltp'))}) — not closed yet")
                else:
                    if once("conf", key):
                        lines.append(f"✅ {tag} CONFIRMED entry {_nf(s.get('entry_hi'))} · "
                                     f"target {_nf(s.get('tp_lo'))} · stop {_nf(s.get('sl'))}")
                        confirmed_today.append(sym)
            if s.get("state") == "IN" and s.get("bars_in_state", 0) >= 2 and r.get("ltp") is not None:
                sl, tp = s.get("sl"), s.get("tp_lo")
                if sl and r["ltp"] <= sl * 1.03 and once("nearsl", key):
                    lines.append(f"🛑 {tag} within 3% of stop {_nf(sl)} (CMP {_nf(r['ltp'])})")
                if tp and 0 <= (tp / r["ltp"] - 1) * 100 <= 3 and once("neartp", key):
                    lines.append(f"🎯 {tag} within 3% of target {_nf(tp)} (CMP {_nf(r['ltp'])})")
            if not live:
                if s.get("tp_date") == today and once("tphit", key):
                    lines.append(f"🎯🏁 {tag} TARGET HIT at {_nf(s.get('tp_lo'))}")
                if s.get("last_sl_date") == today and once("slhit", key):
                    lines.append(f"🛑🏁 {tag} stopped out at {_nf(s.get('sl'))}")

    if live and once("dayopen", market):
        lines.insert(0, "🌅 Scanner live — market day started.")
    if not live and once("eod", market):
        n_conf = len(set(confirmed_today))
        lines.append(f"🌇 Close run done — {scan.get('actionable_count', '—')} actionable setups; "
                     f"{n_conf} confirmed entr{'y' if n_conf == 1 else 'ies'} today.")

    if lines:
        mkt = "🇮🇳 INDIA" if market == "india" else ("🇺🇸 US" if market == "us" else market.upper())
        header = f"📈 <b>KWM Auto Screener</b> · {mkt}" + (" · live" if live else " · close") + "\n"
        sent = send(header + "\n".join(lines))
        _log(lines, live, sent)

    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    io_safe.atomic_write_text(STATE_FILE, json.dumps(state))


def _log(lines, live, sent):
    try:
        log = json.loads(open(LOG_FILE, encoding="utf-8").read())
    except Exception:
        log = []
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    for ln in lines:
        log.append({"at": now, "live": live, "sent": bool(sent), "text": ln})
    log = log[-LOG_KEEP:]
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    io_safe.atomic_write_text(LOG_FILE, json.dumps(log))
