"""
╔══════════════════════════════════════════════════════════════╗
║              NEXUS AI - Dashboard API Server                 ║
║          Reads bot state files → serves JSON on :8080        ║
╚══════════════════════════════════════════════════════════════╝

Run standalone:   py api_server.py
Or import:        from api_server import start_api_server
"""

import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime
from aiohttp import web

# ─── Paths ───────────────────────────────────────────────────
BASE = Path(__file__).parent
DATA_STORE = BASE / "data_store"
POSITIONS_FILE = DATA_STORE / "positions.json"
WEIGHTS_FILE = DATA_STORE / "reactive_weights.json"
DB_FILE = DATA_STORE / "nexus.db"
AB_LOG_FILE = DATA_STORE / "ab_log.json"
TRAINING_DIR = BASE / "training"
OUTCOMES_FILE = TRAINING_DIR / "trade_outcomes.json"

PORT = 8080
_boot_time = time.time()


# ─── Helpers ─────────────────────────────────────────────────

def _read_json(path: Path, default=None):
    """Safely read a JSON file, returning default on any failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _query_db(sql: str, params: tuple = ()):
    """Run a read-only query against nexus.db, return list of dicts."""
    if not DB_FILE.exists():
        return []
    try:
        con = sqlite3.connect(str(DB_FILE), timeout=2)
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute(sql, params).fetchall()]
        con.close()
        return rows
    except Exception:
        return []


def _uptime() -> str:
    s = int(time.time() - _boot_time)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60}s"
    return f"{s // 3600}h {(s % 3600) // 60}m"


# ─── Route handlers ─────────────────────────────────────────

async def handle_stats(_request):
    """Aggregate stats from positions, weights, DB."""
    weights = _read_json(WEIGHTS_FILE)
    positions = _read_json(POSITIONS_FILE, default={})
    if isinstance(positions, list):
        open_count = len(positions)
    else:
        open_count = len(positions)

    # Total trades / win-loss from weights file (reactive AI tracks these)
    total_trades = weights.get("total_trades", 0)
    wins = weights.get("wins", 0)
    losses = weights.get("losses", 0)
    total_pnl = weights.get("total_pnl", 0.0)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

    # Tokens analyzed from scans table
    scans_count = _query_db("SELECT COUNT(*) as cnt FROM scans")
    tokens_analyzed = scans_count[0]["cnt"] if scans_count else 0

    # Balance from simulator or config
    balance = 1.0  # default
    try:
        from config import config
        balance = config.SIMULATION_STARTING_SOL
    except Exception:
        pass

    # Determine mode
    mode = "DRY_RUN"
    try:
        from config import config as cfg
        if not cfg.DRY_RUN and not cfg.SIMULATION_MODE:
            mode = "LIVE"
        elif cfg.SIMULATION_MODE:
            mode = "SIMULATION"
    except Exception:
        pass

    return web.json_response({
        "balance": balance + total_pnl,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "open_positions": open_count,
        "tokens_analyzed": tokens_analyzed,
        "uptime": _uptime(),
        "mode": mode,
    })


async def handle_positions(_request):
    """Open positions from positions.json."""
    raw = _read_json(POSITIONS_FILE, default={})

    # positions.json can be {id: pos} dict or [pos] list
    if isinstance(raw, dict):
        items = list(raw.values())
    else:
        items = raw

    result = []
    now = datetime.now()
    for p in items:
        entry = p.get("entry_price", 0)
        current = p.get("current_price", entry)
        pnl_pct = ((current - entry) / entry * 100) if entry else 0

        # Age
        age = "—"
        et = p.get("entry_time")
        if et:
            try:
                dt = datetime.fromisoformat(et) if isinstance(et, str) else et
                delta = now - dt
                mins = int(delta.total_seconds() / 60)
                if mins < 60:
                    age = f"{mins}m"
                else:
                    age = f"{mins // 60}h {mins % 60}m"
            except Exception:
                pass

        result.append({
            "symbol": p.get("token_symbol", p.get("token_mint", "???")[:8]),
            "token_mint": p.get("token_mint"),
            "entry_price": entry,
            "current_price": current,
            "pnl_percent": round(pnl_pct, 2),
            "size_sol": p.get("sol_invested", 0),
            "age": age,
            "stop_loss": p.get("stop_loss"),
            "take_profit": p.get("take_profit"),
        })
    return web.json_response(result)


async def handle_ab_log(_request):
    """A/B test log from ab_log.json."""
    entries = _read_json(AB_LOG_FILE, default=[])
    if not isinstance(entries, list):
        entries = []
    return web.json_response(entries)


async def handle_weights(_request):
    """Reactive AI weights."""
    w = _read_json(WEIGHTS_FILE)
    return web.json_response({
        "token_analyzer_trust": w.get("token_analyzer_trust", 1.0),
        "sentiment_trust": w.get("sentiment_trust", 1.0),
        "risk_trust": w.get("risk_trust", 1.0),
        "volume_weight": w.get("volume_weight", 1.0),
        "whale_weight": w.get("whale_signal_weight", 1.0),
        "position_size_mult": w.get("position_size_multiplier", 1.0),
        "learning_rate": w.get("learning_rate", 0.15),
        "total_trades": w.get("total_trades", 0),
        "wins": w.get("wins", 0),
        "losses": w.get("losses", 0),
        "total_pnl": w.get("total_pnl", 0.0),
    })


async def handle_activity(_request):
    """Recent activity from activity.json (written by bot) + DB trades/scans."""
    # Primary source: activity.json (live events including rug check rejections)
    ACTIVITY_FILE = DATA_STORE / "activity.json"
    events = _read_json(ACTIVITY_FILE, default=[])
    if not isinstance(events, list):
        events = []

    # Supplement with DB trades
    trades = _query_db(
        "SELECT token_symbol, side, pnl_percent, outcome, entry_time, exit_time, "
        "sol_invested, exit_reason FROM trades ORDER BY id DESC LIMIT 50"
    )
    seen_ts = {e.get("timestamp", "") for e in events}
    for t in trades:
        ts = t.get("exit_time") or t.get("entry_time") or ""
        if ts in seen_ts:
            continue
        if t["side"] == "BUY":
            events.append({
                "type": "buy",
                "message": f"Bought {t['token_symbol']} for {t.get('sol_invested', '?')} SOL",
                "timestamp": ts,
            })
        if t.get("exit_time"):
            pnl = t.get("pnl_percent", 0) or 0
            events.append({
                "type": "sell",
                "message": f"Sold {t['token_symbol']} — {t.get('exit_reason', 'MANUAL')} "
                           f"({'+' if pnl >= 0 else ''}{pnl:.1f}%)",
                "timestamp": ts,
                "pnl": pnl,
            })

    # Recent scans (last 30)
    scans = _query_db(
        "SELECT token_symbol, ai_decision, ai_confidence, scan_time "
        "FROM scans ORDER BY id DESC LIMIT 30"
    )
    for s in scans:
        dec = s.get("ai_decision", "SKIP")
        events.append({
            "type": "scan" if dec == "SKIP" else "buy",
            "message": f"Scanned {s['token_symbol']} → {dec} ({s.get('ai_confidence', 0)}%)",
            "timestamp": s.get("scan_time", ""),
        })

    # Sort by timestamp descending
    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return web.json_response(events[:100])


# ─── CORS middleware ─────────────────────────────────────────

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response()
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


# ─── App factory ─────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_get("/api/positions", handle_positions)
    app.router.add_get("/api/ab-log", handle_ab_log)
    app.router.add_get("/api/weights", handle_weights)
    app.router.add_get("/api/activity", handle_activity)
    return app


async def start_api_server():
    """Start as background task (call from bot's event loop)."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"  📊 Dashboard API running on http://localhost:{PORT}")
    return runner


if __name__ == "__main__":
    print(f"Starting NEXUS Dashboard API on port {PORT}...")
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
