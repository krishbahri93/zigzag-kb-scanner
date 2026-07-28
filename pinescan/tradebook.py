"""
tradebook.py — My TradeBook: the trades Krish ACTUALLY took, not what the scanner found.
========================================================================================

WHY THIS EXISTS (Krish, 2026-07-28)
  He buys a hand-picked subset of scanner signals (limited capital + a price-action bias
  he's built over years), sits until SL or target, and wants his OFFICIAL results tracked
  separately from the engine's all-signals forward test. Every "Bought" click snapshots
  the full signal context alongside his fill — so the book doubles as a labelled dataset
  of his discretion (which the automation lab can later learn a data-driven "Krish
  filter" from).

STORAGE
  One JSON file per dashboard login: data/tradebook/<user>.json (atomic writes, never in
  git — the data/ tree stays server-local). Books are PER-USER via Caddy's x-auth-user
  header, so Mammen's login sees his own (empty) book, not Krish's.

  Trade record: {id, market, sym, name, sector, swing, side, trigger_price, my_price,
  amount (₹, optional), sl, target, buy_date, opened_at, notes, context {depth_pct, rr,
  vol_x, day_pct}, status open|closed, exit_price, exit_date, exit_reason
  target|stop|manual, pnl_pct, pnl_amt, hold_days}
"""
import os
import re
import json
import time
import datetime as dt

from . import io_safe

DIR = "data/tradebook"


def _path(user):
    """One file per login; the username comes from the auth proxy but is sanitised
    anyway — a header must never be able to walk the filesystem."""
    safe = re.sub(r"[^a-z0-9_-]", "", (user or "").lower()) or "guest"
    return os.path.join(DIR, f"{safe}.json")


def _load(user):
    try:
        return json.load(open(_path(user), encoding="utf-8"))
    except Exception:
        return []


def _save(user, trades):
    os.makedirs(DIR, exist_ok=True)
    io_safe.atomic_write_text(_path(user), json.dumps(trades, indent=1))


def _scan_row(market, sym):
    """The stock's current scanner row (or None) — context snapshots + live prices."""
    from pinescan import service
    scan = service.read_scan(market, "nsv2") or {}
    for r in scan.get("rows", []):
        if r.get("sym") == sym:
            return r
    return None


def _quote(market, sym):
    """Best-effort CMP: the live scan row's ltp, else the cache's last close (India)."""
    r = _scan_row(market, sym)
    if r and r.get("ltp"):
        return float(r["ltp"])
    if market == "india":
        from pinescan.markets import india
        df = io_safe.read_parquet_safe(os.path.join(india.CACHE_DIR, f"{sym}.parquet"))
        if df is not None and len(df):
            return float(df["Close"].iloc[-1])
    return None


def add(user, market, p):
    """Record a buy. `p` needs sym + my_price (+ the plan the Buy widget passes through:
    trigger_price, sl, target, swing); amount/buy_date/notes optional. The signal context
    is snapshotted NOW from the live scan — it is gone once the setup completes."""
    sym = str(p["sym"]).upper().strip()
    my_price = float(p["my_price"])
    if my_price <= 0:
        raise ValueError("price must be positive")
    trades = _load(user)
    if any(t["sym"] == sym and t["market"] == market and t["status"] == "open"
           for t in trades):
        raise ValueError(f"{sym} is already open in your TradeBook")
    row = _scan_row(market, sym) or {}
    amount = float(p["amount"]) if p.get("amount") else None
    trade = {
        "id": f"t{int(time.time() * 1000)}",
        "market": market,
        "sym": sym,
        "name": row.get("name") or p.get("name") or "",
        "sector": row.get("sector") or "",
        "swing": p.get("swing") or "",
        "side": "long",
        "trigger_price": float(p["trigger_price"]) if p.get("trigger_price") else None,
        "my_price": my_price,
        "amount": amount,
        "sl": float(p["sl"]) if p.get("sl") else None,
        "target": float(p["target"]) if p.get("target") else None,
        "buy_date": str(p.get("buy_date") or dt.date.today()),
        "opened_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "notes": str(p.get("notes") or "")[:200],
        "context": {"depth_pct": p.get("depth_pct"), "rr": p.get("rr"),
                    "vol_x": row.get("vol_x"), "day_pct": row.get("day_pct")},
        "status": "open",
    }
    trades.append(trade)
    _save(user, trades)
    return trade


def close(user, trade_id, exit_price, reason):
    """Record an exit. reason: target | stop | manual. P&L is settled here, once."""
    if reason not in ("target", "stop", "manual"):
        raise ValueError("reason must be target, stop or manual")
    exit_price = float(exit_price)
    trades = _load(user)
    for t in trades:
        if t["id"] == trade_id and t["status"] == "open":
            t["status"] = "closed"
            t["exit_price"] = exit_price
            t["exit_date"] = str(dt.date.today())
            t["exit_reason"] = reason
            t["pnl_pct"] = round((exit_price / t["my_price"] - 1) * 100, 2)
            t["pnl_amt"] = (round(t["amount"] * (exit_price / t["my_price"] - 1), 2)
                            if t.get("amount") else None)
            try:
                t["hold_days"] = (dt.date.fromisoformat(t["exit_date"])
                                  - dt.date.fromisoformat(t["buy_date"])).days
            except Exception:
                t["hold_days"] = None
            _save(user, trades)
            return t
    raise ValueError("open trade not found")


def listing(user, market):
    """The tab's payload: OPEN positions enriched live + all-time 'my patterns'."""
    from pinescan import service
    trades = [t for t in _load(user) if t["market"] == market]
    today = dt.date.today()
    open_rows = []
    for t in (t for t in trades if t["status"] == "open"):
        cmp_ = _quote(market, t["sym"])
        up_pct = round((cmp_ / t["my_price"] - 1) * 100, 2) if cmp_ else None
        row = _scan_row(market, t["sym"])
        sig = service._best_sig(row) if row else None
        try:
            held = (today - dt.date.fromisoformat(t["buy_date"])).days
        except Exception:
            held = None
        open_rows.append(dict(t, cmp=cmp_, up_pct=up_pct,
                              up_amt=(round(t["amount"] * up_pct / 100, 2)
                                      if t.get("amount") and up_pct is not None else None),
                              dist_target_pct=(round((t["target"] / cmp_ - 1) * 100, 2)
                                               if t.get("target") and cmp_ else None),
                              dist_sl_pct=(round((t["sl"] / cmp_ - 1) * 100, 2)
                                           if t.get("sl") and cmp_ else None),
                              held_days=held, scan_sig=sig,
                              earnings_date=service.next_earnings(market, t["sym"])))
    return {"open": open_rows, "patterns": patterns(trades)}


def stats(user, market, days=30):
    """His OFFICIAL results over a period: closed trades + the headline numbers.
    days=0 -> all time."""
    trades = [t for t in _load(user)
              if t["market"] == market and t["status"] == "closed"]
    if days:
        cutoff = str(dt.date.today() - dt.timedelta(days=days))
        trades = [t for t in trades if (t.get("exit_date") or "") >= cutoff]
    trades.sort(key=lambda t: t.get("exit_date") or "", reverse=True)
    wins = [t for t in trades if (t.get("pnl_pct") or 0) > 0]
    amts = [t["pnl_amt"] for t in trades if t.get("pnl_amt") is not None]
    pcts = [t["pnl_pct"] for t in trades if t.get("pnl_pct") is not None]
    holds = [t["hold_days"] for t in trades if t.get("hold_days") is not None]
    return {
        "days": days,
        "n": len(trades),
        "n_win": len(wins),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else None,
        "pnl_amt": round(sum(amts), 2) if amts else None,
        "avg_pct": round(sum(pcts) / len(pcts), 2) if pcts else None,
        "best_pct": max(pcts) if pcts else None,
        "worst_pct": min(pcts) if pcts else None,
        "avg_hold_days": round(sum(holds) / len(holds), 1) if holds else None,
        "by_reason": {r: sum(1 for t in trades if t.get("exit_reason") == r)
                      for r in ("target", "stop", "manual")},
        "trades": trades,
    }


def patterns(trades):
    """The 'what am I actually buying' strip — the first taste of learning from his
    book. All-time, open + closed; grows more meaningful with every trade."""
    if not trades:
        return None
    by_sector, by_swing = {}, {}
    fills, amts = [], []
    for t in trades:
        if t.get("sector"):
            by_sector[t["sector"]] = by_sector.get(t["sector"], 0) + 1
        if t.get("swing"):
            by_swing[t["swing"]] = by_swing.get(t["swing"], 0) + 1
        if t.get("trigger_price") and t.get("my_price"):
            fills.append((t["my_price"] / t["trigger_price"] - 1) * 100)
        if t.get("amount"):
            amts.append(t["amount"])
    top = sorted(by_sector.items(), key=lambda kv: -kv[1])[:3]
    return {
        "n_total": len(trades),
        "top_sectors": [f"{k} ({v})" for k, v in top],
        "by_swing": by_swing,
        "avg_amount": round(sum(amts) / len(amts), 0) if amts else None,
        "avg_fill_vs_trigger_pct": round(sum(fills) / len(fills), 2) if fills else None,
    }
