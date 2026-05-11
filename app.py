"""
╔══════════════════════════════════════════════════════════════════════╗
║         THUNDER RADAR V101 — INSTITUTIONAL GRADE SCALPING           ║
║                                                                      ║
║  MOTOR DE DETECCIÓN (Tríada de Momentum):                           ║
║  1. Tendencia Alcista : Precio > VWAP  y  Precio > EMA-9           ║
║  2. Liquidez          : RVOL > umbral configurado                   ║
║  3. Explosión         : ROC (Rate of Change) 1-5min > umbral        ║
║                                                                      ║
║  CASCADA DE DATOS (Failover absoluto):                              ║
║  Alpaca WS → Alpaca REST → Yahoo Finance (10 UA) → Twelve Data      ║
║              → Alpha Vantage                                        ║
║                                                                      ║
║  FUNCIONES:                                                          ║
║  • Alert Window automática (HOD + RVOL + Tape Speed)                ║
║  • Top 5min Ranking en vivo                                          ║
║  • Manual Scanner con evaluación instantánea                         ║
║  • Modo Simulación para testing out-of-hours                         ║
║  • Compra 1-click ($2000 por trade) → Alpaca Paper                  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

# ─────────────────────────────────────────────────────────────────────
#  IMPORTS
# ─────────────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
import numpy as np
import requests
import threading
import asyncio
import time
import random
import math
import warnings
from datetime import datetime, timedelta
from collections import deque
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")

# Alpaca
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.requests import TakeProfitRequest, StopLossRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import (StockBarsRequest, StockSnapshotRequest,
                                       StockLatestQuoteRequest)
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.data.live import StockDataStream
    ALPACA_OK = True
except Exception:
    ALPACA_OK = False

# yfinance como fallback
try:
    import yfinance as yf
    YF_OK = True
except Exception:
    YF_OK = False

# ─────────────────────────────────────────────────────────────────────
#  CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="⚡ THUNDER RADAR V101",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────
#  CSS + AUDIO JS
# ─────────────────────────────────────────────────────────────────────
st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');

/* ── BASE ── */
html,body,[class*="css"]{
    background:#020709!important;color:#c9d1d9!important;
    font-family:'Share Tech Mono',monospace;
}
h1,h2,h3{font-family:'Orbitron',sans-serif!important;}

/* ── BUTTONS ── */
.stButton>button{
    width:100%;border-radius:4px;font-weight:bold;
    font-family:'Orbitron',sans-serif;letter-spacing:1px;
    border:1px solid #30363d;transition:all .2s;
}
.stButton>button:hover{transform:translateY(-1px);box-shadow:0 0 14px #00ff8866;}
div[data-testid="metric-container"]{
    background:linear-gradient(135deg,#080d14,#0d1520);
    border:1px solid #1a2535;border-radius:8px;padding:12px;
}

/* ── ALERT CARDS ── */
.card-triple{
    background:linear-gradient(135deg,#1a0400,#0a0205);
    border:2px solid #ff0000;border-radius:9px;
    padding:12px 16px;margin:4px 0;
    animation:pulse-red .85s infinite;
}
@keyframes pulse-red{
    0%,100%{box-shadow:0 0 8px #ff000033;}50%{box-shadow:0 0 28px #ff000088;}
}
.card-hot{
    background:linear-gradient(135deg,#0a0f00,#080d14);
    border:2px solid #00ff88;border-radius:9px;padding:12px 16px;margin:4px 0;
    box-shadow:0 0 14px #00ff8833;
}
.card-mid{
    background:#07090d;border:1px solid #ffc107;
    border-radius:8px;padding:10px 14px;margin:3px 0;
}
.card-cold{
    background:#07090d;border:1px solid #33444466;
    border-radius:8px;padding:10px 14px;margin:3px 0;
}
.card-sim{
    background:linear-gradient(135deg,#001a10,#080d14);
    border:2px solid #00ff88;border-radius:9px;padding:12px 16px;margin:4px 0;
    box-shadow:0 0 10px #00ff8855;
}

/* ── FORCE BAR ── */
.fbar-bg{background:#1a1a2e;border-radius:14px;height:19px;
    width:100%;overflow:hidden;border:1px solid #333;margin:4px 0;}
.fbar-fill{height:100%;border-radius:14px;display:flex;
    align-items:center;justify-content:center;
    font-weight:900;font-size:.76em;color:#000;font-family:'Orbitron',sans-serif;}

/* ── ROC BADGE ── */
.roc-fire{color:#ff4500;font-weight:900;}
.roc-high{color:#ff8c00;font-weight:700;}
.roc-ok  {color:#ffc107;}
.roc-flat{color:#8b949e;}

/* ── HEADER ── */
.hdr{text-align:center;font-family:'Orbitron',sans-serif;font-size:2.0em;font-weight:900;
    background:linear-gradient(90deg,#ff0000,#ff4500,#ffc107,#00ff88,#00d4ff);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:3px;}
.sub{text-align:center;color:#8b949e;font-size:.74em;letter-spacing:3px;}
.badge{display:inline-block;padding:2px 9px;border-radius:18px;font-size:.72em;font-weight:bold;}
.b-reg{background:#15803d;color:#fff;}.b-pre{background:#7c3aed;color:#fff;}
.b-aft{background:#0369a1;color:#fff;}.b-cls{background:#374151;color:#fff;}
.b-sim{background:#ff4500;color:#fff;}
.bx{display:inline-block;padding:1px 7px;border-radius:4px;font-size:.67em;font-weight:bold;margin:1px;}
.bx-hod{background:#ff0000;color:#fff;}
.bx-rvol{background:#ff8c00;color:#fff;}
.bx-roc{background:#7c3aed;color:#fff;}
.bx-vwap{background:#00ff88;color:#000;}
.bx-ema{background:#00d4ff;color:#000;}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;
    animation:blink .7s infinite;}
.dot-green{background:#00ff88;}.dot-red{background:#ff4500;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.1}}
hr.n{border:none;border-top:1px solid #ff450022;margin:10px 0;}
.ibox{background:#080d14;border:1px solid #1a2535;border-radius:7px;
    padding:9px 13px;margin:5px 0;font-size:.78em;line-height:1.55em;}
.ibox-ok{background:#080d14;border:1px solid #00ff8833;border-radius:7px;
    padding:9px 13px;margin:5px 0;font-size:.78em;}
.sim-banner{background:linear-gradient(90deg,#ff4500,#ff8c00);
    color:#000;font-weight:900;font-family:'Orbitron',sans-serif;
    text-align:center;padding:6px;border-radius:6px;margin:6px 0;font-size:.85em;
    letter-spacing:2px;}
.tkr{font-family:'Orbitron',sans-serif;font-size:1.2em;font-weight:900;color:#fff;}
.lbl{color:#8b949e;font-size:.72em;}
.s10{color:#00ff88;font-size:1.8em;font-weight:900;font-family:'Orbitron',sans-serif;}
.s8 {color:#39ff14;font-size:1.5em;font-weight:800;}
.s6 {color:#ffc107;font-size:1.3em;font-weight:700;}
.s4 {color:#ff6b6b;font-size:1.1em;}
</style>

<script>
// ── AUDIO SYNTH ALERTS ──────────────────────────────────────────────
function playTone(freq1, freq2, freq3, vol) {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        [[freq1,0],[freq2,0.15],[freq3,0.30]].forEach(([f,t]) => {
            const o = ctx.createOscillator();
            const g = ctx.createGain();
            o.connect(g); g.connect(ctx.destination);
            o.frequency.setValueAtTime(f, ctx.currentTime+t);
            g.gain.setValueAtTime(vol, ctx.currentTime+t);
            g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime+t+0.35);
            o.start(ctx.currentTime+t); o.stop(ctx.currentTime+t+0.4);
        });
    } catch(e) {}
}
function alertTriple() { playTone(880,1100,1320,0.4); }
function alertNormal() { playTone(660, 880, 660, 0.3); }
function alertSim()    { playTone(440, 554, 659, 0.25); }

setInterval(function() {
    const el = document.getElementById('audio-trigger');
    if (!el) return;
    const tipo = el.dataset.tipo;
    if (!tipo || tipo === '0') return;
    if      (tipo === 'triple') alertTriple();
    else if (tipo === 'sim')    alertSim();
    else                        alertNormal();
    el.dataset.tipo = '0';
}, 1200);
</script>
<div id="audio-trigger" data-tipo="0" style="display:none"></div>
""", unsafe_allow_html=True)

ET = ZoneInfo("America/New_York")

# ─────────────────────────────────────────────────────────────────────
#  API KEYS — st.secrets con fallback a valores demo
# ─────────────────────────────────────────────────────────────────────
def _load_keys():
    try:    ak = st.secrets["alpaca"]["key"]
    except: ak = "PKOKUMRZBCA2YJKVZIATSPGV5J"
    try:    as_ = st.secrets["alpaca"]["secret"]
    except: as_ = "2UBriZpW7NooR1EvtowC63GcarFt7rEQFD9ofti9Ah6N"
    try:    td = st.secrets["twelve"]["key"]
    except: td = ""
    try:    av = st.secrets["alphavantage"]["key"]
    except: av = "demo"
    return ak, as_, td, av

ALPACA_KEY, ALPACA_SECRET, TWELVE_KEY, AV_KEY = _load_keys()

# ─────────────────────────────────────────────────────────────────────
#  CLIENTES ALPACA (cached)
# ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def _get_trading():
    if not ALPACA_OK: return None
    try:    return TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)
    except: return None

@st.cache_resource
def _get_data():
    if not ALPACA_OK: return None
    try:    return StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)
    except: return None

trading = _get_trading()
data_cl = _get_data()

# ─────────────────────────────────────────────────────────────────────
#  USER-AGENTS para rotación Yahoo Finance (evitar 429)
# ─────────────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
]

_ua_idx   = 0
_ua_lock  = threading.Lock()

def get_ua() -> dict:
    """Rota User-Agent en cada llamada para evitar bloqueo de Yahoo."""
    global _ua_idx
    with _ua_lock:
        ua = USER_AGENTS[_ua_idx % len(USER_AGENTS)]
        _ua_idx += 1
    return {"User-Agent": ua, "Accept": "application/json"}

# ─────────────────────────────────────────────────────────────────────
#  SESIÓN DE MERCADO
# ─────────────────────────────────────────────────────────────────────
def get_session() -> str:
    h = datetime.now(ET).hour + datetime.now(ET).minute / 60.0
    if   4.0  <= h < 9.5:  return "PRE-MARKET"
    elif 9.5  <= h < 16.0: return "REGULAR"
    elif 16.0 <= h < 20.0: return "AFTER-HOURS"
    else:                   return "CERRADO"

SESSION = get_session()

# ─────────────────────────────────────────────────────────────────────
#  SHARED STATE — thread-safe
# ─────────────────────────────────────────────────────────────────────
_lock = threading.Lock()

shared = {
    # Precios en vivo: {sym: float}
    "prices"     : {},
    # HOD (High of Day): {sym: float}
    "hod"        : {},
    # LOD (Low of Day): {sym: float}
    "lod"        : {},
    # Open del día: {sym: float}
    "open_day"   : {},
    # Volumen acumulado vela actual: {sym: float}
    "vol_curr"   : {},
    # Open de la vela de 1min actual: {sym: float}
    "open_1m"    : {},
    # Barras históricas: {sym: list[dict]}
    "bars"       : {},
    # Rolling 5min tick-by-tick: {sym: deque(maxlen=600)}
    "rolling5"   : {},
    # Tape speed: {sym: deque(maxlen=200)} de timestamps
    "tape"       : {},
    # VWAP acumulado: {sym: {"pv":float,"vol":float}}
    "vwap_acc"   : {},
    # EMA-9 en vivo: {sym: float}
    "ema9"       : {},
    # Alert Window: list[dict] (más nuevas primero)
    "alertas"    : [],
    # Top 5min ranking: list[dict]
    "ranking5"   : [],
    # Watchlist manual: {sym: dict}
    "watchlist"  : {},
    # WebSocket
    "ws_status"  : "DESCONECTADO",
    "ws_tickers" : [],
    "ws_ticks"   : 0,
    "ws_last"    : None,
    # Sabueso
    "sabueso_st" : "INACTIVO",
    "sabueso_ts" : None,
    "sabueso_tk" : [],
    # Audio trigger
    "audio"      : "0",
    # Fuente de datos en uso
    "fuente_data": "—",
    # Config dinámica (sliders → WebSocket)
    "cfg": {
        "precio_min" : 1.0,
        "precio_max" : 500.0,
        "rvol_min"   : 2.5,
        "roc_min"    : 1.5,
        "hod_dist"   : 1.0,
        "min_force"  : 60,
        "trade_usd"  : 2000.0,
        "sim_mode"   : False,
    },
}

# ─────────────────────────────────────────────────────────────────────
#  CASCADA DE DATOS — Fuentes en orden de prioridad
# ─────────────────────────────────────────────────────────────────────

# ── FUENTE 1: Alpaca Snapshots ────────────────────────────────────────
def _alpaca_top_gainers(n: int = 60) -> list:
    """
    Usa el endpoint de Snapshots de Alpaca para detectar top movers.
    Ordena por % cambio descendente y filtra por rango de precio.
    """
    if not data_cl:
        return []
    try:
        cfg    = shared["cfg"]
        # Lista base de tickers conocidos por volatilidad
        base   = _base_universe()
        lote   = 100
        result = []
        for i in range(0, len(base), lote):
            chunk = base[i:i+lote]
            try:
                req  = StockSnapshotRequest(symbol_or_symbols=chunk, feed="iex")
                snaps = data_cl.get_stock_snapshot(req)
                for sym, snap in snaps.items():
                    try:
                        precio = float(snap.latest_trade.price)
                        if not (cfg["precio_min"] <= precio <= cfg["precio_max"]):
                            continue
                        prev_close = float(snap.previous_daily_bar.close) if snap.previous_daily_bar else precio
                        chg = (precio - prev_close) / max(prev_close, 1e-9) * 100
                        if chg > 0:
                            result.append((sym, chg, precio))
                    except Exception:
                        continue
            except Exception:
                pass
        result.sort(key=lambda x: -x[1])
        syms = [r[0] for r in result[:n]]
        with _lock:
            shared["fuente_data"] = "🟢 Alpaca Snapshots"
        return syms
    except Exception:
        return []


# ── FUENTE 2: Yahoo Finance Screener (con rotación de UA + backoff) ──
def _yahoo_screener(sid: str, n: int = 50, retries: int = 3) -> list:
    """
    Yahoo Finance Screener con 10 User-Agents rotativos y backoff exponencial.
    Maneja error 429 (Too Many Requests) con espera incremental.
    """
    cfg = shared["cfg"]
    for attempt in range(retries):
        try:
            r = requests.get(
                "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved",
                headers=get_ua(),
                params={"scrIds": sid, "count": n, "formatted": "false"},
                timeout=9,
            )
            if r.status_code == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                continue
            quotes = (r.json().get("finance", {})
                       .get("result", [{}])[0].get("quotes", []))
            out = []
            for q in quotes:
                s = q.get("symbol", "").strip().upper()
                if not s or not s.isalpha() or not (1 < len(s) <= 5):
                    continue
                p = float(q.get("regularMarketPrice", 0) or 0)
                if cfg["precio_min"] <= p <= cfg["precio_max"]:
                    out.append(s)
            if out:
                with _lock:
                    shared["fuente_data"] = "🟡 Yahoo Finance"
                return out
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return []


def _yahoo_top_gainers(n: int = 60) -> list:
    """Combina varios screeners de Yahoo."""
    t1 = _yahoo_screener("day_gainers",       n)
    t2 = _yahoo_screener("most_actives",      n)
    t3 = _yahoo_screener("small_cap_gainers", n)
    return list(dict.fromkeys(t1 + t2 + t3))[:n]


# ── FUENTE 3: Twelve Data ─────────────────────────────────────────────
def _twelve_top_gainers(n: int = 40) -> list:
    """Twelve Data market movers (requiere API key gratuita)."""
    if not TWELVE_KEY:
        return []
    cfg = shared["cfg"]
    out = []
    for exc in ["NYSE", "NASDAQ", "AMEX"]:
        try:
            r = requests.get(
                "https://api.twelvedata.com/stocks/market/movers",
                params={"exchange": exc, "direction": "gainers",
                        "outputsize": n, "country": "US", "apikey": TWELVE_KEY},
                timeout=8,
            )
            if r.status_code == 200 and "values" in r.json():
                for item in r.json()["values"]:
                    s = item.get("symbol", "").strip().upper()
                    p = float(item.get("price", 0) or 0)
                    if s and s.isalpha() and (1 < len(s) <= 5) and (cfg["precio_min"] <= p <= cfg["precio_max"]):
                        out.append(s)
        except Exception:
            pass
    if out:
        with _lock:
            shared["fuente_data"] = "🟠 Twelve Data"
    return list(dict.fromkeys(out))[:n]


# ── FUENTE 4: Alpha Vantage TOP_GAINERS ──────────────────────────────
def _av_top_gainers(n: int = 30) -> list:
    """Alpha Vantage TOP_GAINERS como último recurso."""
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": "TOP_GAINERS_LOSERS", "apikey": AV_KEY},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        gainers = data.get("top_gainers", [])
        cfg = shared["cfg"]
        out = []
        for item in gainers[:n]:
            s = item.get("ticker", "").strip().upper()
            p = float(item.get("price", "0").replace(",", "") or 0)
            if s and s.isalpha() and (1 < len(s) <= 5) and (cfg["precio_min"] <= p <= cfg["precio_max"]):
                out.append(s)
        if out:
            with _lock:
                shared["fuente_data"] = "🔴 Alpha Vantage"
        return out
    except Exception:
        return []


# ── CASCADA COMPLETA ──────────────────────────────────────────────────
def obtener_top_movers(n: int = 80) -> list:
    """
    Cascada de failover: Alpaca → Yahoo → Twelve → Alpha Vantage.
    Devuelve hasta n tickers únicos ordenados por actividad.
    """
    result = []

    # Fuente 1: Alpaca Snapshots
    result = _alpaca_top_gainers(n)
    if len(result) >= 20:
        return result[:n]

    # Fuente 2: Yahoo Finance
    yf_result = _yahoo_top_gainers(n)
    result = list(dict.fromkeys(result + yf_result))
    if len(result) >= 20:
        return result[:n]

    # Fuente 3: Twelve Data
    td_result = _twelve_top_gainers(n)
    result = list(dict.fromkeys(result + td_result))
    if len(result) >= 10:
        return result[:n]

    # Fuente 4: Alpha Vantage
    av_result = _av_top_gainers(n)
    result = list(dict.fromkeys(result + av_result))
    if not result:
        # Fallback absoluto: universo base
        result = _base_universe()[:n]
        with _lock:
            shared["fuente_data"] = "⚫ Lista Base (sin internet)"
    return result[:n]


def _base_universe() -> list:
    """Lista base de stocks conocidos por alta volatilidad."""
    return list(dict.fromkeys([
        # Momentum stocks frecuentes
        "SDOT","BLZE","CLRB","STRL","BIYA","EVER","JLHL","NXTS","MRDN",
        "SKK","CNSP","PN","CRE","ELPW","GBTG","SSM","HCAI","RLYB","MNDR",
        "PHOE","GME","AMC","KOSS","BB","NOK","BBIG","SPCE","MULN","MVIS",
        "OCGN","CLOV","SNDL","TLRY","AGEN","MNMD","NVAX","MRNA","BNTX",
        "SRPT","ACAD","HIMS","CRSP","EDIT","COIN","HOOD","MSTR","RIOT",
        "MARA","HUT","CIFR","BTBT","CLSK","RIVN","LCID","CHPT","BLNK",
        "PLUG","FCEL","NIO","XPEV","LI","BABA","JD","PDD","ASTS","LUNR",
        "RKLB","ACHR","JOBY","IONQ","RGTI","SOFI","UPST","AFRM","ROOT",
        # Large/Mid cap con momentum
        "AAPL","MSFT","NVDA","TSLA","AMD","META","AMZN","GOOGL","NFLX",
        "AVGO","QCOM","MU","SMCI","PLTR","CRM","SNOW","DDOG","CRWD",
        "PTON","DOCU","ZM","LYFT","UBER","DASH","ABNB","DKNG","RBLX",
        "SNAP","PINS","PARA","WBD","ROKU","FUBO","SIRI","WKHS","NKLA",
    ]))


# ─────────────────────────────────────────────────────────────────────
#  HISTORIAL DE VELAS — Cascada de datos
# ─────────────────────────────────────────────────────────────────────
def obtener_historial(sym: str, minutos: int = 20) -> list:
    """
    Descarga velas de 1min. Orden de prioridad:
    1. Alpaca REST  2. yfinance  3. Twelve Data
    Maneja DataFrames vacíos correctamente.
    Retorna lista de dicts con open/high/low/close/volume.
    """
    # ── Fuente 1: Alpaca REST ─────────────────────────────────
    if data_cl:
        try:
            start = datetime.now(ET) - timedelta(minutes=minutos + 5)
            req   = StockBarsRequest(
                symbol_or_symbols=sym,
                timeframe=TimeFrame(1, TimeFrameUnit.Minute),
                start=start,
                feed="iex",
                adjustment="raw",
            )
            bars_resp = data_cl.get_stock_bars(req)

            # Extraer DataFrame de forma segura
            df = pd.DataFrame()
            try:
                if hasattr(bars_resp, "__getitem__"):
                    raw = bars_resp[sym]
                    if raw is not None:
                        df = raw.df if hasattr(raw, "df") else pd.DataFrame()
            except (KeyError, IndexError, TypeError):
                df = pd.DataFrame()

            if df is not None and not df.empty and len(df) >= 2:
                df = df.reset_index()
                result = []
                for _, row in df.iterrows():
                    try:
                        result.append({
                            "ts"    : row.get("timestamp", datetime.now(ET)),
                            "open"  : float(row.get("open",  0) or 0),
                            "high"  : float(row.get("high",  0) or 0),
                            "low"   : float(row.get("low",   0) or 0),
                            "close" : float(row.get("close", 0) or 0),
                            "volume": float(row.get("volume",0) or 0),
                            "vwap"  : float(row.get("vwap",  row.get("close", 0)) or 0),
                        })
                    except (ValueError, TypeError):
                        continue
                if len(result) >= 2:
                    return result
        except Exception:
            pass

    # ── Fuente 2: yfinance (fallback) ────────────────────────
    if YF_OK:
        try:
            ticker_yf = yf.Ticker(sym)
            df = ticker_yf.history(period="1d", interval="1m",
                                   prepost=True, auto_adjust=True)
            if df is not None and not df.empty and len(df) >= 2:
                result = []
                for ts, row in df.iterrows():
                    try:
                        close = float(row.get("Close", 0) or 0)
                        result.append({
                            "ts"    : ts,
                            "open"  : float(row.get("Open",  close) or close),
                            "high"  : float(row.get("High",  close) or close),
                            "low"   : float(row.get("Low",   close) or close),
                            "close" : close,
                            "volume": float(row.get("Volume", 0) or 0),
                            "vwap"  : close,
                        })
                    except (ValueError, TypeError):
                        continue
                if len(result) >= 2:
                    return result
        except Exception:
            pass

    # ── Fuente 3: Twelve Data ─────────────────────────────────
    if TWELVE_KEY:
        try:
            r = requests.get(
                "https://api.twelvedata.com/time_series",
                params={"symbol": sym, "interval": "1min", "outputsize": minutos + 5,
                        "format": "JSON", "apikey": TWELVE_KEY},
                timeout=8,
            )
            if r.status_code == 200:
                data   = r.json()
                values = data.get("values", [])
                if values:
                    result = []
                    for v in reversed(values):
                        try:
                            result.append({
                                "ts"    : datetime.now(ET),
                                "open"  : float(v.get("open",  0) or 0),
                                "high"  : float(v.get("high",  0) or 0),
                                "low"   : float(v.get("low",   0) or 0),
                                "close" : float(v.get("close", 0) or 0),
                                "volume": float(v.get("volume",0) or 0),
                                "vwap"  : float(v.get("close", 0) or 0),
                            })
                        except (ValueError, TypeError, KeyError):
                            continue
                    if len(result) >= 2:
                        return result
        except Exception:
            pass

    return []   # Sin datos disponibles


# ─────────────────────────────────────────────────────────────────────
#  INDICADORES TÉCNICOS
# ─────────────────────────────────────────────────────────────────────
def calc_vwap(bars: list) -> float:
    """VWAP = Σ(TP × Vol) / Σ(Vol). TP = (H+L+C)/3."""
    if not bars:
        return 0.0
    sum_pv = sum((b["high"]+b["low"]+b["close"])/3 * b["volume"] for b in bars)
    sum_v  = sum(b["volume"] for b in bars)
    return sum_pv / max(sum_v, 1e-9)


def calc_ema9_bars(bars: list) -> float:
    """EMA-9 de los cierres de las barras históricas."""
    if len(bars) < 2:
        return bars[-1]["close"] if bars else 0.0
    closes = [b["close"] for b in bars]
    k      = 2 / (9 + 1)
    ema    = closes[0]
    for c in closes[1:]:
        ema = c * k + ema * (1 - k)
    return ema


def calc_rvol(sym: str) -> float:
    """RVOL = vol vela actual / media vol barras históricas."""
    with _lock:
        bars     = shared["bars"].get(sym, [])
        vol_curr = shared["vol_curr"].get(sym, 0)
    if len(bars) < 3:
        return 1.0
    vols = [b["volume"] for b in bars if b.get("volume", 0) > 0]
    if not vols:
        return 1.0
    avg = sum(vols) / len(vols)
    return vol_curr / max(avg, 1)


def calc_roc(sym: str, precio: float, segundos: int = 60) -> float:
    """
    ROC (Rate of Change) = % cambio en los últimos `segundos`.
    Lee la rolling window tick-by-tick.
    """
    with _lock:
        rolls = list(shared["rolling5"].get(sym, deque()))
    if not rolls:
        return 0.0
    now = datetime.now(ET)
    precio_base = None
    for ts, price, _ in reversed(rolls):
        diff = (now - ts).total_seconds()
        if diff >= segundos * 0.85:
            precio_base = price
            break
    if precio_base is None or precio_base <= 0:
        return 0.0
    return (precio - precio_base) / precio_base * 100


def calc_hod_dist(sym: str, precio: float) -> float:
    with _lock:
        hod = shared["hod"].get(sym, precio)
    return (precio - hod) / max(hod, 1e-9) * 100


def calc_tape(sym: str, ventana: int = 10) -> float:
    """Ticks por segundo en los últimos `ventana` segundos."""
    with _lock:
        tape = list(shared["tape"].get(sym, deque()))
    if not tape:
        return 0.0
    now     = datetime.now(ET)
    recent  = [t for t in tape if (now - t).total_seconds() <= ventana]
    return len(recent) / ventana


# ─────────────────────────────────────────────────────────────────────
#  TRÍADA DE MOMENTUM — Motor de detección V101
# ─────────────────────────────────────────────────────────────────────
def evaluar_triada(sym: str, precio: float,
                   cambio_dia: float = 0.0) -> dict:
    """
    TRÍADA DE MOMENTUM (detección solo si convergen los 3):
      1. TENDENCIA ALCISTA : precio > VWAP  Y  precio > EMA-9
      2. LIQUIDEZ (RVOL)   : RVOL > cfg["rvol_min"]
      3. EXPLOSIÓN (ROC)   : ROC 1min o 5min > cfg["roc_min"]

    Force Meter 0-100 basado en la intensidad de cada factor.
    Solo genera alerta si los 3 factores están activos.
    """
    cfg = shared["cfg"]

    with _lock:
        bars  = shared["bars"].get(sym, [])
        ema9  = shared["ema9"].get(sym, precio)

    if not bars:
        return {"force":0,"triada":False,"det":{}}

    vwap     = calc_vwap(bars)
    rvol     = calc_rvol(sym)
    roc_1m   = calc_roc(sym, precio, 60)
    roc_5m   = calc_roc(sym, precio, 300)
    hod_dist = calc_hod_dist(sym, precio)
    tps      = calc_tape(sym, 10)

    force = 0
    det   = {}

    # ── FACTOR 1: TENDENCIA ALCISTA (30%) ────────────────────
    sobre_vwap = precio > vwap > 0
    sobre_ema  = precio > ema9 > 0
    tendencia_ok = sobre_vwap and sobre_ema

    if sobre_vwap and sobre_ema:
        force += 30
        det["📈 Tendencia"] = f"▲ Precio>{vwap:.4f} VWAP y >{ema9:.4f} EMA9 ✅"
    elif sobre_vwap:
        force += 15
        det["📈 Tendencia"] = f"→ Precio>{vwap:.4f} VWAP (sin EMA9)"
    elif sobre_ema:
        force += 10
        det["📈 Tendencia"] = f"→ Precio>{ema9:.4f} EMA9 (sin VWAP)"
    else:
        force -= 5
        det["📈 Tendencia"] = f"▼ Bajo VWAP y EMA9"

    # ── FACTOR 2: LIQUIDEZ / RVOL (30%) ──────────────────────
    rvol_ok = rvol >= cfg["rvol_min"]

    if rvol >= cfg["rvol_min"] * 2:
        force += 30; rvol_ok = True
        det["💥 RVOL"] = f"{rvol:.1f}x — EXPLOSIÓN ✅"
    elif rvol >= cfg["rvol_min"]:
        force += 20; rvol_ok = True
        det["💥 RVOL"] = f"{rvol:.1f}x — Alto ✅"
    elif rvol >= cfg["rvol_min"] * 0.7:
        force += 10
        det["💥 RVOL"] = f"{rvol:.1f}x — Moderado"
    else:
        det["💥 RVOL"] = f"{rvol:.1f}x — Bajo"

    # ── FACTOR 3: EXPLOSIÓN / ROC (30%) ──────────────────────
    roc_ok  = roc_1m >= cfg["roc_min"] or roc_5m >= cfg["roc_min"]
    roc_max = max(abs(roc_1m), abs(roc_5m))

    if roc_1m >= cfg["roc_min"] * 2:
        force += 30; roc_ok = True
        det["🚀 ROC"] = f"1min +{roc_1m:.2f}% / 5min +{roc_5m:.2f}% — COHETE ✅"
    elif roc_ok:
        force += 18
        det["🚀 ROC"] = f"1min {roc_1m:+.2f}% / 5min {roc_5m:+.2f}% ✅"
    elif roc_max >= cfg["roc_min"] * 0.5:
        force += 8
        det["🚀 ROC"] = f"1min {roc_1m:+.2f}% / 5min {roc_5m:+.2f}%"
    else:
        det["🚀 ROC"] = f"1min {roc_1m:+.2f}% / 5min {roc_5m:+.2f}% (bajo)"

    # ── FACTORES EXTRAS (10%) ────────────────────────────────
    hod_break = hod_dist >= 0
    if hod_break:
        force += 8
        det["🔴 HOD"] = f"¡RUPTURA HOD! +{hod_dist:.2f}%"
    elif hod_dist >= -cfg["hod_dist"]:
        force += 4
        det["🔴 HOD"] = f"Cerca HOD: {hod_dist:.2f}%"
    else:
        det["🔴 HOD"] = f"HOD: {hod_dist:.2f}%"

    if tps >= 3:
        force += 5
        det["🎯 Tape"] = f"{tps:.1f}t/s — Masivo"
    elif tps >= 1:
        force += 2
        det["🎯 Tape"] = f"{tps:.1f}t/s"

    if cambio_dia >= 15:   force += 5; det["Δ Día"] = f"+{cambio_dia:.1f}% TOP"
    elif cambio_dia >= 5:  force += 2; det["Δ Día"] = f"+{cambio_dia:.1f}%"

    force = max(0, min(100, force))

    # Tríada completa: los 3 factores deben estar activos
    triada = tendencia_ok and rvol_ok and roc_ok

    return {
        "force"     : force,
        "triada"    : triada,
        "tendencia" : tendencia_ok,
        "rvol_ok"   : rvol_ok,
        "roc_ok"    : roc_ok,
        "hod_break" : hod_break,
        "vwap"      : vwap,
        "ema9"      : ema9,
        "rvol"      : rvol,
        "roc_1m"    : roc_1m,
        "roc_5m"    : roc_5m,
        "tps"       : tps,
        "hod_dist"  : hod_dist,
        "det"       : det,
    }


# ─────────────────────────────────────────────────────────────────────
#  MODO SIMULACIÓN — datos ficticios volátiles
# ─────────────────────────────────────────────────────────────────────
SIM_TICKERS = ["AAPL","TSLA","NVDA","GME","AMC","MSTR","SOFI","PLTR",
                "RIVN","COIN","HOOD","MARA","RIOT","NIO","XPEV","SNDL"]

def _inyectar_sim():
    """
    Inyecta datos ficticios volátiles en shared_state
    para probar la UI y las alertas cuando el mercado está cerrado.
    """
    now   = datetime.now(ET)
    for sym in SIM_TICKERS:
        base  = random.uniform(1.5, 80.0)
        noise = random.uniform(-0.05, 0.12)
        precio = round(base * (1 + noise), 4)

        # Generar barras sintéticas (últimas 20 velas de 1min)
        bars = []
        p    = precio * 0.88
        for i in range(20):
            o = p
            c = p * (1 + random.uniform(-0.015, 0.025))
            h = max(o, c) * (1 + random.uniform(0, 0.008))
            l = min(o, c) * (1 - random.uniform(0, 0.008))
            v = random.uniform(50_000, 800_000)
            bars.append({"ts":now-timedelta(minutes=20-i),"open":o,"high":h,
                          "low":l,"close":c,"volume":v,"vwap":c})
            p = c

        # Rolling window con spikes
        if sym not in shared["rolling5"]:
            shared["rolling5"][sym] = deque(maxlen=600)
        for i in range(50):
            ts_r = now - timedelta(seconds=300 - i*6)
            p_r  = precio * (0.95 + i * 0.001 + random.uniform(0, 0.002))
            shared["rolling5"][sym].append((ts_r, p_r, random.uniform(1000, 8000)))

        # Tape speed alto (simula actividad)
        if sym not in shared["tape"]:
            shared["tape"][sym] = deque(maxlen=200)
        for i in range(random.randint(5, 25)):
            shared["tape"][sym].append(now - timedelta(seconds=random.uniform(0, 10)))

        shared["prices"][sym]   = precio
        shared["hod"][sym]      = precio * random.uniform(0.98, 1.03)
        shared["lod"][sym]      = precio * random.uniform(0.88, 0.97)
        shared["open_day"][sym] = precio * random.uniform(0.85, 0.99)
        shared["vol_curr"][sym] = random.uniform(100_000, 2_000_000)
        shared["open_1m"][sym]  = precio * (1 - random.uniform(0, 0.02))
        shared["bars"][sym]     = bars
        shared["ema9"][sym]     = calc_ema9_bars(bars)

        # Evaluar y generar alertas simuladas
        ev = evaluar_triada(sym, precio, random.uniform(2, 30))
        if ev["force"] >= shared["cfg"]["min_force"]:
            _generar_alerta(sym, precio, ev, now, sim=True)

        # Ranking Top 5min
        roc5 = calc_roc(sym, precio, 300)
        _actualizar_ranking(sym, precio, ev, roc5)


def _sim_loop():
    """Hilo que inyecta datos simulados cada 8 segundos."""
    while True:
        try:
            if shared["cfg"].get("sim_mode"):
                with _lock:
                    _inyectar_sim()
                with _lock:
                    shared["audio"] = "sim"
        except Exception:
            pass
        time.sleep(8)

@st.cache_resource
def _start_sim_thread():
    t = threading.Thread(target=_sim_loop, daemon=True, name="sim-loop")
    t.start()
    return t
_sim_thread = _start_sim_thread()


# ─────────────────────────────────────────────────────────────────────
#  WEBSOCKET CALLBACKS
# ─────────────────────────────────────────────────────────────────────
async def _on_bar(bar):
    sym = bar.symbol
    now = datetime.now(ET)
    close  = float(bar.close  or 0)
    high   = float(bar.high   or 0)
    volume = float(bar.volume or 0)

    with _lock:
        if sym not in shared["bars"]:
            shared["bars"][sym] = []
        shared["bars"][sym].append({
            "ts": bar.timestamp, "open": float(bar.open or 0),
            "high": high, "low": float(bar.low or 0),
            "close": close, "volume": volume,
            "vwap": float(bar.vwap or close),
        })
        if len(shared["bars"][sym]) > 60:
            shared["bars"][sym].pop(0)

        # Actualizar EMA-9 incremental
        k = 2 / (9 + 1)
        ema_prev = shared["ema9"].get(sym, close)
        shared["ema9"][sym] = close * k + ema_prev * (1 - k)

        # HOD / LOD
        hod = shared["hod"].get(sym, high)
        if high > hod: shared["hod"][sym] = high
        if sym not in shared["lod"] or float(bar.low or 0) < shared["lod"][sym]:
            shared["lod"][sym] = float(bar.low or close)

        shared["open_1m"][sym]  = float(bar.open or close)
        shared["vol_curr"][sym] = 0
        shared["ws_ticks"] += 1
        shared["ws_last"]   = now


async def _on_trade(trade):
    sym    = trade.symbol
    precio = float(trade.price or 0)
    vol    = float(trade.size  or 0)
    now    = datetime.now(ET)

    if precio <= 0:
        return

    cfg = shared["cfg"]
    if not (cfg["precio_min"] <= precio <= cfg["precio_max"]):
        return

    with _lock:
        shared["prices"][sym]      = precio
        shared["vol_curr"][sym]    = shared["vol_curr"].get(sym, 0) + vol
        if sym not in shared["rolling5"]:
            shared["rolling5"][sym] = deque(maxlen=600)
        shared["rolling5"][sym].append((now, precio, vol))
        if sym not in shared["tape"]:
            shared["tape"][sym] = deque(maxlen=200)
        shared["tape"][sym].append(now)
        hod = shared["hod"].get(sym, precio)
        if precio > hod: shared["hod"][sym] = precio
        if sym not in shared["lod"]: shared["lod"][sym] = precio
        if precio < shared["lod"].get(sym, precio): shared["lod"][sym] = precio
        if sym not in shared["open_day"]: shared["open_day"][sym] = precio
        shared["ws_ticks"] += 1
        shared["ws_last"]   = now

    # Evaluar Tríada (fuera del lock)
    op = shared["open_day"].get(sym, precio)
    cd = (precio - op) / max(op, 1e-9) * 100 if op > 0 else 0
    ev = evaluar_triada(sym, precio, cd)

    roc5 = calc_roc(sym, precio, 300)
    _actualizar_ranking(sym, precio, ev, roc5)

    if ev["force"] >= cfg["min_force"]:
        _generar_alerta(sym, precio, ev, now)


async def _on_error(err):
    with _lock:
        shared["ws_status"] = f"ERROR: {str(err)[:60]}"


def _generar_alerta(sym: str, precio: float, ev: dict,
                     ts: datetime, sim: bool = False):
    """Genera alerta evitando duplicados en 90 segundos."""
    with _lock:
        alertas  = shared["alertas"]
        ts_limit = datetime.now(ET) - timedelta(seconds=90)

        dup = any(
            a["ticker"] == sym and a.get("ts_dt", ts_limit) > ts_limit
            for a in alertas
        )
        if dup:
            return

        alerta = {
            "ticker"    : sym,
            "ts"        : ts.strftime("%H:%M:%S ET"),
            "ts_dt"     : ts,
            "precio"    : precio,
            "force"     : ev["force"],
            "triada"    : ev.get("triada", False),
            "tendencia" : ev.get("tendencia", False),
            "rvol_ok"   : ev.get("rvol_ok", False),
            "roc_ok"    : ev.get("roc_ok", False),
            "hod_break" : ev.get("hod_break", False),
            "rvol"      : ev.get("rvol", 1),
            "roc_1m"    : ev.get("roc_1m", 0),
            "roc_5m"    : ev.get("roc_5m", 0),
            "tps"       : ev.get("tps", 0),
            "hod_dist"  : ev.get("hod_dist", 0),
            "vwap"      : ev.get("vwap", precio),
            "ema9"      : ev.get("ema9", precio),
            "det"       : ev.get("det", {}),
            "sim"       : sim,
        }
        shared["alertas"].insert(0, alerta)
        shared["alertas"] = shared["alertas"][:30]
        shared["audio"]   = "triple" if ev.get("triada") else ("sim" if sim else "normal")


def _actualizar_ranking(sym: str, precio: float, ev: dict, roc5: float):
    """Actualiza el Top 5min Ranking."""
    roc1 = ev.get("roc_1m", 0)
    with _lock:
        entry = {
            "ticker"  : sym,
            "precio"  : precio,
            "roc5"    : roc5,
            "roc1"    : roc1,
            "rvol"    : ev.get("rvol", 1),
            "force"   : ev.get("force", 0),
            "triada"  : ev.get("triada", False),
            "ts"      : datetime.now(ET).strftime("%H:%M:%S"),
        }
        rank = shared["ranking5"]
        idx  = next((i for i, r in enumerate(rank) if r["ticker"] == sym), -1)
        if idx >= 0:
            rank[idx] = entry
        else:
            rank.append(entry)
        shared["ranking5"] = sorted(rank, key=lambda x: -x["roc5"])[:25]


# ─────────────────────────────────────────────────────────────────────
#  WEBSOCKET MANAGER
# ─────────────────────────────────────────────────────────────────────
class WSManager:
    def __init__(self):
        self._thread  = None
        self._loop    = None
        self._stream  = None
        self._running = False

    def start(self, tickers: list):
        if self._running and self._thread and self._thread.is_alive():
            self.update(tickers)
            return
        with _lock:
            shared["ws_status"]  = "CONECTANDO..."
            shared["ws_tickers"] = list(tickers)
        self._running = True
        self._thread  = threading.Thread(
            target=self._run, args=(list(tickers),),
            daemon=True, name="v101-ws",
        )
        self._thread.start()

    def _run(self, tickers):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect(tickers))
        except Exception as e:
            with _lock:
                shared["ws_status"] = f"CAÍDO: {str(e)[:60]}"
            self._running = False

    async def _connect(self, tickers):
        try:
            self._stream = StockDataStream(ALPACA_KEY, ALPACA_SECRET, feed="iex")
            if tickers:
                self._stream.subscribe_bars(_on_bar, *tickers)
                self._stream.subscribe_trades(_on_trade, *tickers)
            with _lock:
                shared["ws_status"] = "🟢 EN VIVO"
            await self._stream._run_forever()
        except Exception as e:
            with _lock:
                shared["ws_status"] = f"DESCONECTADO: {str(e)[:50]}"
            self._running = False

    def update(self, new_tickers: list):
        with _lock:
            current = set(shared["ws_tickers"])
            nuevo   = set(new_tickers)
            to_add  = list(nuevo - current)
            shared["ws_tickers"] = list(nuevo)
        if to_add and self._stream and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._sub_more(to_add), self._loop)

    async def _sub_more(self, tickers):
        if self._stream and tickers:
            try:
                self._stream.subscribe_bars(_on_bar, *tickers)
                self._stream.subscribe_trades(_on_trade, *tickers)
            except Exception:
                pass

    def is_alive(self):
        return bool(self._thread and self._thread.is_alive())


@st.cache_resource
def _get_ws():
    return WSManager()
ws = _get_ws()


# ─────────────────────────────────────────────────────────────────────
#  SABUESO — Hilo de actualización dinámica cada 30s
# ─────────────────────────────────────────────────────────────────────
def _sabueso_loop():
    """
    Busca top movers cada 30 segundos usando la cascada de datos.
    Actualiza la suscripción del WebSocket sin interrumpirlo.
    """
    while True:
        try:
            if not shared["cfg"].get("sim_mode"):
                with _lock:
                    shared["sabueso_st"] = "🔍 Buscando movers..."
                nuevos = obtener_top_movers(80)
                if nuevos:
                    with _lock:
                        actuales  = set(shared["ws_tickers"])
                        watchlist = set(shared["watchlist"].keys())
                        combinado = list(actuales | set(nuevos) | watchlist)[:100]
                        shared["sabueso_tk"] = nuevos
                        shared["sabueso_ts"] = datetime.now(ET)
                        shared["sabueso_st"] = f"✅ {len(nuevos)} movers"
                    if ws.is_alive():
                        ws.update(combinado)
        except Exception as e:
            with _lock:
                shared["sabueso_st"] = f"⚠️ {str(e)[:40]}"
        time.sleep(30)

@st.cache_resource
def _start_sabueso():
    t = threading.Thread(target=_sabueso_loop, daemon=True, name="sabueso")
    t.start()
    return t
_sab = _start_sabueso()


# ─────────────────────────────────────────────────────────────────────
#  WATCHLIST MANUAL — evaluación instantánea
# ─────────────────────────────────────────────────────────────────────
def evaluar_ticker_manual(sym: str) -> dict:
    """
    Descarga historial, inicializa shared_state y aplica la Tríada.
    Clasifica: SETUP IDEAL (>=70), POTENCIAL (>=45), EVITAR (<45).
    """
    bars = obtener_historial(sym, 20)

    if not bars:
        return {"sym": sym, "force": 0, "setup": "SIN DATOS", "precio": 0, "error": True}

    precio = bars[-1]["close"]
    if precio <= 0:
        return {"sym": sym, "force": 0, "setup": "SIN PRECIO", "precio": 0, "error": True}

    with _lock:
        shared["bars"][sym]    = bars
        shared["prices"][sym]  = precio
        shared["hod"][sym]     = max(b["high"]  for b in bars)
        shared["lod"][sym]     = min(b["low"]   for b in bars)
        shared["open_day"][sym]= bars[0]["open"]
        shared["ema9"][sym]    = calc_ema9_bars(bars)
        shared["vol_curr"][sym]= bars[-1]["volume"]
        if sym not in shared["rolling5"]:
            shared["rolling5"][sym] = deque(maxlen=600)
        now = datetime.now(ET)
        for b in bars:
            ts_b = b.get("ts", now)
            if not isinstance(ts_b, datetime):
                ts_b = now
            shared["rolling5"][sym].append((ts_b, b["close"], b["volume"]))

    op  = bars[0]["open"]
    cd  = (precio - op) / max(op, 1e-9) * 100 if op > 0 else 0
    ev  = evaluar_triada(sym, precio, cd)
    f   = ev["force"]
    setup = "SETUP IDEAL" if f>=70 else ("POTENCIAL" if f>=45 else "EVITAR")

    return {
        "sym"       : sym,
        "force"     : f,
        "setup"     : setup,
        "precio"    : precio,
        "roc_1m"    : ev.get("roc_1m",0),
        "roc_5m"    : ev.get("roc_5m",0),
        "rvol"      : ev.get("rvol",1),
        "tendencia" : ev.get("tendencia",False),
        "rvol_ok"   : ev.get("rvol_ok",False),
        "roc_ok"    : ev.get("roc_ok",False),
        "hod_dist"  : ev.get("hod_dist",0),
        "tps"       : ev.get("tps",0),
        "cambio_dia": cd,
        "det"       : ev.get("det",{}),
        "error"     : False,
    }

def agregar_watchlist(texto: str):
    syms = [s.strip().upper() for s in texto.split(",") if s.strip()]
    for sym in syms:
        if not sym or not sym.isalpha() or not (1<len(sym)<=5):
            continue
        ev = evaluar_ticker_manual(sym)
        with _lock:
            shared["watchlist"][sym] = ev
    ws.update(list(set(shared["ws_tickers"]) | set(syms)))


# ─────────────────────────────────────────────────────────────────────
#  SL / TP Y ÓRDENES
# ─────────────────────────────────────────────────────────────────────
def calc_sltp(sym: str, precio: float,
              atr_mult: float = 2.0, min_rr: float = 2.0) -> dict:
    with _lock:
        bars = shared["bars"].get(sym, [])
    try:
        if len(bars) >= 5:
            tr_list = []
            for i in range(1, len(bars)):
                hl = bars[i]["high"] - bars[i]["low"]
                hc = abs(bars[i]["high"] - bars[i-1]["close"])
                lc = abs(bars[i]["low"]  - bars[i-1]["close"])
                tr_list.append(max(hl, hc, lc))
            atr = sum(tr_list[-14:]) / max(len(tr_list[-14:]), 1)
            sup = min(b["low"] for b in bars[-10:])
        else:
            atr = precio * 0.015
            sup = precio * 0.97
        sl     = round(max(precio - atr*atr_mult, sup*0.998, precio*0.92), 4)
        riesgo = max(precio - sl, 1e-9)
        tp     = round(precio + riesgo * min_rr, 4)
        rr     = round((tp - precio) / riesgo, 2)
        return {"sl": sl, "tp": tp, "rr": rr, "atr": round(atr, 4)}
    except (ZeroDivisionError, ValueError, KeyError):
        return {"sl": round(precio*0.97,4), "tp": round(precio*1.06,4),
                "rr": 2.0, "atr": round(precio*0.015,4)}


def comprar_market(sym: str, usd: float, sl: float, tp: float) -> tuple:
    """Market order por valor en USD. Qty = floor(usd / precio)."""
    if not trading:
        return False, "❌ Alpaca no disponible"
    with _lock:
        precio = shared["prices"].get(sym, 0)
    if precio <= 0:
        return False, f"❌ Sin precio para {sym}"
    qty = max(1, int(usd // precio))
    try:
        trading.submit_order(MarketOrderRequest(
            symbol=sym, qty=qty, side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC,
            take_profit=TakeProfitRequest(limit_price=round(tp, 2)),
            stop_loss=StopLossRequest(stop_price=round(sl, 2)),
        ))
        return True, f"✅ MARKET BUY {qty}x {sym} (≈${usd:,.0f}) | SL=${sl:.4f} TP=${tp:.4f}"
    except Exception as e:
        return False, f"❌ {e}"


def vender_market(sym: str, qty: int) -> tuple:
    if not trading:
        return False, "❌ Alpaca no disponible"
    try:
        trading.submit_order(MarketOrderRequest(
            symbol=sym, qty=qty, side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC))
        return True, f"✅ SELL MARKET {qty}x {sym}"
    except Exception as e:
        return False, f"❌ {e}"


def get_account():
    if not trading: return None
    try:    return trading.get_account()
    except: return None

def get_positions():
    if not trading: return []
    try:    return trading.get_all_positions()
    except: return []


# ─────────────────────────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────────────────────────
def fbar(force: int, triada: bool = False) -> str:
    color = ("#ff0000" if triada else
             "#ff4500" if force>=80 else
             "#ff8c00" if force>=65 else
             "#ffc107" if force>=45 else "#374151")
    emoji = "🔥" * (force // 30)
    label = f"{emoji} {force}/100"
    return (f'<div class="fbar-bg">'
            f'<div class="fbar-fill" style="width:{force}%;background:{color}">{label}</div>'
            f'</div>')

def badges_triada(t: bool, r: bool, roc: bool) -> str:
    def b(ok, txt, cls):
        return f'<span class="bx {cls}">{"✅" if ok else "—"} {txt}</span>'
    return (b(t,"TENDENCIA","bx-vwap") +
            b(r,"RVOL","bx-rvol") +
            b(roc,"ROC","bx-roc"))


# ─────────────────────────────────────────────────────────────────────
#  ══════════════════ INTERFAZ PRINCIPAL ══════════════════
# ─────────────────────────────────────────────────────────────────────
st.markdown('<h1 class="hdr">⚡ THUNDER RADAR V101</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub">TRÍADA MOMENTUM · CASCADA FAILOVER · WEBSOCKET · PAPER TRADING</p>',
            unsafe_allow_html=True)

SESSION = get_session()
bm = {"REGULAR":"b-reg","PRE-MARKET":"b-pre","AFTER-HOURS":"b-aft","CERRADO":"b-cls"}
hora_et = datetime.now(ET).strftime("%H:%M:%S ET")
cuenta  = get_account()

h1, h2, h3 = st.columns(3)
with h1:
    ws_st = shared["ws_status"]
    dot_c = "dot-green" if "🟢" in ws_st else "dot-red"
    st.markdown(
        f'<span class="badge {bm.get(SESSION,"b-cls")}">● {SESSION}</span>'
        f' &nbsp;<span class="{dot_c} dot"></span>'
        f'<span style="color:#8b949e;font-size:.71em">WS: {ws_st}</span>',
        unsafe_allow_html=True)
with h2:
    sab   = shared["sabueso_st"]
    fuente= shared["fuente_data"]
    st.markdown(f'<span style="color:#8b949e">🕐 {hora_et}</span><br>'
                f'<span style="color:#8b949e;font-size:.70em">🐕 {sab} | {fuente}</span>',
                unsafe_allow_html=True)
with h3:
    if cuenta:
        eq  = float(cuenta.equity or 0)
        pnl = eq - float(cuenta.last_equity or eq)
        col = "#00ff88" if pnl >= 0 else "#ff4444"
        st.markdown(f'<span style="color:{col}">💰 ${eq:,.2f} | P&L {pnl:+,.2f}</span>',
                    unsafe_allow_html=True)

# ── AUDIO TRIGGER ────────────────────────────────────────────────────
audio_tipo = shared.get("audio", "0")
if audio_tipo != "0":
    st.markdown(
        f'<script>const el=document.getElementById("audio-trigger");'
        f'if(el){{el.dataset.tipo="{audio_tipo}";}}</script>',
        unsafe_allow_html=True)
    with _lock:
        shared["audio"] = "0"

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  BARRA LATERAL
# ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ THUNDER RADAR V101")

    # Modo Simulación
    sim_mode = st.toggle("🟠 MODO SIMULACIÓN (testing out-of-hours)", value=False)
    with _lock:
        shared["cfg"]["sim_mode"] = sim_mode

    if sim_mode:
        st.markdown('<div class="sim-banner">⚠️ MODO SIMULACIÓN ACTIVO</div>',
                    unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**📡 Control WebSocket**")
    if st.button("🚀 INICIAR SISTEMA COMPLETO", use_container_width=True):
        if not sim_mode:
            with st.spinner("Obteniendo top movers..."):
                init_t = obtener_top_movers(80)
            ws.start(init_t)
            with _lock:
                shared["ws_tickers"] = init_t
            st.success(f"✅ {len(init_t)} tickers | WebSocket iniciado")
        else:
            st.info("Modo simulación: WebSocket no necesario.")

    n_ws = len(shared["ws_tickers"])
    n_tk = shared["ws_ticks"]
    st.markdown(f'<span style="color:#8b949e;font-size:.73em">'
                f'{n_ws} tickers | {n_tk:,} ticks</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**💰 Filtros**")
    pm  = st.number_input("Precio Mín $", value=1.0,   step=0.5,  min_value=0.01)
    pM  = st.number_input("Precio Máx $", value=500.0, step=10.0, max_value=9999.0)

    st.markdown("**🔺 Tríada de Momentum**")
    rv  = st.slider("RVOL mínimo",        1.5, 10.0, 2.5, 0.5,
                     help="Volumen relativo. 2.5 = 250% del promedio")
    roc = st.slider("ROC mínimo % (1min)", 0.5, 10.0, 1.5, 0.5,
                     help="Rate of Change mínimo en el último minuto")
    hod = st.slider("HOD dist. máx %",    0.1,  5.0, 1.0, 0.1,
                     help="Distancia máxima al máximo del día")
    mf  = st.slider("Force mínimo alerta",  30, 95, 60, 5)

    st.markdown("**🔒 Gestión Riesgo**")
    atr_m = st.slider("ATR × SL",  0.5, 4.0, 2.0, 0.5)
    rr_m  = st.slider("R:R mínimo",1.5, 4.0, 2.0, 0.5)
    usd_t = st.number_input("$ por trade",value=2000,min_value=100,step=100)

    auto_ref_s = st.toggle("🔁 Auto-refresh (8 seg)", value=True)

# Actualizar config dinámica
with _lock:
    shared["cfg"].update({
        "precio_min": pm,   "precio_max": pM,
        "rvol_min"  : rv,   "roc_min"   : roc,
        "hod_dist"  : hod,  "min_force" : mf,
        "trade_usd" : float(usd_t),
        "sim_mode"  : sim_mode,
    })

# ─────────────────────────────────────────────────────────────────────
#  MODO SIMULACIÓN — Banner prominente
# ─────────────────────────────────────────────────────────────────────
if sim_mode:
    st.markdown("""
    <div class="sim-banner">
    🟠 MODO SIMULACIÓN ACTIVO — Datos ficticios volátiles inyectados cada 8 seg
    para probar la UI, alertas y audio. Sin órdenes reales.
    </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  MANUAL SCANNER — entrada de tickers
# ─────────────────────────────────────────────────────────────────────
st.subheader("🔍 Manual Scanner — Evaluación Instantánea de Tickers")

mc1, mc2 = st.columns([3, 1])
with mc1:
    ticker_in = st.text_input("Ingresa tickers separados por coma",
                               placeholder="AAPL, TSLA, GME, NVDA ...",
                               label_visibility="collapsed", key="t_input")
with mc2:
    if st.button("➕ EVALUAR AHORA", use_container_width=True):
        if ticker_in.strip():
            with st.spinner("📡 Analizando..."):
                agregar_watchlist(ticker_in)
            st.rerun()

if st.button("🗑️ Limpiar Manual Scanner", use_container_width=False):
    with _lock:
        shared["watchlist"] = {}
    st.rerun()

with _lock:
    wl_items = list(shared["watchlist"].items())

if wl_items:
    for sym, ev_old in wl_items:
        with _lock:
            precio_ws = shared["prices"].get(sym, ev_old.get("precio", 0))
        if precio_ws > 0:
            cd  = ev_old.get("cambio_dia", 0)
            ev2 = evaluar_triada(sym, precio_ws, cd)
            f   = ev2["force"]
            roc1= ev2.get("roc_1m", 0)
            roc5= ev2.get("roc_5m", 0)
            rvol= ev2.get("rvol", 1)
        else:
            f    = ev_old.get("force", 0)
            ev2  = ev_old
            roc1 = ev_old.get("roc_1m", 0)
            roc5 = ev_old.get("roc_5m", 0)
            rvol = ev_old.get("rvol", 1)

        setup = "SETUP IDEAL" if f>=70 else ("POTENCIAL" if f>=45 else "EVITAR")
        sc    = "#00ff88" if f>=70 else ("#ffc107" if f>=45 else "#ff4444")
        card  = "card-hot" if f>=70 else ("card-mid" if f>=45 else "card-cold")
        fb    = fbar(f, ev2.get("triada", False))
        bdg   = badges_triada(ev2.get("tendencia",False),
                               ev2.get("rvol_ok",False),
                               ev2.get("roc_ok",False))
        orden = calc_sltp(sym, precio_ws, atr_m, rr_m)

        col_m1, col_m2 = st.columns([4, 1])
        with col_m1:
            st.markdown(f"""
            <div class="{card}">
              <span class="tkr">{sym}</span>
              &nbsp;&nbsp;
              <span style="color:{sc};font-size:1.5em;font-weight:900">{f}/100</span>
              &nbsp;&nbsp;
              <b style="color:{sc}">{setup}</b>
              &nbsp;&nbsp;{bdg}
              <br>{fb}<br>
              <span class="lbl">Precio</span> <b style="color:#fff">${precio_ws:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">ROC 1min</span>
              <b style="color:{'#00ff88' if roc1>=0 else '#ff4444'}">{roc1:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">ROC 5min</span>
              <b style="color:{'#00ff88' if roc5>=0 else '#ff4444'}">{roc5:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">RVOL</span> {rvol:.1f}x
              &nbsp;|&nbsp;
              <span class="lbl">HOD</span> {ev2.get('hod_dist',0):+.2f}%
              &nbsp;|&nbsp;
              <span class="lbl">VWAP</span> ${ev2.get('vwap',0):.4f}
              &nbsp;|&nbsp;
              <span class="lbl">EMA9</span> ${ev2.get('ema9',0):.4f}
              <br>
              <span class="lbl">SL</span> <b style="color:#ff6b6b">${orden['sl']:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">TP</span> <b style="color:#00ff88">${orden['tp']:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">R:R</span> 1:{orden['rr']}
              &nbsp;|&nbsp;
              <span class="lbl">ATR</span> ${orden['atr']:.4f}
            </div>""", unsafe_allow_html=True)
        with col_m2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"🟢 Comprar\n{sym}", key=f"buy_m_{sym}",
                         use_container_width=True):
                ok, msg = comprar_market(sym, usd_t, orden["sl"], orden["tp"])
                st.success(msg) if ok else st.error(msg)
            if st.button(f"🗑️ {sym}", key=f"del_m_{sym}",
                         use_container_width=True):
                with _lock:
                    shared["watchlist"].pop(sym, None)
                st.rerun()

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  ALERT WINDOW — Tríada de Momentum (automático)
# ─────────────────────────────────────────────────────────────────────
with _lock:
    alertas_now = list(shared["alertas"])

n_triada = sum(1 for a in alertas_now if a.get("triada"))
n_sim    = sum(1 for a in alertas_now if a.get("sim"))
st.subheader(
    f"🚨 Alert Window — {len(alertas_now)} alertas "
    f"({n_triada} Tríada Completa | {n_sim} simuladas)"
)

if alertas_now:
    for al in alertas_now[:12]:
        triada = al.get("triada", False)
        sim    = al.get("sim", False)
        card   = ("card-sim" if sim else
                  "card-triple" if triada else "card-mid")
        f      = al["force"]
        fb     = fbar(f, triada)
        bdg    = badges_triada(al.get("tendencia",False),
                                al.get("rvol_ok",False),
                                al.get("roc_ok",False))
        rc1    = al.get("roc_1m", 0)
        rc5    = al.get("roc_5m", 0)
        orden  = calc_sltp(al["ticker"], al["precio"], atr_m, rr_m)

        col_a1, col_a2 = st.columns([4, 1])
        with col_a1:
            sim_txt = ' <span class="b-sim" style="padding:1px 6px;border-radius:3px;font-size:.66em">SIM</span>' if sim else ""
            st.markdown(f"""
            <div class="{card}">
              <span class="tkr">{'🚨' if triada else '⚡'} {al['ticker']}</span>
              {sim_txt}
              &nbsp;&nbsp;
              <span class="{'s10' if f>=80 else 's8' if f>=65 else 's6'}">{f}/100</span>
              &nbsp;&nbsp;
              <span style="color:#8b949e;font-size:.76em">{al['ts']}</span>
              &nbsp;&nbsp;{bdg}
              <br>{fb}<br>
              <span class="lbl">Precio</span> <b style="color:#fff">${al['precio']:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">ROC 1min</span>
              <b style="color:{'#00ff88' if rc1>=0 else '#ff4444'}">{rc1:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">ROC 5min</span>
              <b style="color:{'#00ff88' if rc5>=0 else '#ff4444'}">{rc5:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">RVOL</span>
              <b style="color:{'#ff4500' if al['rvol']>=5 else '#ff8c00' if al['rvol']>=2.5 else '#ffc107'}">{al['rvol']:.1f}x</b>
              &nbsp;|&nbsp;
              <span class="lbl">HOD</span>
              <b style="color:{'#ff4500' if al['hod_dist']>=0 else '#8b949e'}">{al['hod_dist']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">Tape</span> {al['tps']:.1f}t/s
              <br>
              <span class="lbl">SL</span> <b style="color:#ff6b6b">${orden['sl']:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">TP</span> <b style="color:#00ff88">${orden['tp']:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">R:R</span> 1:{orden['rr']}
              &nbsp;|&nbsp;
              <span class="lbl">VWAP</span> ${al.get('vwap',0):.4f}
              &nbsp;|&nbsp;
              <span class="lbl">EMA9</span> ${al.get('ema9',0):.4f}
            </div>""", unsafe_allow_html=True)
        with col_a2:
            st.markdown("<br>", unsafe_allow_html=True)
            key_btn = f"buy_a_{al['ticker']}_{al['ts'].replace(':','').replace(' ','')}"
            if st.button(f"🟢 Comprar\n{al['ticker']}\n≈${usd_t:,.0f}",
                         key=key_btn, use_container_width=True):
                if not sim:
                    ok, msg = comprar_market(al["ticker"],usd_t,orden["sl"],orden["tp"])
                    st.success(msg) if ok else st.error(msg)
                else:
                    st.info("Modo sim: sin orden real.")
else:
    if sim_mode:
        st.markdown("""<div class="ibox-ok">
        🟠 Modo simulación activo — generando datos ficticios cada 8 seg.
        Las alertas aparecerán aquí cuando el Force Meter supere el umbral configurado.
        </div>""", unsafe_allow_html=True)
    elif ws.is_alive():
        st.markdown("""<div class="ibox">
        🟡 WebSocket activo — esperando señales de Tríada de Momentum...<br>
        <b>Condiciones:</b> Precio > VWAP y EMA9 (Tendencia) +
        RVOL alto (Liquidez) + ROC explosivo (Ignición).
        </div>""", unsafe_allow_html=True)
    else:
        st.info("Pulsa **🚀 INICIAR SISTEMA** o activa el **Modo Simulación** para comenzar.")

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  TOP 5MIN RANKING
# ─────────────────────────────────────────────────────────────────────
with _lock:
    ranking_now = list(shared["ranking5"])

st.subheader(f"📈 Top 5min Ranking — {len(ranking_now)} stocks activos")

if ranking_now:
    rows = []
    for i, r in enumerate(ranking_now[:20]):
        medallas = ["🥇","🥈","🥉"] + [""] * 17
        rows.append({
            "#"         : f"{medallas[i]}{i+1}",
            "Ticker"    : r["ticker"],
            "Precio $"  : round(r["precio"], 4),
            "ROC 5min %" : round(r["roc5"], 2),
            "ROC 1min %" : round(r["roc1"], 2),
            "RVOL"      : round(r["rvol"], 1),
            "Force"     : r["force"],
            "Tríada"    : "🚨" if r.get("triada") else "—",
            "Hora"      : r.get("ts", "—"),
        })
    df_r = pd.DataFrame(rows)
    def cv(v): return f"color:{'#00ff88' if v>=0 else '#ff4444'};font-weight:bold"
    def cf(v):
        if v>=80: return "background-color:#7f1d1d;color:#ff4500;font-weight:900"
        elif v>=65: return "background-color:#78350f;color:#ffc107"
        elif v>=45: return "background-color:#1a2535"
        else: return "color:#8b949e"
    def cr(v):
        if v>=5: return "color:#ff4500;font-weight:900"
        elif v>=2.5: return "color:#ff8c00;font-weight:700"
        elif v>=1.5: return "color:#ffc107"
        else: return "color:#8b949e"
    fmt = {"Precio $":"${:.4f}","ROC 5min %":"{:+.2f}%",
           "ROC 1min %":"{:+.2f}%","RVOL":"{:.1f}x","Force":"{:.0f}"}
    try:
        styled = (df_r.style
                  .map(cv, subset=["ROC 5min %","ROC 1min %"])
                  .map(cf, subset=["Force"])
                  .map(cr, subset=["RVOL"])
                  .format(fmt))
    except Exception:
        try:
            styled = (df_r.style
                      .applymap(cv, subset=["ROC 5min %","ROC 1min %"])
                      .applymap(cf, subset=["Force"])
                      .applymap(cr, subset=["RVOL"])
                      .format(fmt))
        except Exception:
            styled = df_r.style.format(fmt)
    st.dataframe(styled, use_container_width=True, hide_index=True, height=360)

    # Compra 1-clic para el Top 5
    st.markdown("**⚡ Compra 1-clic — Top 5 del ranking:**")
    cols5 = st.columns(5)
    for i, r in enumerate(ranking_now[:5]):
        orden_r = calc_sltp(r["ticker"], r["precio"], atr_m, rr_m)
        with cols5[i]:
            lbl = f"🟢 {r['ticker']}\n${r['precio']:.2f}\n+{r['roc5']:.1f}%/5m"
            if st.button(lbl, key=f"buy_rk_{r['ticker']}_{i}",
                         use_container_width=True):
                if not sim_mode:
                    ok,msg = comprar_market(r["ticker"],usd_t,orden_r["sl"],orden_r["tp"])
                    st.success(msg) if ok else st.error(msg)
                else:
                    st.info("Sim: sin orden real.")
else:
    st.info("El ranking se construye cuando el WebSocket recibe datos de precio "
            "o cuando el Modo Simulación está activo.")

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  PORTAFOLIO ACTIVO
# ─────────────────────────────────────────────────────────────────────
st.subheader("💼 Portafolio Activo — Paper Trading Alpaca")
posiciones = get_positions()
if posiciones:
    rows_p = []
    for p in posiciones:
        pp = float(p.unrealized_plpc or 0) * 100
        pu = float(p.unrealized_pl  or 0)
        ico = "🟢" if pp >= 0 else "🔴"
        rows_p.append({
            "Ticker":    p.symbol,
            "Qty":       p.qty,
            "Entrada $": round(float(p.avg_entry_price or 0), 4),
            "Actual $":  round(float(p.current_price   or 0), 4),
            "P&L %":     f"{ico} {pp:+.2f}%",
            "P&L $":     f"${pu:+.2f}",
            "Valor $":   f"${float(p.market_value or 0):,.2f}",
        })
    st.dataframe(pd.DataFrame(rows_p), use_container_width=True, hide_index=True)
    pc1, pc2, pc3 = st.columns([2, 1, 1])
    with pc1:
        tc = st.selectbox("Cerrar posición", [r["Ticker"] for r in rows_p])
    with pc2:
        if st.button("🔴 Cerrar"):
            qty_p = int([r["Qty"] for r in rows_p if r["Ticker"]==tc][0])
            ok,msg = vender_market(tc, qty_p)
            st.success(msg) if ok else st.error(msg)
    with pc3:
        if st.button("🔴 Cerrar TODO"):
            for pos in posiciones:
                vender_market(pos.symbol, int(pos.qty))
            st.warning("Cerrando todas las posiciones...")
else:
    st.info("Sin posiciones abiertas.")

# ─────────────────────────────────────────────────────────────────────
#  AUTO-REFRESH (sin recargar toda la página, solo la UI lee shared)
# ─────────────────────────────────────────────────────────────────────
if auto_ref_s:
    time.sleep(8)
    st.rerun()

st.markdown('<hr class="n">', unsafe_allow_html=True)
st.markdown("""<div style="text-align:center;color:#8b949e;font-size:.67em;
font-family:'Share Tech Mono',monospace">
⚡ THUNDER RADAR V101 — TRÍADA MOMENTUM · CASCADA FAILOVER · ALPACA PAPER<br>
Fuentes: Alpaca Snapshots → Yahoo Finance (10 UA) → Twelve Data → Alpha Vantage<br>
Solo uso educativo. Los resultados pasados no garantizan rendimientos futuros.
</div>""", unsafe_allow_html=True)
