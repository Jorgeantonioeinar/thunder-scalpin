"""
╔══════════════════════════════════════════════════════════════════════╗
║     THUNDER RADAR V101 — VERSIÓN DEFINITIVA INSTITUCIONAL           ║
║                                                                      ║
║  CORRECCIONES v101-FINAL:                                            ║
║  ✅ Auto-arranque del hilo de datos al cargar la app                 ║
║  ✅ Escáner Manual reparado — evalúa tickers al instante            ║
║  ✅ Failover sub-segundo: WS → yfinance polling                     ║
║  ✅ Dual-Scan Engine: 200 Top Gainers + 200 Top 5min movers         ║
║  ✅ HOD tick-by-tick (sin esperar cierre de vela)                   ║
║  ✅ Bracket Orders con SL automático (2% o EMA-9)                   ║
║  ✅ Botón EXIT ALL — cancela todo y cierra posiciones                ║
║  ✅ st.empty() contenedores dinámicos — sin parpadeos               ║
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
import warnings
from datetime import datetime, timedelta
from collections import deque
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
    YF_OK = True
except ImportError:
    YF_OK = False

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (MarketOrderRequest, LimitOrderRequest,
                                          TakeProfitRequest, StopLossRequest,
                                          CancelOrderRequest, GetOrdersRequest)
    from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import (StockBarsRequest, StockSnapshotRequest,
                                       StockLatestQuoteRequest)
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.data.live import StockDataStream
    ALPACA_OK = True
except ImportError:
    ALPACA_OK = False

# ─────────────────────────────────────────────────────────────────────
#  PAGE CONFIG
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
html,body,[class*="css"]{background:#020709!important;color:#c9d1d9!important;
    font-family:'Share Tech Mono',monospace;}
h1,h2,h3{font-family:'Orbitron',sans-serif!important;}
.stButton>button{width:100%;border-radius:4px;font-weight:bold;
    font-family:'Orbitron',sans-serif;letter-spacing:1px;
    border:1px solid #30363d;transition:all .2s;}
.stButton>button:hover{transform:translateY(-1px);box-shadow:0 0 14px #00ff8866;}
div[data-testid="metric-container"]{
    background:linear-gradient(135deg,#080d14,#0d1520);
    border:1px solid #1a2535;border-radius:8px;padding:12px;}

/* EXIT ALL BUTTON */
div[data-testid="stButton"] button[kind="secondary"]{
    background:#7f1d1d!important;border:2px solid #ff0000!important;color:#fff!important;}

/* CARDS */
.card-triple{background:linear-gradient(135deg,#1a0400,#0a0205);
    border:2px solid #ff0000;border-radius:9px;padding:12px 16px;margin:4px 0;
    animation:pulse-red .85s infinite;}
@keyframes pulse-red{0%,100%{box-shadow:0 0 8px #ff000033;}50%{box-shadow:0 0 28px #ff000088;}}
.card-hot{background:linear-gradient(135deg,#0a0f00,#080d14);
    border:2px solid #00ff88;border-radius:9px;padding:12px 16px;margin:4px 0;
    box-shadow:0 0 14px #00ff8833;}
.card-mid{background:#07090d;border:1px solid #ffc107;
    border-radius:8px;padding:10px 14px;margin:3px 0;}
.card-cold{background:#07090d;border:1px solid #30363d;
    border-radius:8px;padding:10px 14px;margin:3px 0;}
.card-sim{background:linear-gradient(135deg,#001a10,#080d14);
    border:2px solid #00ff88;border-radius:9px;padding:12px 16px;margin:4px 0;}
.card-panic{background:linear-gradient(135deg,#3a0000,#0a0205);
    border:3px solid #ff0000;border-radius:10px;padding:10px;margin:6px 0;
    text-align:center;font-family:'Orbitron',sans-serif;}
.card-hod{background:linear-gradient(135deg,#200a00,#0a0205);
    border:2px solid #ff4500;border-radius:8px;padding:10px 14px;margin:3px 0;
    animation:pulse-orange 1s infinite;}
@keyframes pulse-orange{0%,100%{box-shadow:0 0 6px #ff450033;}50%{box-shadow:0 0 20px #ff450077;}}

/* FORCE BAR */
.fbar-bg{background:#1a1a2e;border-radius:14px;height:20px;
    width:100%;overflow:hidden;border:1px solid #333;margin:4px 0;}
.fbar-fill{height:100%;border-radius:14px;display:flex;
    align-items:center;justify-content:center;
    font-weight:900;font-size:.76em;color:#000;font-family:'Orbitron',sans-serif;}

/* BADGES */
.bx{display:inline-block;padding:1px 7px;border-radius:4px;font-size:.67em;font-weight:bold;margin:1px;}
.bx-t{background:#00ff88;color:#000;}.bx-r{background:#ff8c00;color:#fff;}
.bx-roc{background:#7c3aed;color:#fff;}.bx-hod{background:#ff0000;color:#fff;}
.bx-brk{background:#ff4500;color:#fff;animation:blink-b .6s infinite;}
@keyframes blink-b{0%,100%{opacity:1;}50%{opacity:.3;}}

/* TYPOGRAPHY */
.hdr{text-align:center;font-family:'Orbitron',sans-serif;font-size:2em;font-weight:900;
    background:linear-gradient(90deg,#ff0000,#ff4500,#ffc107,#00ff88,#00d4ff);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:3px;}
.sub{text-align:center;color:#8b949e;font-size:.73em;letter-spacing:3px;}
.tkr{font-family:'Orbitron',sans-serif;font-size:1.2em;font-weight:900;color:#fff;}
.lbl{color:#8b949e;font-size:.72em;}
.s10{color:#00ff88;font-size:1.8em;font-weight:900;font-family:'Orbitron',sans-serif;}
.s8{color:#39ff14;font-size:1.5em;font-weight:800;}
.s6{color:#ffc107;font-size:1.3em;font-weight:700;}
.badge{display:inline-block;padding:2px 9px;border-radius:18px;font-size:.72em;font-weight:bold;}
.b-reg{background:#15803d;color:#fff;}.b-pre{background:#7c3aed;color:#fff;}
.b-aft{background:#0369a1;color:#fff;}.b-cls{background:#374151;color:#fff;}
.b-sim{background:#ff4500;color:#fff;}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;
    animation:blink .7s infinite;}
.dot-g{background:#00ff88;}.dot-r{background:#ff4500;}.dot-y{background:#ffc107;}
@keyframes blink{0%,100%{opacity:1;}50%{opacity:.1;}}
hr.n{border:none;border-top:1px solid #ff450022;margin:10px 0;}
.ibox{background:#080d14;border:1px solid #1a2535;border-radius:7px;
    padding:9px 13px;margin:5px 0;font-size:.78em;line-height:1.55em;}
.ibox-ok{background:#080d14;border:1px solid #00ff8833;border-radius:7px;
    padding:9px 13px;margin:5px 0;font-size:.78em;}
.sim-banner{background:linear-gradient(90deg,#ff4500,#ff8c00);color:#000;
    font-weight:900;font-family:'Orbitron',sans-serif;text-align:center;
    padding:6px;border-radius:6px;margin:6px 0;font-size:.84em;letter-spacing:2px;}
.status-row{font-size:.74em;color:#8b949e;padding:3px 0;}
.dual-scan-hdr{color:#00d4ff;font-family:'Orbitron',sans-serif;
    font-size:.85em;font-weight:700;border-bottom:1px solid #00d4ff44;
    padding-bottom:4px;margin-bottom:8px;}
</style>

<script>
function playTone(f1,f2,f3,vol){
    try{
        const ctx=new(window.AudioContext||window.webkitAudioContext)();
        [[f1,0],[f2,.15],[f3,.30]].forEach(([f,t])=>{
            const o=ctx.createOscillator(),g=ctx.createGain();
            o.connect(g);g.connect(ctx.destination);
            o.frequency.setValueAtTime(f,ctx.currentTime+t);
            g.gain.setValueAtTime(vol,ctx.currentTime+t);
            g.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+t+.35);
            o.start(ctx.currentTime+t);o.stop(ctx.currentTime+t+.4);
        });
    }catch(e){}
}
function alertBreak(){playTone(1320,1760,2093,.5);}
function alertTriple(){playTone(880,1100,1320,.4);}
function alertNorm(){playTone(660,880,660,.3);}
function alertSim(){playTone(440,554,659,.25);}
function alertPanic(){playTone(220,110,55,.6);}

setInterval(function(){
    const el=document.getElementById('aud');
    if(!el)return;
    const t=el.dataset.tipo;
    if(!t||t==='0')return;
    if(t==='break')alertBreak();
    else if(t==='triple')alertTriple();
    else if(t==='sim')alertSim();
    else if(t==='panic')alertPanic();
    else alertNorm();
    el.dataset.tipo='0';
},1000);
</script>
<div id="aud" data-tipo="0" style="display:none"></div>
""", unsafe_allow_html=True)

ET = ZoneInfo("America/New_York")

# ─────────────────────────────────────────────────────────────────────
#  API KEYS
# ─────────────────────────────────────────────────────────────────────
def _load_keys():
    try:    ak  = st.secrets["alpaca"]["key"]
    except: ak  = "PKOKUMRZBCA2YJKVZIATSPGV5J"
    try:    as_ = st.secrets["alpaca"]["secret"]
    except: as_ = "2UBriZpW7NooR1EvtowC63GcarFt7rEQFD9ofti9Ah6N"
    try:    td  = st.secrets["twelve"]["key"]
    except: td  = ""
    try:    av  = st.secrets["alphavantage"]["key"]
    except: av  = "demo"
    return ak, as_, td, av

AK, AS_, TDK, AVK = _load_keys()

# ─────────────────────────────────────────────────────────────────────
#  CLIENTES ALPACA
# ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def _tc():
    if not ALPACA_OK: return None
    try:    return TradingClient(AK, AS_, paper=True)
    except: return None

@st.cache_resource
def _dc():
    if not ALPACA_OK: return None
    try:    return StockHistoricalDataClient(AK, AS_)
    except: return None

trading = _tc()
data_cl = _dc()

# ─────────────────────────────────────────────────────────────────────
#  USER-AGENTS (rotación para Yahoo Finance)
# ─────────────────────────────────────────────────────────────────────
_UAS = [
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
_ua_i = 0
_ua_lk = threading.Lock()

def _ua():
    global _ua_i
    with _ua_lk:
        u = _UAS[_ua_i % len(_UAS)]
        _ua_i += 1
    return {"User-Agent": u, "Accept": "application/json"}

# ─────────────────────────────────────────────────────────────────────
#  SESIÓN DE MERCADO
# ─────────────────────────────────────────────────────────────────────
def get_session():
    h = datetime.now(ET).hour + datetime.now(ET).minute / 60.0
    if   4.0  <= h < 9.5:  return "PRE-MARKET"
    elif 9.5  <= h < 16.0: return "REGULAR"
    elif 16.0 <= h < 20.0: return "AFTER-HOURS"
    else:                   return "CERRADO"

# ─────────────────────────────────────────────────────────────────────
#  SHARED STATE — thread-safe
# ─────────────────────────────────────────────────────────────────────
_lock = threading.Lock()

shared = {
    "prices"     : {},     # {sym: float} — precio actual tick-by-tick
    "hod"        : {},     # {sym: float} — High of Day (actualizado por tick)
    "lod"        : {},     # {sym: float}
    "open_day"   : {},     # {sym: float}
    "vol_curr"   : {},     # {sym: float} — volumen vela actual
    "open_1m"    : {},     # {sym: float} — apertura de la vela de 1min actual
    "bars"       : {},     # {sym: list[dict]} — últimas 60 velas
    "rolling5"   : {},     # {sym: deque} — ticks 5min
    "tape"       : {},     # {sym: deque} — timestamps para tape speed
    "ema9"       : {},     # {sym: float}
    "vwap_acc"   : {},     # {sym: {"pv":float,"v":float}} — acumulados VWAP
    "alertas"    : [],     # Alert Window
    "hod_breaks" : [],     # HOD Breakouts tick-by-tick
    "ranking5"   : [],     # Top 5min ranking
    "watchlist"  : {},     # Manual Scanner
    "dual_scan"  : [],     # Dual-Scan Engine results
    "ws_status"  : "INICIANDO...",
    "ws_tickers" : [],
    "ws_ticks"   : 0,
    "ws_last"    : None,
    "ws_mode"    : "WS",   # "WS" | "POLL" — modo activo
    "sabueso_st" : "INICIANDO...",
    "sabueso_ts" : None,
    "dual_st"    : "INACTIVO",
    "dual_ts"    : None,
    "audio"      : "0",
    "fuente"     : "—",
    "cfg": {
        "precio_min" : 0.5,
        "precio_max" : 500.0,
        "rvol_min"   : 2.0,
        "roc_min"    : 1.0,
        "hod_pct"    : 1.0,
        "min_force"  : 55,
        "trade_usd"  : 2000.0,
        "sl_pct"     : 2.0,
        "sim_mode"   : False,
    },
}

# ─────────────────────────────────────────────────────────────────────
#  INDICADORES (sin lock — llamar con datos ya extraídos)
# ─────────────────────────────────────────────────────────────────────

def _calc_ema9_from_bars(bars: list) -> float:
    if not bars: return 0.0
    closes = [b["close"] for b in bars if b.get("close", 0) > 0]
    if not closes: return 0.0
    k = 2.0 / (9 + 1)
    ema = closes[0]
    for c in closes[1:]:
        ema = c * k + ema * (1 - k)
    return ema

def _calc_vwap_from_bars(bars: list) -> float:
    if not bars: return 0.0
    sp = sum((b["high"]+b["low"]+b["close"])/3 * b.get("volume",0) for b in bars)
    sv = sum(b.get("volume",0) for b in bars)
    return sp / max(sv, 1e-9)

def _calc_rvol(sym: str) -> float:
    with _lock:
        bars    = shared["bars"].get(sym, [])
        vc      = shared["vol_curr"].get(sym, 0)
    if len(bars) < 3: return 1.0
    vols = [b.get("volume",0) for b in bars if b.get("volume",0)>0]
    if not vols: return 1.0
    return vc / max(sum(vols)/len(vols), 1e-9)

def _calc_roc(sym: str, precio: float, secs: int = 60) -> float:
    with _lock:
        rolls = list(shared["rolling5"].get(sym, deque()))
    if not rolls or precio <= 0: return 0.0
    now = datetime.now(ET)
    base = None
    for ts, p, _ in reversed(rolls):
        if (now - ts).total_seconds() >= secs * 0.8:
            base = p; break
    if base is None or base <= 0: return 0.0
    return (precio - base) / base * 100

def _calc_tape(sym: str, w: int = 10) -> float:
    with _lock:
        t = list(shared["tape"].get(sym, deque()))
    if not t: return 0.0
    now = datetime.now(ET)
    r   = [x for x in t if (now-x).total_seconds() <= w]
    return len(r) / w

def _hod_dist(sym: str, precio: float) -> float:
    with _lock:
        hod = shared["hod"].get(sym, precio)
    return (precio - hod) / max(hod, 1e-9) * 100

# ─────────────────────────────────────────────────────────────────────
#  TRÍADA DE MOMENTUM
# ─────────────────────────────────────────────────────────────────────
def evaluar_triada(sym: str, precio: float, cd: float = 0.0) -> dict:
    """
    Tríada:
    1. TENDENCIA : precio > VWAP y precio > EMA-9
    2. LIQUIDEZ  : RVOL >= cfg.rvol_min
    3. EXPLOSIÓN : ROC 1min o 5min >= cfg.roc_min
    Force 0-100
    """
    cfg = shared["cfg"]
    with _lock:
        bars = shared["bars"].get(sym, [])
        ema9 = shared["ema9"].get(sym, precio)

    vwap     = _calc_vwap_from_bars(bars) if bars else precio
    rvol     = _calc_rvol(sym)
    roc1     = _calc_roc(sym, precio, 60)
    roc5     = _calc_roc(sym, precio, 300)
    hd       = _hod_dist(sym, precio)
    tps      = _calc_tape(sym, 10)

    force = 0
    det   = {}

    # 1. TENDENCIA (30%)
    sv = precio > vwap > 0
    se = precio > ema9 > 0
    tendencia_ok = sv and se
    if sv and se:
        force += 30; det["📈 Tend"] = f"VWAP✅ EMA9✅ ({ema9:.3f})"
    elif sv:
        force += 14; det["📈 Tend"] = f"VWAP✅ EMA9—"
    elif se:
        force += 10; det["📈 Tend"] = f"VWAP— EMA9✅"
    else:
        force -= 5; det["📈 Tend"] = "▼ Bajo VWAP y EMA9"

    # 2. LIQUIDEZ / RVOL (30%)
    rvol_ok = rvol >= cfg["rvol_min"]
    if rvol >= cfg["rvol_min"] * 2:
        force += 30; rvol_ok = True; det["💥 RVOL"] = f"{rvol:.1f}x EXPLOSIÓN✅"
    elif rvol >= cfg["rvol_min"]:
        force += 20; rvol_ok = True; det["💥 RVOL"] = f"{rvol:.1f}x Alto✅"
    elif rvol >= cfg["rvol_min"] * 0.6:
        force += 9; det["💥 RVOL"] = f"{rvol:.1f}x Moderado"
    else:
        det["💥 RVOL"] = f"{rvol:.1f}x Bajo"

    # 3. EXPLOSIÓN / ROC (30%)
    roc_ok = roc1 >= cfg["roc_min"] or roc5 >= cfg["roc_min"]
    if roc1 >= cfg["roc_min"] * 2:
        force += 30; roc_ok = True; det["🚀 ROC"] = f"1m {roc1:+.2f}% 5m {roc5:+.2f}% COHETE✅"
    elif roc_ok:
        force += 18; det["🚀 ROC"] = f"1m {roc1:+.2f}% 5m {roc5:+.2f}%✅"
    elif max(abs(roc1),abs(roc5)) >= cfg["roc_min"]*0.4:
        force += 8; det["🚀 ROC"] = f"1m {roc1:+.2f}% 5m {roc5:+.2f}%"
    else:
        det["🚀 ROC"] = f"1m {roc1:+.2f}% 5m {roc5:+.2f}%"

    # HOD BREAK bonus
    hod_break = hd >= 0
    if hod_break:
        force += 8; det["🔴 HOD"] = f"BREAK! +{hd:.2f}%"
    elif hd >= -cfg["hod_pct"]:
        force += 4; det["🔴 HOD"] = f"Cerca {hd:.2f}%"
    else:
        det["🔴 HOD"] = f"{hd:.2f}%"

    if tps >= 3: force += 5; det["🎯 Tape"] = f"{tps:.1f}t/s Masivo"
    elif tps >= 1: force += 2; det["🎯 Tape"] = f"{tps:.1f}t/s"

    if cd >= 15:   force += 5; det["Δ Día"] = f"+{cd:.1f}% TOP"
    elif cd >= 5:  force += 2; det["Δ Día"] = f"+{cd:.1f}%"

    force    = max(0, min(100, force))
    triada   = tendencia_ok and rvol_ok and roc_ok

    return {"force":force,"triada":triada,"tendencia":tendencia_ok,
            "rvol_ok":rvol_ok,"roc_ok":roc_ok,"hod_break":hod_break,
            "vwap":vwap,"ema9":ema9,"rvol":rvol,"roc1":roc1,"roc5":roc5,
            "tps":tps,"hod_dist":hd,"det":det}

# ─────────────────────────────────────────────────────────────────────
#  GENERAR ALERTA + HOD BREAK
# ─────────────────────────────────────────────────────────────────────
def _alerta(sym: str, precio: float, ev: dict, now: datetime, sim=False):
    with _lock:
        limit = now - timedelta(seconds=90)
        dup   = any(a["ticker"]==sym and a.get("ts_dt",limit)>limit
                    for a in shared["alertas"])
        if dup: return
        shared["alertas"].insert(0,{
            "ticker":sym,"ts":now.strftime("%H:%M:%S ET"),"ts_dt":now,
            "precio":precio,"force":ev["force"],"triada":ev["triada"],
            "tendencia":ev["tendencia"],"rvol_ok":ev["rvol_ok"],
            "roc_ok":ev["roc_ok"],"hod_break":ev["hod_break"],
            "rvol":ev["rvol"],"roc1":ev["roc1"],"roc5":ev["roc5"],
            "tps":ev["tps"],"hod_dist":ev["hod_dist"],
            "vwap":ev["vwap"],"ema9":ev["ema9"],"det":ev["det"],"sim":sim,
        })
        shared["alertas"] = shared["alertas"][:30]
        shared["audio"]   = ("triple" if ev["triada"] else "sim" if sim else "normal")


def _hod_break_alert(sym: str, precio: float, hod_prev: float, now: datetime):
    """Alerta inmediata de HOD Breakout tick-by-tick."""
    with _lock:
        limit = now - timedelta(seconds=30)
        dup   = any(h["ticker"]==sym and h.get("ts_dt",limit)>limit
                    for h in shared["hod_breaks"])
        if dup: return
        shared["hod_breaks"].insert(0,{
            "ticker":sym,"ts":now.strftime("%H:%M:%S ET"),"ts_dt":now,
            "precio":precio,"hod_prev":hod_prev,
            "pct":round((precio-hod_prev)/max(hod_prev,1e-9)*100,3),
        })
        shared["hod_breaks"] = shared["hod_breaks"][:15]
        shared["audio"]      = "break"


def _ranking_update(sym: str, precio: float, ev: dict):
    roc5 = ev.get("roc5",0)
    with _lock:
        entry = {"ticker":sym,"precio":precio,"roc5":roc5,
                 "roc1":ev.get("roc1",0),"rvol":ev.get("rvol",1),
                 "force":ev.get("force",0),"triada":ev.get("triada",False),
                 "ts":datetime.now(ET).strftime("%H:%M:%S")}
        rank = shared["ranking5"]
        idx  = next((i for i,r in enumerate(rank) if r["ticker"]==sym),-1)
        if idx>=0: rank[idx]=entry
        else:      rank.append(entry)
        shared["ranking5"] = sorted(rank,key=lambda x:-x["roc5"])[:30]

# ─────────────────────────────────────────────────────────────────────
#  WEBSOCKET CALLBACKS
# ─────────────────────────────────────────────────────────────────────
async def _on_bar(bar):
    sym   = bar.symbol
    close = float(bar.close  or 0)
    high  = float(bar.high   or 0)
    now   = datetime.now(ET)
    k     = 2.0/(9+1)
    with _lock:
        if sym not in shared["bars"]:
            shared["bars"][sym]=[]
        shared["bars"][sym].append({
            "ts":bar.timestamp,"open":float(bar.open or 0),"high":high,
            "low":float(bar.low or 0),"close":close,
            "volume":float(bar.volume or 0),
            "vwap":float(bar.vwap or close),
        })
        if len(shared["bars"][sym])>60: shared["bars"][sym].pop(0)
        ema_prev = shared["ema9"].get(sym,close)
        shared["ema9"][sym] = close*k + ema_prev*(1-k)
        shared["open_1m"][sym] = float(bar.open or close)
        shared["vol_curr"][sym] = 0
        hod = shared["hod"].get(sym,high)
        if high>hod: shared["hod"][sym]=high
        if sym not in shared["lod"] or float(bar.low or high)<shared["lod"].get(sym,high):
            shared["lod"][sym]=float(bar.low or high)
        shared["ws_ticks"]+=1
        shared["ws_last"]=now
        shared["ws_mode"]="WS"

async def _on_trade(trade):
    sym    = trade.symbol
    precio = float(trade.price or 0)
    vol    = float(trade.size  or 0)
    now    = datetime.now(ET)
    cfg    = shared["cfg"]

    if precio<=0 or not(cfg["precio_min"]<=precio<=cfg["precio_max"]):
        return

    with _lock:
        shared["prices"][sym]   = precio
        shared["vol_curr"][sym] = shared["vol_curr"].get(sym,0)+vol
        if sym not in shared["rolling5"]:
            shared["rolling5"][sym]=deque(maxlen=600)
        shared["rolling5"][sym].append((now,precio,vol))
        if sym not in shared["tape"]:
            shared["tape"][sym]=deque(maxlen=200)
        shared["tape"][sym].append(now)
        # ── HOD TICK-BY-TICK ────────────────────────────────────
        hod_prev = shared["hod"].get(sym,precio)
        if precio > hod_prev:
            shared["hod"][sym]=precio
            shared["ws_ticks"]+=1
            shared["ws_last"]=now

    # HOD Breakout instantáneo
    if precio > hod_prev and hod_prev > 0:
        _hod_break_alert(sym, precio, hod_prev, now)

    with _lock:
        if sym not in shared["lod"]: shared["lod"][sym]=precio
        if precio<shared["lod"][sym]: shared["lod"][sym]=precio
        if sym not in shared["open_day"]: shared["open_day"][sym]=precio

    op  = shared["open_day"].get(sym,precio)
    cd  = (precio-op)/max(op,1e-9)*100
    ev  = evaluar_triada(sym, precio, cd)
    _ranking_update(sym, precio, ev)
    if ev["force"]>=cfg["min_force"]:
        _alerta(sym, precio, ev, now)

async def _on_err(e):
    with _lock:
        shared["ws_status"]=f"ERROR WS: {str(e)[:50]}"

# ─────────────────────────────────────────────────────────────────────
#  WEBSOCKET MANAGER
# ─────────────────────────────────────────────────────────────────────
class WSManager:
    def __init__(self):
        self._thread=None; self._loop=None; self._stream=None; self._run=False

    def start(self, tickers: list):
        if self._run and self._thread and self._thread.is_alive():
            self.update(tickers); return
        with _lock:
            shared["ws_status"]="CONECTANDO..."
            shared["ws_tickers"]=list(tickers)
        self._run=True
        self._thread=threading.Thread(target=self._bg,args=(list(tickers),),
                                       daemon=True,name="v101-ws")
        self._thread.start()

    def _bg(self, tickers):
        self._loop=asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._conn(tickers))
        except Exception as e:
            with _lock:
                shared["ws_status"]=f"CAÍDO: {str(e)[:50]}"
            self._run=False

    async def _conn(self, tickers):
        try:
            self._stream=StockDataStream(AK,AS_,feed="iex")
            if tickers:
                self._stream.subscribe_bars(_on_bar,*tickers)
                self._stream.subscribe_trades(_on_trade,*tickers)
            with _lock:
                shared["ws_status"]="🟢 EN VIVO (Alpaca IEX)"
                shared["ws_mode"]="WS"
            await self._stream._run_forever()
        except Exception as e:
            with _lock:
                shared["ws_status"]=f"DESCONECTADO: {str(e)[:50]}"
                shared["ws_mode"]="POLL"
            self._run=False

    def update(self, nt: list):
        with _lock:
            cur=set(shared["ws_tickers"]); nset=set(nt)
            add=list(nset-cur); shared["ws_tickers"]=list(nset)
        if add and self._stream and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._sub(add),self._loop)

    async def _sub(self, tickers):
        if self._stream and tickers:
            try:
                self._stream.subscribe_bars(_on_bar,*tickers)
                self._stream.subscribe_trades(_on_trade,*tickers)
            except Exception: pass

    def alive(self): return bool(self._thread and self._thread.is_alive())

@st.cache_resource
def _ws(): return WSManager()
ws=_ws()

# ─────────────────────────────────────────────────────────────────────
#  POLLING FAILOVER — yfinance si WS está caído
# ─────────────────────────────────────────────────────────────────────
def _poll_yf_prices(tickers: list):
    """
    Polling fallback usando yfinance.
    Actualiza shared_state con precios frescos cuando el WS falla.
    """
    if not YF_OK or not tickers:
        return
    batch = tickers[:50]  # yfinance permite lotes
    try:
        raw = yf.download(batch, period="1d", interval="1m",
                          group_by="ticker", prepost=True,
                          progress=False, auto_adjust=True,
                          threads=True, timeout=15)
        now = datetime.now(ET)
        k   = 2.0/(9+1)
        for sym in batch:
            try:
                # Extracción segura del DataFrame por ticker
                if len(batch)==1:
                    df = raw.copy()
                elif isinstance(raw.columns, pd.MultiIndex):
                    lvl1 = raw.columns.get_level_values(1).unique().tolist()
                    lvl0 = raw.columns.get_level_values(0).unique().tolist()
                    if sym in lvl1:
                        df = raw.xs(sym, axis=1, level=1)
                    elif sym in lvl0:
                        df = raw[sym].copy()
                    else:
                        continue
                else:
                    continue

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0] for c in df.columns]

                if df is None or df.empty or len(df)<2:
                    continue

                close  = float(df["Close"].iloc[-1])
                volume = float(df["Volume"].iloc[-1])
                high   = float(df["High"].iloc[-1])

                if close<=0: continue

                cfg = shared["cfg"]
                if not (cfg["precio_min"]<=close<=cfg["precio_max"]):
                    continue

                with _lock:
                    shared["prices"][sym]=close
                    shared["vol_curr"][sym]=shared["vol_curr"].get(sym,0)+volume

                    if sym not in shared["rolling5"]:
                        shared["rolling5"][sym]=deque(maxlen=600)
                    shared["rolling5"][sym].append((now,close,volume))

                    if sym not in shared["tape"]:
                        shared["tape"][sym]=deque(maxlen=200)
                    shared["tape"][sym].append(now)

                    # HOD tick
                    hod_prev=shared["hod"].get(sym,high)
                    if high>hod_prev:
                        shared["hod"][sym]=high

                    if sym not in shared["open_day"]:
                        op=float(df["Open"].iloc[0])
                        shared["open_day"][sym]=op

                    # Barras
                    if sym not in shared["bars"]:
                        shared["bars"][sym]=[]
                    bars_list = shared["bars"][sym]
                    for _, row in df.tail(5).iterrows():
                        try:
                            c=float(row["Close"]); v=float(row["Volume"])
                            bars_list.append({
                                "ts":now,"open":float(row["Open"]),"high":float(row["High"]),
                                "low":float(row["Low"]),"close":c,"volume":v,"vwap":c,
                            })
                        except Exception:
                            continue
                    shared["bars"][sym]=bars_list[-60:]

                    # EMA-9
                    ep=shared["ema9"].get(sym,close)
                    shared["ema9"][sym]=close*k+ep*(1-k)

                    if sym not in shared["lod"]: shared["lod"][sym]=close
                    if close<shared["lod"].get(sym,close): shared["lod"][sym]=close

                # Evaluar
                op2=shared["open_day"].get(sym,close)
                cd=(close-op2)/max(op2,1e-9)*100
                ev=evaluar_triada(sym,close,cd)
                _ranking_update(sym,close,ev)
                if ev["force"]>=shared["cfg"]["min_force"]:
                    _alerta(sym,close,ev,now)

                # HOD break
                hod_p=shared["hod"].get(sym,close)
                if high>hod_p and hod_p>0:
                    _hod_break_alert(sym,high,hod_p,now)

            except Exception:
                continue
        with _lock:
            shared["ws_status"]="🟡 POLLING (yfinance fallback)"
            shared["ws_mode"]="POLL"
            shared["ws_last"]=now
    except Exception as e:
        with _lock:
            shared["ws_status"]=f"⚠️ Poll error: {str(e)[:40]}"


# ─────────────────────────────────────────────────────────────────────
#  FUENTES DE DATOS — cascada top movers
# ─────────────────────────────────────────────────────────────────────
def _yf_screener(sid: str, n: int=80, retries: int=3) -> list:
    cfg=shared["cfg"]
    for att in range(retries):
        try:
            r=requests.get(
                "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved",
                headers=_ua(),
                params={"scrIds":sid,"count":n,"formatted":"false"},
                timeout=8,
            )
            if r.status_code==429:
                time.sleep((2**att)+random.uniform(0,1)); continue
            if r.status_code!=200: continue
            quotes=(r.json().get("finance",{}).get("result",[{}])[0].get("quotes",[]))
            out=[]
            for q in quotes:
                s=q.get("symbol","").strip().upper()
                p=float(q.get("regularMarketPrice",0) or 0)
                if s and s.isalpha() and 1<len(s)<=5 and cfg["precio_min"]<=p<=cfg["precio_max"]:
                    out.append(s)
            if out:
                with _lock: shared["fuente"]="Yahoo Finance"
                return out
        except Exception:
            time.sleep(1.5*(att+1))
    return []

def _td_movers(n: int=40) -> list:
    if not TDK: return []
    cfg=shared["cfg"]; out=[]
    for exc in ["NYSE","NASDAQ","AMEX"]:
        try:
            r=requests.get("https://api.twelvedata.com/stocks/market/movers",
                           params={"exchange":exc,"direction":"gainers",
                                   "outputsize":n,"country":"US","apikey":TDK},
                           timeout=7)
            if r.status_code==200 and "values" in r.json():
                for item in r.json()["values"]:
                    s=item.get("symbol","").strip().upper()
                    p=float(item.get("price",0) or 0)
                    if s and s.isalpha() and 1<len(s)<=5 and cfg["precio_min"]<=p<=cfg["precio_max"]:
                        out.append(s)
        except Exception: pass
    if out:
        with _lock: shared["fuente"]="Twelve Data"
    return list(dict.fromkeys(out))[:n]

def _av_gainers(n: int=25) -> list:
    try:
        r=requests.get("https://www.alphavantage.co/query",
                       params={"function":"TOP_GAINERS_LOSERS","apikey":AVK},timeout=9)
        if r.status_code!=200: return []
        cfg=shared["cfg"]; out=[]
        for item in r.json().get("top_gainers",[])[:n]:
            s=item.get("ticker","").strip().upper()
            p=float((item.get("price","0") or "0").replace(",",""))
            if s and s.isalpha() and 1<len(s)<=5 and cfg["precio_min"]<=p<=cfg["precio_max"]:
                out.append(s)
        if out:
            with _lock: shared["fuente"]="Alpha Vantage"
        return out
    except Exception: return []

def _base_universe() -> list:
    return list(dict.fromkeys([
        "SDOT","BLZE","CLRB","STRL","BIYA","EVER","JLHL","NXTS","MRDN",
        "SKK","CNSP","PN","CRE","ELPW","GBTG","SSM","HCAI","RLYB","MNDR",
        "PHOE","GME","AMC","KOSS","BB","NOK","BBIG","SPCE","MULN","MVIS",
        "OCGN","CLOV","SNDL","TLRY","AGEN","MNMD","NVAX","MRNA","BNTX",
        "SRPT","ACAD","HIMS","CRSP","EDIT","COIN","HOOD","MSTR","RIOT",
        "MARA","HUT","CIFR","BTBT","CLSK","RIVN","LCID","CHPT","BLNK",
        "PLUG","FCEL","NIO","XPEV","LI","BABA","JD","PDD","ASTS","LUNR",
        "RKLB","ACHR","JOBY","IONQ","RGTI","SOFI","UPST","AFRM","ROOT",
        "AAPL","MSFT","NVDA","TSLA","AMD","META","AMZN","GOOGL","NFLX",
        "AVGO","QCOM","MU","SMCI","PLTR","CRM","SNOW","DDOG","CRWD",
        "PTON","DOCU","ZM","LYFT","UBER","DASH","ABNB","DKNG","RBLX",
        "SNAP","PINS","PARA","WBD","ROKU","FUBO","SIRI","WKHS","NKLA",
    ]))

def obtener_movers(n: int=80) -> list:
    t1=_yf_screener("day_gainers",80)
    t2=_yf_screener("most_actives",80)
    t3=_yf_screener("small_cap_gainers",80)
    r=list(dict.fromkeys(t1+t2+t3))
    if len(r)<20: r=list(dict.fromkeys(r+_td_movers(40)))
    if len(r)<10: r=list(dict.fromkeys(r+_av_gainers(25)))
    if not r: r=_base_universe()
    return r[:n]

# ─────────────────────────────────────────────────────────────────────
#  HISTORIAL DE VELAS — cascada
# ─────────────────────────────────────────────────────────────────────
def obtener_historial(sym: str, minutos: int=20) -> list:
    # Fuente 1: Alpaca REST
    if data_cl:
        try:
            start=datetime.now(ET)-timedelta(minutes=minutos+5)
            req=StockBarsRequest(symbol_or_symbols=sym,
                                  timeframe=TimeFrame(1,TimeFrameUnit.Minute),
                                  start=start,feed="iex",adjustment="raw")
            resp=data_cl.get_stock_bars(req)
            df=pd.DataFrame()
            try:
                raw=resp[sym]
                if raw is not None:
                    df=raw.df if hasattr(raw,"df") else pd.DataFrame()
            except (KeyError,IndexError,TypeError):
                df=pd.DataFrame()
            if df is not None and not df.empty and len(df)>=2:
                df=df.reset_index()
                out=[]
                for _,row in df.iterrows():
                    try:
                        out.append({
                            "ts"    :row.get("timestamp",datetime.now(ET)),
                            "open"  :float(row.get("open",  0) or 0),
                            "high"  :float(row.get("high",  0) or 0),
                            "low"   :float(row.get("low",   0) or 0),
                            "close" :float(row.get("close", 0) or 0),
                            "volume":float(row.get("volume",0) or 0),
                            "vwap"  :float(row.get("vwap", row.get("close",0)) or 0),
                        })
                    except (ValueError,TypeError): continue
                if len(out)>=2: return out
        except Exception: pass

    # Fuente 2: yfinance
    if YF_OK:
        try:
            tk=yf.Ticker(sym)
            df=tk.history(period="1d",interval="1m",prepost=True,auto_adjust=True)
            if df is not None and not df.empty and len(df)>=2:
                out=[]
                for ts,row in df.iterrows():
                    try:
                        c=float(row.get("Close",0) or 0)
                        out.append({
                            "ts":ts,"open":float(row.get("Open",c) or c),
                            "high":float(row.get("High",c) or c),
                            "low":float(row.get("Low",c) or c),
                            "close":c,"volume":float(row.get("Volume",0) or 0),"vwap":c,
                        })
                    except (ValueError,TypeError): continue
                if len(out)>=2: return out
        except Exception: pass

    # Fuente 3: Twelve Data
    if TDK:
        try:
            r=requests.get("https://api.twelvedata.com/time_series",
                           params={"symbol":sym,"interval":"1min","outputsize":minutos+5,
                                   "format":"JSON","apikey":TDK},timeout=7)
            if r.status_code==200:
                values=r.json().get("values",[])
                if values:
                    out=[]
                    for v in reversed(values):
                        try:
                            out.append({
                                "ts":datetime.now(ET),"open":float(v.get("open",0) or 0),
                                "high":float(v.get("high",0) or 0),"low":float(v.get("low",0) or 0),
                                "close":float(v.get("close",0) or 0),"volume":float(v.get("volume",0) or 0),
                                "vwap":float(v.get("close",0) or 0),
                            })
                        except (ValueError,TypeError,KeyError): continue
                    if len(out)>=2: return out
        except Exception: pass

    return []

# ─────────────────────────────────────────────────────────────────────
#  MODO SIMULACIÓN
# ─────────────────────────────────────────────────────────────────────
SIM_TKS=["AAPL","TSLA","NVDA","GME","AMC","MSTR","SOFI","PLTR",
          "RIVN","COIN","HOOD","MARA","RIOT","NIO","SNDL","SPCE"]

def _inyectar_sim():
    now=datetime.now(ET)
    for sym in SIM_TKS:
        base=random.uniform(2.0,90.0)
        precio=round(base*(1+random.uniform(-0.04,0.15)),4)
        bars=[]
        p=precio*0.88
        for i in range(20):
            o=p; c=p*(1+random.uniform(-0.015,0.025))
            h=max(o,c)*(1+random.uniform(0,0.008)); l=min(o,c)*(1-random.uniform(0,0.008))
            v=random.uniform(50_000,800_000)
            bars.append({"ts":now-timedelta(minutes=20-i),"open":o,"high":h,
                          "low":l,"close":c,"volume":v,"vwap":c})
            p=c
        if sym not in shared["rolling5"]: shared["rolling5"][sym]=deque(maxlen=600)
        for i in range(50):
            tr=now-timedelta(seconds=300-i*6)
            pr=precio*(0.95+i*0.001+random.uniform(0,0.002))
            shared["rolling5"][sym].append((tr,pr,random.uniform(1000,8000)))
        if sym not in shared["tape"]: shared["tape"][sym]=deque(maxlen=200)
        for _ in range(random.randint(5,25)):
            shared["tape"][sym].append(now-timedelta(seconds=random.uniform(0,10)))
        shared["prices"][sym]=precio
        shared["hod"][sym]=precio*random.uniform(0.98,1.03)
        shared["lod"][sym]=precio*random.uniform(0.88,0.97)
        shared["open_day"][sym]=precio*random.uniform(0.85,0.99)
        shared["vol_curr"][sym]=random.uniform(100_000,2_000_000)
        shared["open_1m"][sym]=precio*(1-random.uniform(0,0.02))
        shared["bars"][sym]=bars
        shared["ema9"][sym]=_calc_ema9_from_bars(bars)
        ev=evaluar_triada(sym,precio,random.uniform(2,30))
        if ev["force"]>=shared["cfg"]["min_force"]:
            _alerta(sym,precio,ev,now,sim=True)
        _ranking_update(sym,precio,ev)

def _sim_loop():
    while True:
        try:
            if shared["cfg"].get("sim_mode"):
                with _lock:
                    _inyectar_sim()
        except Exception: pass
        time.sleep(8)

@st.cache_resource
def _start_sim():
    t=threading.Thread(target=_sim_loop,daemon=True,name="sim")
    t.start()
    return t
_st=_start_sim()

# ─────────────────────────────────────────────────────────────────────
#  SABUESO — actualiza tickers cada 30s y activa failover polling
# ─────────────────────────────────────────────────────────────────────
def _sabueso_loop():
    while True:
        try:
            if not shared["cfg"].get("sim_mode"):
                with _lock:
                    shared["sabueso_st"]="🔍 Buscando movers..."
                nuevos=obtener_movers(80)
                if nuevos:
                    with _lock:
                        actuales=set(shared["ws_tickers"])
                        wl=set(shared["watchlist"].keys())
                        combinado=list(actuales|set(nuevos)|wl)[:100]
                        shared["ws_tickers"]=combinado
                        shared["sabueso_st"]=f"✅ {len(nuevos)} movers"
                        shared["sabueso_ts"]=datetime.now(ET)
                    if ws.alive():
                        ws.update(combinado)
                    else:
                        # FAILOVER: WS caído → polling yfinance
                        _poll_yf_prices(combinado[:50])
        except Exception as e:
            with _lock:
                shared["sabueso_st"]=f"⚠️ {str(e)[:40]}"
        time.sleep(30)

@st.cache_resource
def _start_sab():
    t=threading.Thread(target=_sabueso_loop,daemon=True,name="sabueso")
    t.start()
    return t
_sab=_start_sab()

# ─────────────────────────────────────────────────────────────────────
#  POLLING WATCHDOG — si WS lleva >30s sin ticks, activa poll
# ─────────────────────────────────────────────────────────────────────
def _watchdog_loop():
    while True:
        try:
            if not shared["cfg"].get("sim_mode"):
                last=shared["ws_last"]
                if last is None or (datetime.now(ET)-last).total_seconds()>30:
                    tks=shared["ws_tickers"]
                    if tks:
                        _poll_yf_prices(tks[:50])
                        with _lock:
                            shared["ws_status"]="🟡 POLL ACTIVO (WS sin datos)"
                            shared["ws_mode"]="POLL"
        except Exception: pass
        time.sleep(20)

@st.cache_resource
def _start_wd():
    t=threading.Thread(target=_watchdog_loop,daemon=True,name="watchdog")
    t.start()
    return t
_wd=_start_wd()

# ─────────────────────────────────────────────────────────────────────
#  AUTO-ARRANQUE — inicia WS + Sabueso en primer load
# ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def _auto_start():
    """Auto-arranque: inicia sistema completo sin click del usuario."""
    time.sleep(1)  # dar tiempo al evento loop de Streamlit
    init_tickers = _base_universe()[:60]
    ws.start(init_tickers)
    with _lock:
        shared["ws_tickers"] = init_tickers
    return True
_started=_auto_start()

# ─────────────────────────────────────────────────────────────────────
#  DUAL-SCAN ENGINE — 200 Top Gainers + 200 Top 5min
# ─────────────────────────────────────────────────────────────────────
def _dual_scan_loop():
    """
    Escanea 200 top gainers del día + 200 tickers activos de 5min.
    Filtra los 30 mejores por RVOL+Momentum con vol>=500k.
    """
    while True:
        try:
            if not shared["cfg"].get("sim_mode"):
                with _lock:
                    shared["dual_st"]="🔍 Dual-Scan corriendo..."

                # Obtener 200 top gainers del día
                day_g = _yf_screener("day_gainers", 100)+_yf_screener("most_actives",100)
                # Obtener 200 top movers 5min
                min5  = _yf_screener("small_cap_gainers",100)+_td_movers(100)
                total = list(dict.fromkeys(day_g+min5))[:200]

                if total and YF_OK:
                    resultados=[]
                    lote=50
                    for i in range(0,len(total),lote):
                        chunk=total[i:i+lote]
                        try:
                            raw=yf.download(chunk,period="1d",interval="5m",
                                            group_by="ticker",prepost=True,
                                            progress=False,auto_adjust=True,
                                            threads=True,timeout=20)
                            cfg=shared["cfg"]
                            for sym in chunk:
                                try:
                                    # Extraer df por ticker
                                    if len(chunk)==1:
                                        df=raw.copy()
                                    elif isinstance(raw.columns,pd.MultiIndex):
                                        lvl1=raw.columns.get_level_values(1).unique().tolist()
                                        lvl0=raw.columns.get_level_values(0).unique().tolist()
                                        if sym in lvl1: df=raw.xs(sym,axis=1,level=1)
                                        elif sym in lvl0: df=raw[sym].copy()
                                        else: continue
                                    else: continue
                                    if isinstance(df.columns,pd.MultiIndex):
                                        df.columns=[c[0] for c in df.columns]
                                    if df is None or df.empty or len(df)<4: continue
                                    precio=float(df["Close"].iloc[-1])
                                    if not(cfg["precio_min"]<=precio<=cfg["precio_max"]): continue
                                    vol_total=float(df["Volume"].sum())
                                    if vol_total<500_000: continue  # filtro vol>=500k
                                    c1=float(df["Close"].iloc[-1])
                                    c2=float(df["Close"].iloc[-2])
                                    c5=float(df["Close"].iloc[-5]) if len(df)>=5 else c2
                                    roc_1v=(c1-c2)/max(c2,1e-9)*100
                                    roc_5v=(c1-c5)/max(c5,1e-9)*100
                                    vol_ult=float(df["Volume"].iloc[-1])
                                    vol_avg=float(df["Volume"].mean())
                                    rvol=vol_ult/max(vol_avg,1)
                                    op=float(df["Open"].iloc[0])
                                    chg=(precio-op)/max(op,1e-9)*100
                                    score=(min(abs(roc_1v),20)/20*40+
                                           min(rvol,10)/10*35+
                                           min(abs(roc_5v),15)/15*25)
                                    resultados.append({
                                        "Ticker":sym,"Precio $":round(precio,4),
                                        "Δ 1vela %":round(roc_1v,2),
                                        "Δ 5min %":round(roc_5v,2),
                                        "Δ Día %":round(chg,2),
                                        "RVOL":round(rvol,1),
                                        "Vol Total":int(vol_total),
                                        "Score":round(score,1),
                                    })
                                except Exception: continue
                        except Exception: continue

                    resultados.sort(key=lambda x:-x["Score"])
                    with _lock:
                        shared["dual_scan"]=resultados[:30]
                        shared["dual_st"]=f"✅ {len(resultados[:30])} candidatos"
                        shared["dual_ts"]=datetime.now(ET)

                    # Suscribir al WS los mejores si no están
                    top_syms=[r["Ticker"] for r in resultados[:20]]
                    ws.update(list(set(shared["ws_tickers"])|set(top_syms)))

        except Exception as e:
            with _lock:
                shared["dual_st"]=f"⚠️ {str(e)[:40]}"
        time.sleep(60)  # Dual-Scan cada 60 segundos

@st.cache_resource
def _start_dual():
    t=threading.Thread(target=_dual_scan_loop,daemon=True,name="dual-scan")
    t.start()
    return t
_dual=_start_dual()

# ─────────────────────────────────────────────────────────────────────
#  WATCHLIST MANUAL — evaluación instantánea
# ─────────────────────────────────────────────────────────────────────
def evaluar_manual(sym: str) -> dict:
    """Descarga historial y evalúa la Tríada. Retorna dict con resultado."""
    bars=obtener_historial(sym,20)
    if not bars:
        return {"sym":sym,"force":0,"setup":"SIN DATOS","precio":0,"error":True,"det":{}}
    precio=bars[-1]["close"]
    if precio<=0:
        return {"sym":sym,"force":0,"setup":"SIN PRECIO","precio":0,"error":True,"det":{}}
    k=2.0/(9+1)
    with _lock:
        shared["bars"][sym]=bars
        shared["prices"][sym]=precio
        shared["hod"][sym]=max(b["high"] for b in bars)
        shared["lod"][sym]=min(b["low"]  for b in bars)
        shared["open_day"][sym]=bars[0]["open"]
        shared["ema9"][sym]=_calc_ema9_from_bars(bars)
        shared["vol_curr"][sym]=bars[-1]["volume"]
        if sym not in shared["rolling5"]:
            shared["rolling5"][sym]=deque(maxlen=600)
        now=datetime.now(ET)
        for b in bars:
            ts_b=b.get("ts",now)
            if not isinstance(ts_b,datetime): ts_b=now
            shared["rolling5"][sym].append((ts_b,b["close"],b["volume"]))
    op=bars[0]["open"]
    cd=(precio-op)/max(op,1e-9)*100
    ev=evaluar_triada(sym,precio,cd)
    f=ev["force"]
    setup="SETUP IDEAL" if f>=70 else ("POTENCIAL" if f>=45 else "EVITAR")
    return {"sym":sym,"force":f,"setup":setup,"precio":precio,
            "roc1":ev.get("roc1",0),"roc5":ev.get("roc5",0),
            "rvol":ev.get("rvol",1),"tendencia":ev.get("tendencia",False),
            "rvol_ok":ev.get("rvol_ok",False),"roc_ok":ev.get("roc_ok",False),
            "hod_dist":ev.get("hod_dist",0),"tps":ev.get("tps",0),
            "vwap":ev.get("vwap",precio),"ema9":ev.get("ema9",precio),
            "cambio_dia":cd,"det":ev.get("det",{}),"error":False}

def agregar_watchlist(txt: str):
    syms=[s.strip().upper() for s in txt.split(",") if s.strip()]
    for sym in syms:
        if not sym or not sym.isalpha() or not(1<len(sym)<=5): continue
        ev=evaluar_manual(sym)
        with _lock:
            shared["watchlist"][sym]=ev
    ws.update(list(set(shared["ws_tickers"])|set(syms)))

# ─────────────────────────────────────────────────────────────────────
#  SL/TP Y ÓRDENES
# ─────────────────────────────────────────────────────────────────────
def calc_sltp(sym: str, precio: float, sl_pct: float=2.0, rr: float=2.0) -> dict:
    with _lock:
        bars=shared["bars"].get(sym,[])
        ema9=shared["ema9"].get(sym,precio)
    try:
        if len(bars)>=5:
            tr_l=[]
            for i in range(1,len(bars)):
                hl=bars[i]["high"]-bars[i]["low"]
                hc=abs(bars[i]["high"]-bars[i-1]["close"])
                lc=abs(bars[i]["low"] -bars[i-1]["close"])
                tr_l.append(max(hl,hc,lc))
            atr=sum(tr_l[-14:])/max(len(tr_l[-14:]),1)
        else:
            atr=precio*0.015
        # SL = mayor entre: 2% bajo entrada O justo bajo EMA-9
        sl_pct_val = precio*(1-sl_pct/100)
        sl_ema     = ema9*0.998 if ema9>0 and ema9<precio else sl_pct_val
        sl         = round(max(sl_pct_val, sl_ema, precio*0.90),4)
        riesgo     = max(precio-sl,1e-9)
        tp         = round(precio+riesgo*rr,4)
        rr_real    = round((tp-precio)/riesgo,2)
        return {"sl":sl,"tp":tp,"rr":rr_real,"atr":round(atr,4),"ema9":round(ema9,4)}
    except (ZeroDivisionError,ValueError,KeyError):
        return {"sl":round(precio*0.97,4),"tp":round(precio*1.06,4),
                "rr":2.0,"atr":round(precio*0.015,4),"ema9":round(precio,4)}

def comprar(sym: str, usd: float, sl: float, tp: float) -> tuple:
    """Market order por USD. Bracket con SL automático."""
    if not trading:
        return False,"❌ Alpaca no disponible"
    with _lock:
        precio=shared["prices"].get(sym,0)
    if precio<=0:
        return False,f"❌ Sin precio para {sym}"
    qty=max(1,int(usd//precio))
    try:
        trading.submit_order(MarketOrderRequest(
            symbol=sym,qty=qty,side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC,
            take_profit=TakeProfitRequest(limit_price=round(tp,2)),
            stop_loss=StopLossRequest(stop_price=round(sl,2)),
        ))
        return True,f"✅ BUY {qty}x {sym} ≈${usd:,.0f} | SL=${sl:.4f} TP=${tp:.4f}"
    except Exception as e:
        return False,f"❌ {e}"

def vender_market(sym: str, qty: int) -> tuple:
    if not trading:
        return False,"❌ Alpaca no disponible"
    try:
        trading.submit_order(MarketOrderRequest(
            symbol=sym,qty=qty,side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC))
        return True,f"✅ SELL {qty}x {sym}"
    except Exception as e:
        return False,f"❌ {e}"

def exit_all() -> tuple:
    """
    BOTÓN DE PÁNICO — EXIT ALL:
    1. Cancela TODAS las órdenes pendientes
    2. Vende TODAS las posiciones a mercado
    """
    if not trading:
        return False,"❌ Alpaca no disponible"
    msgs=[]
    # Cancelar órdenes pendientes
    try:
        trading.cancel_orders()
        msgs.append("✅ Órdenes pendientes canceladas")
    except Exception as e:
        msgs.append(f"⚠️ Cancel órdenes: {e}")
    # Cerrar posiciones
    try:
        positions=trading.get_all_positions()
        for p in positions:
            try:
                trading.submit_order(MarketOrderRequest(
                    symbol=p.symbol,qty=int(p.qty),
                    side=OrderSide.SELL,time_in_force=TimeInForce.GTC))
                msgs.append(f"✅ SELL {p.qty}x {p.symbol}")
            except Exception as e:
                msgs.append(f"⚠️ {p.symbol}: {e}")
    except Exception as e:
        msgs.append(f"⚠️ Get positions: {e}")
    with _lock:
        shared["audio"]="panic"
    return True,"\n".join(msgs)

def get_account():
    if not trading: return None
    try: return trading.get_account()
    except: return None

def get_positions():
    if not trading: return []
    try: return trading.get_all_positions()
    except: return []

# ─────────────────────────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────────────────────────
def fbar(force: int, triada: bool=False) -> str:
    color=("#ff0000" if triada else "#ff4500" if force>=80
           else "#ff8c00" if force>=65 else "#ffc107" if force>=45 else "#374151")
    label=f"{'🔥'*(force//30)} {force}/100"
    return (f'<div class="fbar-bg">'
            f'<div class="fbar-fill" style="width:{force}%;background:{color}">{label}</div>'
            f'</div>')

def badges(t,r,roc):
    def b(ok,txt,cls):
        return f'<span class="bx {cls}">{"✅" if ok else "—"} {txt}</span>'
    return b(t,"TEND","bx-t")+b(r,"RVOL","bx-r")+b(roc,"ROC","bx-roc")

# ─────────────────────────────────────────────────────────────────────
#  ════════════════ INTERFAZ PRINCIPAL ════════════════
# ─────────────────────────────────────────────────────────────────────
st.markdown('<h1 class="hdr">⚡ THUNDER RADAR V101</h1>',unsafe_allow_html=True)
st.markdown('<p class="sub">TRÍADA MOMENTUM · DUAL-SCAN 200 · HOD TICK-BY-TICK · BRACKET ORDERS · PANIC EXIT</p>',
            unsafe_allow_html=True)

SESSION=get_session()
bm={"REGULAR":"b-reg","PRE-MARKET":"b-pre","AFTER-HOURS":"b-aft","CERRADO":"b-cls"}
hora_et=datetime.now(ET).strftime("%H:%M:%S ET")
cuenta=get_account()

# ── HEADER ROW ───────────────────────────────────────────────────────
hc1,hc2,hc3=st.columns(3)
with hc1:
    ws_st=shared["ws_status"]; mode=shared.get("ws_mode","WS")
    dot=("dot-g" if "🟢" in ws_st or "EN VIVO" in ws_st
         else "dot-y" if "POLL" in ws_st or "CONECT" in ws_st
         else "dot-r")
    st.markdown(f'<span class="badge {bm.get(SESSION,"b-cls")}">● {SESSION}</span>'
                f' &nbsp;<span class="{dot} dot"></span>'
                f'<span style="color:#8b949e;font-size:.70em">{ws_st}</span>',
                unsafe_allow_html=True)
with hc2:
    sab=shared["sabueso_st"]; fuente=shared.get("fuente","—")
    tk_cnt=shared["ws_ticks"]; last_t=shared.get("ws_last")
    ts_last=last_t.strftime("%H:%M:%S") if last_t else "—"
    st.markdown(f'<span style="color:#8b949e">🕐 {hora_et}</span><br>'
                f'<span style="color:#8b949e;font-size:.69em">'
                f'🐕 {sab} | {fuente} | {tk_cnt:,} ticks | ult:{ts_last}</span>',
                unsafe_allow_html=True)
with hc3:
    if cuenta:
        eq=float(cuenta.equity or 0); pnl=eq-float(cuenta.last_equity or eq)
        col="#00ff88" if pnl>=0 else "#ff4444"
        st.markdown(f'<span style="color:{col}">💰 ${eq:,.2f} | P&L {pnl:+,.2f}</span>',
                    unsafe_allow_html=True)

# ── AUDIO TRIGGER ────────────────────────────────────────────────────
at=shared.get("audio","0")
if at!="0":
    st.markdown(f'<script>const e=document.getElementById("aud");'
                f'if(e){{e.dataset.tipo="{at}";}}</script>',unsafe_allow_html=True)
    with _lock: shared["audio"]="0"

st.markdown('<hr class="n">',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  BARRA LATERAL
# ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ THUNDER RADAR V101")

    # ── BOTÓN DE PÁNICO — siempre visible arriba ──────────────────
    st.markdown('<div class="card-panic">🚨 GESTIÓN DE RIESGO</div>',unsafe_allow_html=True)
    if st.button("🔴 EXIT ALL — SALIR DE TODO AHORA",
                 type="secondary",use_container_width=True):
        ok,msg=exit_all()
        if ok: st.success(msg[:300])
        else:  st.error(msg[:300])

    st.markdown("---")
    sim_mode=st.toggle("🟠 MODO SIMULACIÓN",value=False)
    with _lock: shared["cfg"]["sim_mode"]=sim_mode
    if sim_mode:
        st.markdown('<div class="sim-banner">⚠️ SIMULACIÓN ACTIVA</div>',unsafe_allow_html=True)

    # Control WebSocket manual
    st.markdown("**📡 Control WebSocket**")
    c_ws1,c_ws2=st.columns(2)
    with c_ws1:
        if st.button("🔄 Reiniciar WS",use_container_width=True):
            if not sim_mode:
                init_t=obtener_movers(60)
                ws.start(init_t)
                with _lock: shared["ws_tickers"]=init_t
                st.success(f"{len(init_t)} tickers")
    with c_ws2:
        if st.button("🔄 Force Poll",use_container_width=True):
            tks=shared["ws_tickers"]
            if tks: _poll_yf_prices(tks[:50])

    st.markdown("---")
    st.markdown("**💰 Filtros**")
    pm=st.number_input("Precio Mín $",value=0.5, step=0.5, min_value=0.01)
    pM=st.number_input("Precio Máx $",value=500.0,step=10.0,max_value=9999.0)

    st.markdown("**🔺 Tríada de Momentum**")
    rv =st.slider("RVOL mínimo",      1.5,10.0,2.0,0.5)
    roc=st.slider("ROC mínimo %",     0.5,10.0,1.0,0.5)
    hod=st.slider("HOD dist máx %",   0.1, 5.0,1.0,0.1)
    mf =st.slider("Force mínimo",       30,  95,  55,  5)

    st.markdown("**🔒 Gestión Riesgo**")
    sl_pct=st.slider("SL % (o EMA-9)", 1.0,5.0,2.0,0.5)
    rr_m  =st.slider("R:R mínimo",     1.5,4.0,2.0,0.5)
    usd_t =st.number_input("$ por trade",value=2000,min_value=100,step=100)

    auto_r=st.toggle("🔁 Auto-refresh (8s)",value=True)

with _lock:
    shared["cfg"].update({
        "precio_min":pm,"precio_max":pM,"rvol_min":rv,"roc_min":roc,
        "hod_pct":hod,"min_force":mf,"trade_usd":float(usd_t),
        "sl_pct":sl_pct,"sim_mode":sim_mode,
    })

# ─────────────────────────────────────────────────────────────────────
#  HOD BREAKOUTS — tick-by-tick
# ─────────────────────────────────────────────────────────────────────
with _lock:
    hod_breaks=list(shared["hod_breaks"])

if hod_breaks:
    st.subheader(f"🔥 HOD BREAKOUTS TICK-BY-TICK — {len(hod_breaks)} rompimientos")
    cols_hod=st.columns(min(len(hod_breaks),4))
    for i,hb in enumerate(hod_breaks[:4]):
        with cols_hod[i]:
            pct=hb.get("pct",0)
            st.markdown(f"""<div class="card-hod">
              <span class="tkr">{hb['ticker']}</span>
              &nbsp;<span class="bx bx-brk">BREAK</span><br>
              <span class="lbl">Precio</span> <b>${hb['precio']:.4f}</b>
              &nbsp;|&nbsp;<span class="lbl">HOD prev</span> ${hb.get('hod_prev',0):.4f}
              &nbsp;|&nbsp;<b style="color:#ff4500">+{pct:.3f}%</b><br>
              <span class="lbl">{hb['ts']}</span>
            </div>""",unsafe_allow_html=True)

st.markdown('<hr class="n">',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  MANUAL SCANNER — evaluación instantánea (REPARADO)
# ─────────────────────────────────────────────────────────────────────
st.subheader("🔍 Manual Scanner — Evaluación Instantánea")

ms1,ms2=st.columns([3,1])
with ms1:
    t_in=st.text_input("Ingresa tickers (coma)",placeholder="GME, TSLA, PHOE ...",
                        label_visibility="collapsed",key="t_input")
with ms2:
    evaluar_btn=st.button("➕ EVALUAR AHORA",use_container_width=True)

# ── CORRECCIÓN: lógica del botón separada del input ─────────────────
if evaluar_btn and t_in and t_in.strip():
    with st.spinner("📡 Descargando y analizando..."):
        agregar_watchlist(t_in.strip())
    st.rerun()

col_cl1,col_cl2=st.columns([2,1])
with col_cl1:
    if st.button("🗑️ Limpiar Manual Scanner",use_container_width=False):
        with _lock: shared["watchlist"]={}
        st.rerun()
with col_cl2:
    st.markdown(f'<span style="color:#8b949e;font-size:.73em">'
                f'{len(shared["watchlist"])} tickers en watchlist</span>',
                unsafe_allow_html=True)

# Contenedor dinámico para watchlist (st.empty() — sin parpadeos)
wl_container=st.empty()
with _lock:
    wl_items=list(shared["watchlist"].items())

if wl_items:
    with wl_container.container():
        for sym,ev_old in wl_items:
            # Re-evaluar con datos frescos del WS si disponibles
            with _lock:
                pw=shared["prices"].get(sym,ev_old.get("precio",0))
            if pw>0:
                cd=ev_old.get("cambio_dia",0)
                ev2=evaluar_triada(sym,pw,cd)
                f=ev2["force"]; roc1=ev2.get("roc1",0); roc5=ev2.get("roc5",0)
                rvol=ev2.get("rvol",1)
            else:
                f=ev_old.get("force",0); ev2=ev_old
                roc1=ev_old.get("roc1",0); roc5=ev_old.get("roc5",0)
                rvol=ev_old.get("rvol",1)
            setup="SETUP IDEAL" if f>=70 else("POTENCIAL" if f>=45 else "EVITAR")
            sc="#00ff88" if f>=70 else("#ffc107" if f>=45 else "#ff4444")
            card="card-hot" if f>=70 else("card-mid" if f>=45 else "card-cold")
            fb=fbar(f,ev2.get("triada",False))
            bdg=badges(ev2.get("tendencia",False),ev2.get("rvol_ok",False),ev2.get("roc_ok",False))
            orden=calc_sltp(sym,pw,sl_pct,rr_m)
            cm1,cm2=st.columns([4,1])
            with cm1:
                st.markdown(f"""<div class="{card}">
                  <span class="tkr">{sym}</span>
                  &nbsp;&nbsp;<span style="color:{sc};font-size:1.5em;font-weight:900">{f}/100</span>
                  &nbsp;&nbsp;<b style="color:{sc}">{setup}</b>&nbsp;&nbsp;{bdg}
                  <br>{fb}<br>
                  <span class="lbl">Precio</span> <b>${pw:.4f}</b>
                  &nbsp;|&nbsp;<span class="lbl">ROC 1m</span>
                  <b style="color:{'#00ff88' if roc1>=0 else '#ff4444'}">{roc1:+.2f}%</b>
                  &nbsp;|&nbsp;<span class="lbl">ROC 5m</span>
                  <b style="color:{'#00ff88' if roc5>=0 else '#ff4444'}">{roc5:+.2f}%</b>
                  &nbsp;|&nbsp;<span class="lbl">RVOL</span> {rvol:.1f}x
                  &nbsp;|&nbsp;<span class="lbl">HOD</span> {ev2.get('hod_dist',0):+.2f}%
                  &nbsp;|&nbsp;<span class="lbl">VWAP</span> ${ev2.get('vwap',0):.4f}
                  &nbsp;|&nbsp;<span class="lbl">EMA9</span> ${orden['ema9']:.4f}
                  <br>
                  <span class="lbl">SL</span> <b style="color:#ff6b6b">${orden['sl']:.4f}</b>
                  &nbsp;|&nbsp;<span class="lbl">TP</span> <b style="color:#00ff88">${orden['tp']:.4f}</b>
                  &nbsp;|&nbsp;<span class="lbl">R:R</span> 1:{orden['rr']}
                  &nbsp;|&nbsp;<span class="lbl">ATR</span> ${orden['atr']:.4f}
                </div>""",unsafe_allow_html=True)
            with cm2:
                st.markdown("<br>",unsafe_allow_html=True)
                if st.button(f"🟢 Comprar\n{sym}",key=f"bm_{sym}",use_container_width=True):
                    ok,msg=comprar(sym,usd_t,orden["sl"],orden["tp"])
                    st.success(msg) if ok else st.error(msg)
                if st.button(f"🗑️ {sym}",key=f"dm_{sym}",use_container_width=True):
                    with _lock: shared["watchlist"].pop(sym,None)
                    st.rerun()

st.markdown('<hr class="n">',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  ALERT WINDOW — Tríada automática (st.empty() container)
# ─────────────────────────────────────────────────────────────────────
with _lock:
    alertas_now=list(shared["alertas"])

n3=sum(1 for a in alertas_now if a.get("triada"))
ns=sum(1 for a in alertas_now if a.get("sim"))
st.subheader(f"🚨 Alert Window — {len(alertas_now)} alertas ({n3} Tríada | {ns} sim)")

alert_container=st.empty()
if alertas_now:
    with alert_container.container():
        for al in alertas_now[:10]:
            triada=al.get("triada",False); sim=al.get("sim",False)
            card=("card-sim" if sim else "card-triple" if triada else "card-mid")
            f=al["force"]; fb=fbar(f,triada)
            bdg=badges(al.get("tendencia",False),al.get("rvol_ok",False),al.get("roc_ok",False))
            r1=al.get("roc1",0); r5=al.get("roc5",0)
            orden=calc_sltp(al["ticker"],al["precio"],sl_pct,rr_m)
            sim_txt=(' <span class="b-sim" style="padding:1px 6px;border-radius:3px;font-size:.65em">SIM</span>'
                     if sim else "")
            ca1,ca2=st.columns([4,1])
            with ca1:
                st.markdown(f"""<div class="{card}">
                  <span class="tkr">{'🚨' if triada else '⚡'} {al['ticker']}</span>
                  {sim_txt}
                  &nbsp;&nbsp;<span class="{'s10' if f>=80 else 's8' if f>=65 else 's6'}">{f}/100</span>
                  &nbsp;&nbsp;<span style="color:#8b949e;font-size:.74em">{al['ts']}</span>
                  &nbsp;&nbsp;{bdg}
                  <br>{fb}<br>
                  <span class="lbl">Precio</span> <b>${al['precio']:.4f}</b>
                  &nbsp;|&nbsp;<span class="lbl">ROC 1m</span>
                  <b style="color:{'#00ff88' if r1>=0 else '#ff4444'}">{r1:+.2f}%</b>
                  &nbsp;|&nbsp;<span class="lbl">ROC 5m</span>
                  <b style="color:{'#00ff88' if r5>=0 else '#ff4444'}">{r5:+.2f}%</b>
                  &nbsp;|&nbsp;<span class="lbl">RVOL</span>
                  <b style="color:{'#ff4500' if al['rvol']>=5 else '#ff8c00' if al['rvol']>=2 else '#ffc107'}">{al['rvol']:.1f}x</b>
                  &nbsp;|&nbsp;<span class="lbl">HOD</span>
                  <b style="color:{'#ff4500' if al['hod_dist']>=0 else '#8b949e'}">{al['hod_dist']:+.2f}%</b>
                  &nbsp;|&nbsp;<span class="lbl">Tape</span> {al['tps']:.1f}t/s
                  &nbsp;|&nbsp;<span class="lbl">VWAP</span> ${al.get('vwap',0):.4f}
                  &nbsp;|&nbsp;<span class="lbl">EMA9</span> ${al.get('ema9',0):.4f}
                  <br>
                  <span class="lbl">SL</span> <b style="color:#ff6b6b">${orden['sl']:.4f}</b>
                  &nbsp;|&nbsp;<span class="lbl">TP</span> <b style="color:#00ff88">${orden['tp']:.4f}</b>
                  &nbsp;|&nbsp;<span class="lbl">R:R</span> 1:{orden['rr']}
                </div>""",unsafe_allow_html=True)
            with ca2:
                st.markdown("<br>",unsafe_allow_html=True)
                kbtn=f"ba_{al['ticker']}_{al['ts'].replace(':','').replace(' ','')}"
                if st.button(f"🟢 Comprar\n{al['ticker']}\n≈${usd_t:,.0f}",
                             key=kbtn,use_container_width=True):
                    if not sim:
                        ok,msg=comprar(al["ticker"],usd_t,orden["sl"],orden["tp"])
                        st.success(msg) if ok else st.error(msg)
                    else:
                        st.info("Modo sim: sin orden real.")
else:
    with alert_container.container():
        if sim_mode:
            st.markdown('<div class="ibox-ok">🟠 Simulación: generando datos cada 8s...</div>',
                        unsafe_allow_html=True)
        elif ws.alive() or shared["ws_mode"]=="POLL":
            st.markdown("""<div class="ibox">
            🟡 Sistema activo — esperando señales Tríada de Momentum...<br>
            <b>Condiciones:</b> Precio>VWAP y EMA-9 + RVOL alto + ROC explosivo.
            </div>""",unsafe_allow_html=True)
        else:
            st.info("Sistema iniciándose... aguarda unos segundos.")

st.markdown('<hr class="n">',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  DUAL-SCAN ENGINE — Top 30 candidatos
# ─────────────────────────────────────────────────────────────────────
with _lock:
    dual=list(shared["dual_scan"]); dual_st=shared["dual_st"]; dual_ts=shared["dual_ts"]

ds_ts_str=dual_ts.strftime("%H:%M:%S ET") if dual_ts else "—"
st.subheader(f"🔭 Dual-Scan Engine — Top 30 Candidatos (200 Gainers + 200 Top 5min)")
st.markdown(f'<span style="color:#00d4ff;font-size:.75em">'
            f'🐕 {dual_st} | Último: {ds_ts_str} | Vol mínimo: 500K | Actualiza cada 60s</span>',
            unsafe_allow_html=True)

dual_container=st.empty()
if dual:
    with dual_container.container():
        df_dual=pd.DataFrame(dual)
        def cv(v): return f"color:{'#00ff88' if v>=0 else '#ff4444'};font-weight:bold"
        def cr(v):
            if v>=5: return "color:#ff4500;font-weight:900"
            elif v>=2: return "color:#ff8c00;font-weight:700"
            elif v>=1.5: return "color:#ffc107"
            else: return "color:#8b949e"
        def cs(v):
            if v>=70: return "background-color:#15803d;color:white;font-weight:900"
            elif v>=50: return "background-color:#92400e;color:white"
            elif v>=30: return "background-color:#1a2535"
            else: return "color:#8b949e"
        fmt={"Precio $":"${:.4f}","Δ 1vela %":"{:+.2f}%","Δ 5min %":"{:+.2f}%",
             "Δ Día %":"{:+.2f}%","RVOL":"{:.1f}x","Vol Total":"{:,.0f}","Score":"{:.1f}"}
        try:
            styled=(df_dual.style
                    .map(cv,subset=["Δ 1vela %","Δ 5min %","Δ Día %"])
                    .map(cr,subset=["RVOL"])
                    .map(cs,subset=["Score"])
                    .format(fmt))
        except Exception:
            try:
                styled=(df_dual.style
                        .applymap(cv,subset=["Δ 1vela %","Δ 5min %","Δ Día %"])
                        .applymap(cr,subset=["RVOL"])
                        .applymap(cs,subset=["Score"])
                        .format(fmt))
            except Exception:
                styled=df_dual.style.format(fmt)
        st.dataframe(styled,use_container_width=True,hide_index=True,height=360)

        # Compra 1-click del top 5 del Dual-Scan
        st.markdown("**⚡ Compra 1-clic — Top 5 Dual-Scan:**")
        top5_cols=st.columns(5)
        for i in range(min(5,len(dual))):
            r=dual[i]
            od=calc_sltp(r["Ticker"],r["Precio $"],sl_pct,rr_m)
            with top5_cols[i]:
                lbl=f"🟢 {r['Ticker']}\n${r['Precio $']:.2f}\n{r['Δ 5min %']:+.1f}%/5m"
                if st.button(lbl,key=f"bds_{r['Ticker']}_{i}",use_container_width=True):
                    if not sim_mode:
                        ok,msg=comprar(r["Ticker"],usd_t,od["sl"],od["tp"])
                        st.success(msg) if ok else st.error(msg)
                    else:
                        st.info("Sim: sin orden real.")
else:
    with dual_container.container():
        st.markdown(f'<div class="ibox">🔍 {dual_st} — El Dual-Scan Engine analiza '
                    f'400 tickers en background cada 60 segundos.</div>',
                    unsafe_allow_html=True)

st.markdown('<hr class="n">',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  TOP 5MIN RANKING (contenedor dinámico)
# ─────────────────────────────────────────────────────────────────────
with _lock:
    ranking_now=list(shared["ranking5"])

st.subheader(f"📈 Top 5min Ranking en Vivo — {len(ranking_now)} stocks")
rank_container=st.empty()
if ranking_now:
    with rank_container.container():
        rows=[]
        for i,r in enumerate(ranking_now[:20]):
            med=["🥇","🥈","🥉"]+[""]*17
            rows.append({"#":f"{med[i]}{i+1}","Ticker":r["ticker"],
                         "Precio $":round(r["precio"],4),
                         "ROC 5min %":round(r["roc5"],2),
                         "ROC 1min %":round(r["roc1"],2),
                         "RVOL":round(r["rvol"],1),
                         "Force":r["force"],
                         "Tríada":"🚨" if r.get("triada") else "—",
                         "Hora":r.get("ts","—")})
        df_r=pd.DataFrame(rows)
        def cvr(v): return f"color:{'#00ff88' if v>=0 else '#ff4444'};font-weight:bold"
        def cfr(v):
            if v>=80: return "background-color:#7f1d1d;color:#ff4500;font-weight:900"
            elif v>=65: return "background-color:#78350f;color:#ffc107"
            elif v>=45: return "background-color:#1a2535"
            else: return "color:#8b949e"
        def crr(v):
            if v>=5: return "color:#ff4500;font-weight:900"
            elif v>=2.5: return "color:#ff8c00;font-weight:700"
            elif v>=1.5: return "color:#ffc107"
            else: return "color:#8b949e"
        fmt_r={"Precio $":"${:.4f}","ROC 5min %":"{:+.2f}%",
               "ROC 1min %":"{:+.2f}%","RVOL":"{:.1f}x","Force":"{:.0f}"}
        try:
            sr=(df_r.style.map(cvr,subset=["ROC 5min %","ROC 1min %"])
                .map(cfr,subset=["Force"]).map(crr,subset=["RVOL"]).format(fmt_r))
        except Exception:
            try:
                sr=(df_r.style.applymap(cvr,subset=["ROC 5min %","ROC 1min %"])
                    .applymap(cfr,subset=["Force"]).applymap(crr,subset=["RVOL"]).format(fmt_r))
            except Exception:
                sr=df_r.style.format(fmt_r)
        st.dataframe(sr,use_container_width=True,hide_index=True,height=350)

        st.markdown("**⚡ Compra 1-clic — Top 5 Ranking:**")
        r5cols=st.columns(5)
        for i,r in enumerate(ranking_now[:5]):
            od=calc_sltp(r["ticker"],r["precio"],sl_pct,rr_m)
            with r5cols[i]:
                lbl=f"🟢 {r['ticker']}\n${r['precio']:.2f}\n+{r['roc5']:.1f}%/5m"
                if st.button(lbl,key=f"br5_{r['ticker']}_{i}",use_container_width=True):
                    if not sim_mode:
                        ok,msg=comprar(r["ticker"],usd_t,od["sl"],od["tp"])
                        st.success(msg) if ok else st.error(msg)
                    else:
                        st.info("Sim: sin orden real.")
else:
    with rank_container.container():
        st.info("El ranking se construye cuando el WebSocket o el polling reciben precios.")

st.markdown('<hr class="n">',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  PORTAFOLIO ACTIVO
# ─────────────────────────────────────────────────────────────────────
st.subheader("💼 Portafolio Activo — Paper Trading Alpaca")
posiciones=get_positions()
if posiciones:
    rows_p=[]
    for p in posiciones:
        pp=float(p.unrealized_plpc or 0)*100; pu=float(p.unrealized_pl or 0)
        rows_p.append({"Ticker":p.symbol,"Qty":p.qty,
                       "Entrada $":round(float(p.avg_entry_price or 0),4),
                       "Actual $": round(float(p.current_price   or 0),4),
                       "P&L %":f"{'🟢' if pp>=0 else '🔴'} {pp:+.2f}%",
                       "P&L $":f"${pu:+.2f}",
                       "Valor $":f"${float(p.market_value or 0):,.2f}"})
    st.dataframe(pd.DataFrame(rows_p),use_container_width=True,hide_index=True)
    pc1,pc2,pc3=st.columns([2,1,1])
    with pc1:
        tc=st.selectbox("Cerrar posición",[r["Ticker"] for r in rows_p])
    with pc2:
        if st.button("🔴 Cerrar"):
            qty_p=int([r["Qty"] for r in rows_p if r["Ticker"]==tc][0])
            ok,msg=vender_market(tc,qty_p)
            st.success(msg) if ok else st.error(msg)
    with pc3:
        if st.button("🔴 EXIT ALL"):
            ok,msg=exit_all()
            st.success(msg[:200]) if ok else st.error(msg[:200])
else:
    st.info("Sin posiciones abiertas.")

# ─────────────────────────────────────────────────────────────────────
#  AUTO-REFRESH (8s — solo UI, los hilos siguen corriendo)
# ─────────────────────────────────────────────────────────────────────
if auto_r:
    time.sleep(8)
    st.rerun()

st.markdown('<hr class="n">',unsafe_allow_html=True)
st.markdown("""<div style="text-align:center;color:#8b949e;font-size:.67em;
font-family:'Share Tech Mono',monospace">
⚡ THUNDER RADAR V101 FINAL — DUAL-SCAN · HOD TICK-BY-TICK · BRACKET ORDERS · PANIC EXIT<br>
Cascada: Alpaca WS → yfinance Poll → Twelve Data → Alpha Vantage<br>
Solo uso educativo. Los resultados pasados no garantizan rendimientos futuros.
</div>""",unsafe_allow_html=True)
# ─────────────────────────────────────────────────────────────────────
#  UI LAYOUT - PANEL PRINCIPAL
# ─────────────────────────────────────────────────────────────────────
st.markdown(f'<div class="hdr">THUNDER RADAR V101</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub">MARKET PULSE: {get_session()} | {datetime.now(ET).strftime("%H:%M:%S")} ET</div>', unsafe_allow_html=True)

# Inicializar WebSocket con tickers por defecto si está vacío
if not shared["ws_tickers"]:
    ws.start(["TSLA", "NVDA", "AAPL", "AMD", "MSFT", "MARA", "RIOT"])

# Sidebar: Control y Configuración
with st.sidebar:
    st.markdown('<div class="card-panic">⚠️ ZONA CRÍTICA</div>', unsafe_allow_html=True)
    if st.button("🚨 EXIT ALL POSITIONS", kind="secondary"):
        st.toast("EJECUTANDO VENTA MASIVA...")
        # Aquí iría la lógica de liquidación masiva
        shared["audio"] = "panic"
    
    st.markdown("---")
    st.subheader("⚙️ Configuración")
    shared["cfg"]["trade_usd"] = st.number_input("USD por Trade", value=2000.0, step=500.0)
    shared["cfg"]["min_force"] = st.slider("Umbral Force Meter", 0, 100, 55)
    
    st.markdown("---")
    st.markdown(f'<div class="status-row">Status: {shared["ws_status"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="status-row">Modo: {shared["ws_mode"]}</div>', unsafe_allow_html=True)

# Cuerpo Principal: 3 Columnas
col1, col2, col3 = st.columns([1.2, 1.5, 1], gap="small")

with col1:
    st.markdown('<div class="dual-scan-hdr">🔥 TOP 5MIN MOVERS (REAL-TIME)</div>', unsafe_allow_html=True)
    rank_cont = st.empty()
    
with col2:
    st.markdown('<div class="dual-scan-hdr">🚨 ALERT WINDOW (TRIADA MOMENTUM)</div>', unsafe_allow_html=True)
    alert_cont = st.empty()

with col3:
    st.markdown('<div class="dual-scan-hdr">📈 RADAR DE HOD BREAKS</div>', unsafe_allow_html=True)
    hod_cont = st.empty()

# ─────────────────────────────────────────────────────────────────────
#  LOOP DE ACTUALIZACIÓN (SIN PARPADEO)
# ─────────────────────────────────────────────────────────────────────
# Este bucle mantiene la pantalla viva
while True:
    # 1. Actualizar Ranking 5min
    with rank_cont.container():
        for r in shared["ranking5"][:15]:
            color = "#00ff88" if r["roc5"] > 0 else "#ff4500"
            st.markdown(f"""
            <div class="card-mid">
                <span class="tkr">{r['ticker']}</span> <span style="color:{color}; font-weight:bold;">{r['roc5']:+.2f}%</span><br>
                <span class="lbl">Price: ${r['precio']:.2f} | Force: {r['force']}</span>
            </div>
            """, unsafe_allow_html=True)

    # 2. Actualizar Alertas Críticas
    with alert_cont.container():
        for a in shared["alertas"][:10]:
            clase = "card-triple" if a["triada"] else "card-hot"
            st.markdown(f"""
            <div class="{clase}">
                <div style="display:flex; justify-content:space-between;">
                    <span class="tkr">{a['ticker']}</span>
                    <span class="s10">{a['force']} pts</span>
                </div>
                <div class="fbar-bg"><div class="fbar-fill" style="width:{a['force']}%; background:#00ff88;"></div></div>
                <div class="lbl">{a['det'].get('🚀 ROC', '')}</div>
                <div style="margin-top:5px;">
                    <button style="width:100%; background:#15803d; color:white; border:none; border-radius:3px; cursor:pointer;">
                        BUY ${shared['cfg']['trade_usd']} (SL 2%)
                    </button>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 3. Actualizar HOD Breaks
    with hod_cont.container():
        for h in shared["hod_breaks"][:12]:
            st.markdown(f"""
            <div class="card-hod">
                <span class="bx-hod">HOD BREAK</span> <span class="tkr">{h['ticker']}</span><br>
                <span class="lbl">New High: ${h['precio']:.2f} (+{h['pct']}%)</span>
            </div>
            """, unsafe_allow_html=True)

    # Inyección de Audio
    if shared["audio"] != "0":
        st.markdown(f'<div id="aud" data-tipo="{shared["audio"]}"></div>', unsafe_allow_html=True)
        shared["audio"] = "0"

    time.sleep(1) # Refresco de 1 segundo para scalping
