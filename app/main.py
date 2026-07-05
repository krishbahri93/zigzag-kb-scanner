"""
main.py — the local FastAPI app: Scanner + Forward + Settings, over the SAME pinescan.service
functions the CLIs use (no scan/forward logic lives here). Launched by start.bat via
`uvicorn app.main:app`. Read-only on the data cache (every page recomputes from it, so a crash can't
corrupt anything); the one mutating action is Refresh, which runs in a single background job.

ROUTES
  GET  /                 -> /scanner?market=us
  GET  /scanner          -> live actionable setups (the recommendations) for a market + scanner
  GET  /forward          -> the 5-strategy paper-trading standings + open positions (table-first)
  GET  /settings         -> enter API keys; trigger Refresh; see data freshness
  POST /settings/keys    -> persist a user's keys (atomic, via service.write_*)
  POST /refresh          -> start a background data refresh (single-flight)
  GET  /status           -> {data_status, job} JSON for the status-strip poll
"""
import os
import subprocess
import sys

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from pinescan import service
from pinescan.scanners import registry
from app.jobs import Jobs

app = FastAPI(title="ZigZag Scanner (local)")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
jobs = Jobs()
MARKETS = ["us", "india"]


def _ctx(request, market):
    """The context every page needs: the status strip (data freshness, keys, current job) + the
    market list + the registered scanners."""
    return {"request": request, "markets": MARKETS, "market": market,
            "data": service.data_status(market), "job": jobs.status(),
            "scanners": registry.list_scanners()}


@app.get("/")
def home():
    return RedirectResponse("/scanner?market=india")


@app.get("/status")
def status(market: str = "us"):
    return JSONResponse({"data": service.data_status(market), "job": jobs.status()})


@app.get("/scanner")
def scanner_page(request: Request, market: str = "us", scanner: str = "nsv2"):
    ctx = _ctx(request, market)
    ctx["scanner"] = scanner
    ctx["scan"] = service.read_scan(market, scanner)   # cached (fast); None until the first Refresh
    return templates.TemplateResponse(request, "scanner.html", ctx)


@app.get("/forward")
def forward_page(request: Request, market: str = "us"):
    ctx = _ctx(request, market)
    ctx["fwd"] = service.read_forward(market)          # cached (fast); None until the first Refresh
    return templates.TemplateResponse(request, "forward.html", ctx)


@app.get("/settings")
def settings_page(request: Request, market: str = "us"):
    return templates.TemplateResponse(request, "settings.html", _ctx(request, market))


def _mint_dhan_token(prog):
    """Run the headless Dhan token mint (the same script the 08:30 timer runs) as a background job,
    so freshly saved secrets are validated within seconds instead of the next morning."""
    prog("Contacting Dhan to mint today's token …")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(root, "scripts", "refresh_dhan_token.py")
    r = subprocess.run([sys.executable, script], cwd=root,
                       capture_output=True, text=True, timeout=300)
    if r.returncode == 0:
        return {"ok": True, "msg": "Dhan token minted ✓ — it now auto-renews daily at 08:30."}
    err = (r.stderr or r.stdout or "").strip().splitlines()
    return {"ok": False, "msg": f"Dhan token mint failed: {err[-1][:140] if err else 'unknown error'}"}


@app.post("/settings/keys")
def save_keys(market: str = Form("us"), polygon_key: str = Form(""),
              dhan_client_id: str = Form(""), dhan_token: str = Form(""),
              dhan_pin: str = Form(""), dhan_totp_secret: str = Form("")):
    if polygon_key.strip():
        service.write_polygon_key(polygon_key)
    if any(v.strip() for v in (dhan_client_id, dhan_token, dhan_pin, dhan_totp_secret)):
        service.write_dhan_creds(dhan_client_id, dhan_token, dhan_pin, dhan_totp_secret)
        # all three long-lived secrets present -> mint a token right now (single-flight, visible
        # in the status strip), so the user immediately learns whether the secrets work
        if service.data_status("india")["keys"].get("dhan_auto"):
            jobs.start(_mint_dhan_token, label="Minting today's Dhan token …")
    return RedirectResponse(f"/settings?market={market}", status_code=303)


@app.post("/refresh")
def refresh(request: Request, market: str = Form("us")):
    jobs.start(lambda prog: service.refresh_market(market, prog), label=f"Refreshing {market} …")
    back = request.headers.get("referer") or f"/scanner?market={market}"
    return RedirectResponse(back, status_code=303)
