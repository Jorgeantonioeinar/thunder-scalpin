"""
╔══════════════════════════════════════════════════════════════════════╗
║         THUNDER RADAR V100 — CLON GRATUITO DE TRADE IDEAS           ║
║                          SCALPING DE ALTA VELOCIDAD                  ║
║                                                                      ║
║  ARQUITECTURA:                                                       ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │  HILO 1: WebSocket (Alpaca IEX)  → datos tick-by-tick       │   ║
║  │  HILO 2: Sabueso  (cada 30s)     → Yahoo/Twelve Top Gainers │   ║
║  │  HILO PRINCIPAL: Streamlit UI    → lee shared_state         │   ║
║  └──────────────────────────────────────────────────────────────┘   ║
║                                                                      ║
║  FUNCIONES CLAVE:                                                    ║
║  • Alert Window   → alertas automáticas HOD + RVOL + Tape Speed     ║
║  • Manual Scanner → evalúa tickers del usuario en tiempo real        ║
║  • Top 5min Ranking → ranking en vivo por % ganancia en 5 minutos   ║
║  • Sabueso        → actualiza tickers cada 30s sin interrumpir WS   ║
║  • Compra 1-clic  → orden market directo desde cada alerta          ║
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
import warnings
from datetime import datetime, timedelta
from collections import deque
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")

# Alpaca
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.requests import TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.live import StockDataStream

# ─────────────────────────────────────────────────────────────────────
#  CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="⚡ THUNDER RADAR V100",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');

html,body,[class*="css"]{
    background:#020709!important;color:#c9d1d9!important;
    font-family:'Share Tech Mono',monospace;
}
h1,h2,h3{font-family:'Orbitron',sans-serif!important;}
.stButton>button{
    width:100%;border-radius:4px;font-weight:bold;
    font-family:'Orbitron',sans-serif;letter-spacing:1px;
    border:1px solid #30363d;transition:all .2s;
}
.stButton>button:hover{transform:translateY(-1px);box-shadow:0 0 14px #ff450066;}

div[data-testid="metric-container"]{
    background:linear-gradient(135deg,#080d14,#0d1520);
    border:1px solid #1a2535;border-radius:8px;padding:12px;
}

/* ── ALERT WINDOW (radar) ─────────────── */
.alert-card{
    background:linear-gradient(135deg,#1a0400,#0a0205);
    border:2px solid #ff0000;border-radius:8px;
    padding:11px 15px;margin:4px 0;
    animation:pulse-red .9s infinite;
}
@keyframes pulse-red{
    0%,100%{box-shadow:0 0 8px #ff000033;}
    50%    {box-shadow:0 0 28px #ff000088;}
}

/* ── MANUAL SCANNER ─────────────────────── */
.manual-good{background:linear-gradient(135deg,#061510,#080d14);
    border:2px solid #00ff88;border-radius:8px;padding:11px 15px;margin:4px 0;
    box-shadow:0 0 14px #00ff8844;}
.manual-mid {background:#0a0c10;border:1px solid #ffc107;
    border-radius:8px;padding:10px 14px;margin:3px 0;}
.manual-bad {background:#0a0810;border:1px solid #ff444433;
    border-radius:8px;padding:10px 14px;margin:3px 0;}

/* ── FORCE BAR ──────────────────────────── */
.fbar-bg{background:#1a1a2e;border-radius:16px;height:20px;
    width:100%;overflow:hidden;border:1px solid #333;}
.fbar-fill{height:100%;border-radius:16px;display:flex;
    align-items:center;justify-content:center;
    font-weight:900;font-size:.78em;color:#000;font-family:'Orbitron',sans-serif;}

/* ── TOP 5MIN TABLE ─────────────────────── */
.rank-row{padding:6px 10px;margin:2px 0;border-radius:6px;
    border-left:3px solid #ff4500;background:#080c12;}
.rank-row-gold{border-left-color:#ffd700;}
.rank-row-silver{border-left-color:#c0c0c0;}
.rank-row-bronze{border-left-color:#cd7f32;}

/* ── TEXTO ──────────────────────────────── */
.s10{color:#00ff88;font-size:1.8em;font-weight:900;font-family:'Orbitron',sans-serif;}
.s8 {color:#39ff14;font-size:1.5em;font-weight:800;}
.s6 {color:#ffc107;font-size:1.3em;font-weight:700;}
.tkr{font-family:'Orbitron',sans-serif;font-size:1.2em;font-weight:900;color:#fff;}
.lbl{color:#8b949e;font-size:.72em;}

/* ── HEADER ─────────────────────────────── */
.hdr{text-align:center;font-family:'Orbitron',sans-serif;font-size:2.1em;font-weight:900;
    background:linear-gradient(90deg,#ff0000,#ff4500,#ffc107,#00ff88,#00d4ff);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:3px;}
.sub{text-align:center;color:#8b949e;font-size:.75em;letter-spacing:3px;}

/* ── BADGES ─────────────────────────────── */
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.73em;font-weight:bold;}
.b-reg{background:#15803d;color:#fff;}.b-pre{background:#7c3aed;color:#fff;}
.b-aft{background:#0369a1;color:#fff;}.b-cls{background:#374151;color:#fff;}
.b-hod{background:#ff0000;color:#fff;padding:1px 7px;border-radius:4px;font-size:.68em;}
.b-rvol{background:#ff8c00;color:#fff;padding:1px 7px;border-radius:4px;font-size:.68em;}
.b-tape{background:#7c3aed;color:#fff;padding:1px 7px;border-radius:4px;font-size:.68em;}

.dot{display:inline-block;width:8px;height:8px;background:#ff4500;border-radius:50%;
    margin-right:4px;animation:blink .7s infinite;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.1}}
hr.n{border:none;border-top:1px solid #ff450022;margin:10px 0;}
.ibox{background:#080d14;border:1px solid #1a2535;border-radius:8px;
    padding:10px 14px;margin:5px 0;font-size:.79em;line-height:1.6em;}
.sabueso-ok{color:#00ff88;font-weight:bold;}
.sabueso-run{color:#ffc107;font-weight:bold;}
</style>

<script>
// ─── AUDIO ALERT SINTÉTICO ───────────────────────────────────────────
function playAlert(tipo) {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        if (tipo === 'hod') {
            // HOD Breakout: tono ascendente urgente
            osc.frequency.setValueAtTime(660, ctx.currentTime);
            osc.frequency.setValueAtTime(880, ctx.currentTime+0.1);
            osc.frequency.setValueAtTime(1100, ctx.currentTime+0.2);
            osc.frequency.setValueAtTime(1320, ctx.currentTime+0.3);
        } else {
            // Spike normal
            osc.frequency.setValueAtTime(880, ctx.currentTime);
            osc.frequency.setValueAtTime(1100, ctx.currentTime+0.15);
            osc.frequency.setValueAtTime(880, ctx.currentTime+0.3);
        }
        gain.gain.setValueAtTime(0.35, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime+0.6);
        osc.start(ctx.currentTime); osc.stop(ctx.currentTime+0.6);
    } catch(e) {}
}

// Polling para trigger de alertas
setInterval(function() {
    const el = document.getElementById('audio-trigger');
    if (el) {
        const tipo = el.dataset.tipo;
        if (tipo && tipo !== '0') {
            playAlert(tipo);
            el.dataset.tipo = '0';
        }
    }
}, 1500);
</script>
<div id="audio-trigger" data-tipo="0" style="display:none"></div>
""", unsafe_allow_html=True)

ET = ZoneInfo("America/New_York")

# ─────────────────────────────────────────────────────────────────────
#  API KEYS (st.secrets con fallback)
# ─────────────────────────────────────────────────────────────────────
def _keys():
    try:
        ak = st.secrets["alpaca"]["key"]
        as_ = st.secrets["alpaca"]["secret"]
    except Exception:
        ak  = "PKOKUMRZBCA2YJKVZIATSPGV5J"
        as_ = "2UBriZpW7NooR1EvtowC63GcarFt7rEQFD9ofti9Ah6N"
    try:
        td = st.secrets["twelve"]["key"]
    except Exception:
        td = ""
    return ak, as_, td

ALPACA_KEY, ALPACA_SECRET, TWELVE_KEY = _keys()

# ─────────────────────────────────────────────────────────────────────
#  CLIENTES ALPACA (cached — una sola instancia)
# ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def _trading():
    return TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

@st.cache_resource
def _data():
    return StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)

trading = _trading()
data_cl = _data()

# ─────────────────────────────────────────────────────────────────────
#  SESIÓN
# ─────────────────────────────────────────────────────────────────────
def get_session():
    h = datetime.now(ET).hour + datetime.now(ET).minute / 60.0
    if   4.0  <= h < 9.5:  return "PRE-MARKET"
    elif 9.5  <= h < 16.0: return "REGULAR"
    elif 16.0 <= h < 20.0: return "AFTER-HOURS"
    else:                   return "CERRADO"

SESSION = get_session()

# ─────────────────────────────────────────────────────────────────────
#  SHARED STATE — diccionario global thread-safe
#  Hilo WebSocket escribe → Streamlit UI lee
#  Hilo Sabueso actualiza tickers → WebSocket se suscribe
# ─────────────────────────────────────────────────────────────────────
_lock = threading.Lock()

shared = {
    # Precios en vivo: {sym: float}
    "prices": {},
    # HOD (High of Day) en vivo: {sym: float}
    "hod": {},
    # LOD (Low of Day): {sym: float}
    "lod": {},
    # Precio de apertura del día: {sym: float}
    "open_price": {},
    # Volumen acumulado vela actual: {sym: float}
    "vol_current": {},
    # Precio al inicio de la vela de 1min actual: {sym: float}
    "open_1min": {},
    # Rolling window 5min: {sym: deque(maxlen=500)} → (ts, price, volume)
    # CRÍTICO: esta es la fuente del ranking Top 5min y de la detección HOD
    "rolling5": {},
    # Ticks por segundo (tape speed): {sym: deque(maxlen=100)} → ts
    "tape": {},
    # Barras históricas: {sym: list de dicts}
    "bars": {},
    # Alertas Alert Window: list de dicts (más nuevas primero)
    "alertas": [],
    # Ranking Top 5min: list de dicts ordenados por vel_5m
    "ranking5": [],
    # Tickers suscritos actualmente al WS
    "ws_tickers": [],
    # Estado WebSocket
    "ws_status": "DESCONECTADO",
    "ws_ticks": 0,
    "ws_last": None,
    # Estado Sabueso
    "sabueso_status": "INACTIVO",
    "sabueso_last": None,
    "sabueso_tickers": [],
    # Watchlist manual: {sym: dict con evaluación}
    "watchlist": {},
    # Trigger de audio
    "audio_tipo": "0",
    # Nueva alerta HOD
    "nueva_hod": False,
    # Config dinámica (sliders Streamlit → WebSocket la lee)
    "cfg": {
        "precio_min": 0.01,
        "precio_max": 100.0,
        "rvol_min": 3.0,
        "min_force": 65,
        "spike_min": 2.0,
        "hod_dist_pct": 1.0,  # % distancia máxima al HOD
    },
}

# ─────────────────────────────────────────────────────────────────────
#  CÁLCULO DE MÉTRICAS (llamado desde WebSocket callbacks)
# ─────────────────────────────────────────────────────────────────────

def calc_vel_5m(sym: str, precio_actual: float) -> float:
    """
    Calcula % cambio en los últimos 5 minutos usando rolling window.
    Esta es la métrica del RANKING TOP 5MIN.
    Compara precio_actual vs precio de hace exactamente 300 segundos.
    """
    with _lock:
        rolls = list(shared["rolling5"].get(sym, deque()))
    if not rolls:
        return 0.0
    now = datetime.now(ET)
    # Buscar el precio más cercano a 5 minutos atrás
    precio_5m = None
    for ts, price, vol in reversed(rolls):
        diff = (now - ts).total_seconds()
        if diff >= 290:   # entre 290 y 360 segundos = ~5min
            precio_5m = price
            break
    if precio_5m is None or precio_5m <= 0:
        return 0.0
    return (precio_actual - precio_5m) / precio_5m * 100


def calc_vel_1m(sym: str, precio_actual: float) -> float:
    """% cambio en el último minuto."""
    with _lock:
        rolls = list(shared["rolling5"].get(sym, deque()))
    if not rolls:
        return 0.0
    now = datetime.now(ET)
    precio_1m = None
    for ts, price, vol in reversed(rolls):
        if (now - ts).total_seconds() >= 55:
            precio_1m = price
            break
    if precio_1m is None or precio_1m <= 0:
        return 0.0
    return (precio_actual - precio_1m) / precio_1m * 100


def calc_rvol(sym: str) -> float:
    """
    RVOL = vol vela actual / promedio vol de velas previas (últimas 20).
    Fuente: shared["vol_current"] y shared["bars"].
    """
    with _lock:
        vol_curr = shared["vol_current"].get(sym, 0)
        bars     = shared["bars"].get(sym, [])
    if not bars or len(bars) < 3:
        return 1.0
    vols_prev = [b["volume"] for b in bars[-20:] if b.get("volume",0) > 0]
    if not vols_prev:
        return 1.0
    avg = sum(vols_prev) / len(vols_prev)
    return vol_curr / max(avg, 1)


def calc_tape_speed(sym: str) -> float:
    """
    Ticks por segundo en los últimos 10 segundos.
    Aceleración masiva del tape = señal de actividad institucional.
    """
    with _lock:
        tape = list(shared["tape"].get(sym, deque()))
    if not tape:
        return 0.0
    now     = datetime.now(ET)
    recent  = [t for t in tape if (now - t).total_seconds() <= 10]
    return len(recent) / 10.0


def calc_hod_dist(sym: str, precio: float) -> float:
    """
    % distancia del precio actual al HOD (High of Day).
    Negativo = por debajo del HOD. Positivo = rompió el HOD.
    HOD_dist = (precio - HOD) / HOD * 100
    """
    with _lock:
        hod = shared["hod"].get(sym, precio)
    if hod <= 0:
        return 0.0
    return (precio - hod) / hod * 100


def actualizar_hod(sym: str, high: float, precio: float):
    """Actualiza el HOD y detecta ruptura."""
    with _lock:
        hod_prev = shared["hod"].get(sym, 0)
        if high > hod_prev:
            shared["hod"][sym] = high
        if sym not in shared["lod"] or precio < shared["lod"].get(sym, 999999):
            shared["lod"][sym] = precio


def calcular_force(sym: str, precio: float, cambio_dia: float = 0.0) -> dict:
    """
    Force Meter 0-100 con Triple Condición HOD:
      1. HOD Breakout o cercanía (< hod_dist_pct%)   → peso 30%
      2. RVOL >= 3.0x                                → peso 30%
      3. Tape Speed acelerado                        → peso 20%
      + Velocity 1min/5min                           → peso 20%

    CLASIFICACIÓN:
      force >= 80 → IGNICIÓN (comprar YA)
      force >= 65 → Setup alcista
      force >= 40 → Vigilancia
      force <  40 → Sin interés
    """
    cfg    = shared["cfg"]
    force  = 0
    det    = {}
    hod_breakout = False
    rvol_ok      = False
    tape_ok      = False

    # ── 1. HOD BREAKOUT / CERCANÍA (30%) ─────────────────────
    hod_dist = calc_hod_dist(sym, precio)
    max_dist = cfg["hod_dist_pct"]  # por defecto 1.0%
    if hod_dist >= 0:                         # rompió el HOD
        force += 30; hod_breakout = True
        det["🔴 HOD"] = f"¡RUPTURA HOD! +{hod_dist:.2f}% arriba"
    elif hod_dist >= -max_dist:              # cerca del HOD
        frac = (max_dist + hod_dist) / max_dist
        force += int(frac * 20)
        det["🔴 HOD"] = f"Cerca HOD: {hod_dist:.2f}% (umbral {max_dist}%)"
    else:
        det["🔴 HOD"] = f"Lejos HOD: {hod_dist:.2f}%"

    # ── 2. RVOL >= 3.0x (30%) ────────────────────────────────
    rvol = calc_rvol(sym)
    min_rvol = cfg["rvol_min"]
    if rvol >= min_rvol * 2:
        force += 30; rvol_ok = True
        det["💥 RVOL"] = f"{rvol:.1f}x — EXPLOSIÓN ✅"
    elif rvol >= min_rvol:
        force += 20; rvol_ok = True
        det["💥 RVOL"] = f"{rvol:.1f}x — Alto ✅"
    elif rvol >= min_rvol * 0.7:
        force += 10
        det["💥 RVOL"] = f"{rvol:.1f}x — Moderado"
    else:
        det["💥 RVOL"] = f"{rvol:.1f}x — Normal"

    # ── 3. TAPE SPEED (20%) ──────────────────────────────────
    tps = calc_tape_speed(sym)
    if tps >= 5:
        force += 20; tape_ok = True
        det["🎯 Tape"] = f"{tps:.1f} t/s — MASIVO ✅"
    elif tps >= 2:
        force += 12; tape_ok = True
        det["🎯 Tape"] = f"{tps:.1f} t/s — Alto"
    elif tps >= 0.5:
        force += 5
        det["🎯 Tape"] = f"{tps:.1f} t/s — Normal"
    else:
        det["🎯 Tape"] = f"{tps:.1f} t/s — Bajo"

    # ── 4. VELOCIDADES (20%) ─────────────────────────────────
    vel1 = calc_vel_1m(sym, precio)
    vel5 = calc_vel_5m(sym, precio)

    if vel1 >= 5:
        force += 12; det["⚡ Vel 1min"] = f"+{vel1:.2f}% — COHETE"
    elif vel1 >= 2:
        force += 8;  det["⚡ Vel 1min"] = f"+{vel1:.2f}% — Fuerte"
    elif vel1 >= 0.5:
        force += 4;  det["⚡ Vel 1min"] = f"+{vel1:.2f}%"
    elif vel1 < 0:
        force -= 3;  det["⚡ Vel 1min"] = f"{vel1:.2f}% ▼"
    else:
        det["⚡ Vel 1min"] = f"{vel1:+.2f}% →"

    if vel5 >= 5:
        force += 8; det["📈 Vel 5min"] = f"+{vel5:.2f}% — MOMENTUM"
    elif vel5 >= 2:
        force += 5; det["📈 Vel 5min"] = f"+{vel5:.2f}%"
    elif vel5 >= 0.5:
        force += 2; det["📈 Vel 5min"] = f"+{vel5:.2f}%"
    else:
        det["📈 Vel 5min"] = f"{vel5:+.2f}%"

    # Bonus Δ día
    if cambio_dia >= 20: force += 5; det["Δ Día"] = f"+{cambio_dia:.1f}% TOP"
    elif cambio_dia >= 5: force += 2; det["Δ Día"] = f"+{cambio_dia:.1f}%"

    force = max(0, min(100, force))

    # Triple condición HOD (alerta máxima)
    triple_hod = hod_breakout and rvol_ok and tape_ok

    return {
        "force"     : force,
        "triple_hod": triple_hod,
        "hod_break" : hod_breakout,
        "rvol_ok"   : rvol_ok,
        "tape_ok"   : tape_ok,
        "rvol"      : rvol,
        "vel1"      : vel1,
        "vel5"      : vel5,
        "tps"       : tps,
        "hod_dist"  : hod_dist,
        "detalles"  : det,
    }


# ─────────────────────────────────────────────────────────────────────
#  WEBSOCKET CALLBACKS — Alpaca StockDataStream
# ─────────────────────────────────────────────────────────────────────

async def on_bar(bar):
    """Vela de 1min cerrada — resetea volumen y apertura de nueva vela."""
    sym = bar.symbol
    with _lock:
        if sym not in shared["bars"]:
            shared["bars"][sym] = []
        shared["bars"][sym].append({
            "ts":     bar.timestamp,
            "open":   float(bar.open),
            "high":   float(bar.high),
            "low":    float(bar.low),
            "close":  float(bar.close),
            "volume": float(bar.volume),
            "vwap":   float(bar.vwap) if bar.vwap else float(bar.close),
        })
        # Mantener últimas 60 velas
        if len(shared["bars"][sym]) > 60:
            shared["bars"][sym].pop(0)

        # Nueva apertura de vela
        shared["open_1min"][sym]   = float(bar.open)
        shared["vol_current"][sym] = 0
        shared["ws_ticks"] += 1
        shared["ws_last"]   = datetime.now(ET)

        # Actualizar HOD con el high de la barra
        actualizar_hod(sym, float(bar.high), float(bar.close))


async def on_trade(trade):
    """
    Trade tick-by-tick — el corazón del sistema.
    Actualiza precios, rolling window y evalúa despegue en cada tick.
    """
    sym    = trade.symbol
    precio = float(trade.price)
    vol    = float(trade.size)
    ts     = datetime.now(ET)

    cfg = shared["cfg"]

    # Filtro de precio configurado por slider
    if not (cfg["precio_min"] <= precio <= cfg["precio_max"]):
        return

    with _lock:
        shared["prices"][sym]      = precio
        shared["vol_current"][sym] = shared["vol_current"].get(sym, 0) + vol

        # Rolling window 5min
        if sym not in shared["rolling5"]:
            shared["rolling5"][sym] = deque(maxlen=500)
        shared["rolling5"][sym].append((ts, precio, vol))

        # Tape speed (deque de timestamps últimos 100 ticks)
        if sym not in shared["tape"]:
            shared["tape"][sym] = deque(maxlen=100)
        shared["tape"][sym].append(ts)

        # HOD
        hod = shared["hod"].get(sym, precio)
        if precio > hod:
            shared["hod"][sym] = precio
        if sym not in shared["lod"]:
            shared["lod"][sym] = precio
        if precio < shared["lod"].get(sym, precio):
            shared["lod"][sym] = precio

        shared["ws_ticks"] += 1
        shared["ws_last"]   = ts

    # Evaluar Force (fuera del lock para minimizar latencia)
    ev = calcular_force(sym, precio)
    force    = ev["force"]
    trip_hod = ev["triple_hod"]
    min_force = cfg["min_force"]

    # ── Actualizar ranking Top 5min ───────────────────────────
    vel5 = ev["vel5"]
    with _lock:
        # Actualizar entrada en el ranking
        entry = {
            "ticker": sym, "precio": precio, "vel5": vel5,
            "vel1": ev["vel1"], "rvol": ev["rvol"],
            "force": force, "ts": ts.strftime("%H:%M:%S"),
            "hod_dist": ev["hod_dist"], "tps": ev["tps"],
        }
        # Actualizar o insertar en ranking
        rank = shared["ranking5"]
        idx  = next((i for i,r in enumerate(rank) if r["ticker"]==sym), -1)
        if idx >= 0:
            rank[idx] = entry
        else:
            rank.append(entry)
        # Ordenar por vel5min descendente
        shared["ranking5"] = sorted(rank, key=lambda x: -x["vel5"])[:30]

    # ── Generar alerta si cumple condiciones ─────────────────
    if force >= min_force:
        _generar_alerta(sym, precio, ev, ts, trip_hod)


def _generar_alerta(sym, precio, ev, ts, triple_hod):
    """Genera una alerta en shared['alertas'] evitando duplicados recientes."""
    with _lock:
        alertas  = shared["alertas"]
        ts_limit = datetime.now(ET) - timedelta(seconds=90)

        # Evitar alerta duplicada del mismo ticker en 90 segundos
        dup = any(
            a["ticker"] == sym and
            datetime.strptime(a["ts_raw"], "%H:%M:%S").replace(
                year=ts.year, month=ts.month, day=ts.day, tzinfo=ET
            ) > ts_limit
            for a in alertas if "ts_raw" in a
        )
        if dup:
            return

        alerta = {
            "ticker"    : sym,
            "ts"        : ts.strftime("%H:%M:%S ET"),
            "ts_raw"    : ts.strftime("%H:%M:%S"),
            "precio"    : precio,
            "force"     : ev["force"],
            "triple_hod": triple_hod,
            "hod_break" : ev["hod_break"],
            "rvol_ok"   : ev["rvol_ok"],
            "tape_ok"   : ev["tape_ok"],
            "rvol"      : ev["rvol"],
            "vel1"      : ev["vel1"],
            "vel5"      : ev["vel5"],
            "tps"       : ev["tps"],
            "hod_dist"  : ev["hod_dist"],
            "detalles"  : ev["detalles"],
        }
        shared["alertas"].insert(0, alerta)
        shared["alertas"] = shared["alertas"][:25]  # max 25 alertas

        # Trigger de audio
        shared["audio_tipo"] = "hod" if triple_hod else "spike"
        if triple_hod:
            shared["nueva_hod"] = True


async def on_error(err):
    with _lock:
        shared["ws_status"] = f"ERROR: {str(err)[:60]}"


# ─────────────────────────────────────────────────────────────────────
#  WEBSOCKET MANAGER — hilo de background
# ─────────────────────────────────────────────────────────────────────
class WSManager:
    """
    Gestiona el WebSocket de Alpaca en un hilo daemon.
    Permite suscribir/desuscribir tickers en caliente.
    """
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
            daemon=True, name="v100-ws"
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
                self._stream.subscribe_bars(on_bar, *tickers)
                self._stream.subscribe_trades(on_trade, *tickers)
            with _lock:
                shared["ws_status"] = "🟢 EN VIVO"
            await self._stream._run_forever()
        except Exception as e:
            with _lock:
                shared["ws_status"] = f"DESCONECTADO: {str(e)[:60]}"
            self._running = False

    def update(self, new_tickers: list):
        """Suscribe nuevos tickers sin reiniciar la conexión."""
        with _lock:
            current = set(shared["ws_tickers"])
            nuevo   = set(new_tickers)
            to_add  = list(nuevo - current)
            shared["ws_tickers"] = list(nuevo)

        if to_add and self._stream and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._sub_more(to_add), self._loop)

    async def _sub_more(self, tickers):
        if self._stream and tickers:
            try:
                self._stream.subscribe_bars(on_bar, *tickers)
                self._stream.subscribe_trades(on_trade, *tickers)
            except Exception:
                pass

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()


@st.cache_resource
def get_ws_manager():
    return WSManager()

ws = get_ws_manager()


# ─────────────────────────────────────────────────────────────────────
#  SABUESO — hilo background que busca top movers cada 30s
#  y actualiza dinámicamente la suscripción del WebSocket
# ─────────────────────────────────────────────────────────────────────
YH = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Accept": "application/json"}

def _yahoo_screener(sid: str, n: int = 50) -> list:
    """Obtiene tickers de un screener de Yahoo Finance."""
    for base in ["https://query1.finance.yahoo.com",
                 "https://query2.finance.yahoo.com"]:
        try:
            r = requests.get(
                f"{base}/v1/finance/screener/predefined/saved",
                headers=YH,
                params={"scrIds": sid, "count": n, "formatted": "false"},
                timeout=8
            )
            if r.status_code == 200:
                quotes = (r.json().get("finance",{})
                           .get("result",[{}])[0].get("quotes",[]))
                cfg = shared["cfg"]
                out = []
                for q in quotes:
                    s = q.get("symbol","").strip().upper()
                    if not s or not s.isalpha() or not (1<len(s)<=5):
                        continue
                    p = float(q.get("regularMarketPrice",0))
                    if cfg["precio_min"] <= p <= cfg["precio_max"]:
                        out.append(s)
                if out:
                    return out
        except Exception:
            pass
    return []


def _twelve_movers(n: int = 30) -> list:
    """Obtiene top gainers de Twelve Data."""
    if not TWELVE_KEY:
        return []
    cfg = shared["cfg"]
    result = []
    for exc in ["NYSE","NASDAQ","AMEX"]:
        try:
            r = requests.get(
                "https://api.twelvedata.com/stocks/market/movers",
                params={"exchange":exc,"direction":"gainers",
                        "outputsize":n,"country":"US","apikey":TWELVE_KEY},
                timeout=8
            )
            if r.status_code == 200 and "values" in r.json():
                for item in r.json()["values"]:
                    s = item.get("symbol","").strip().upper()
                    if not s or not s.isalpha() or not (1<len(s)<=5):
                        continue
                    p = float(item.get("price",0))
                    if cfg["precio_min"] <= p <= cfg["precio_max"]:
                        result.append(s)
        except Exception:
            pass
    return result


def sabueso_loop():
    """
    Hilo Sabueso: cada 30 segundos busca los top movers
    y actualiza la suscripción del WebSocket sin interrumpirlo.
    Fuentes: Yahoo day_gainers + most_actives + small_cap_gainers + Twelve Data
    """
    while True:
        try:
            with _lock:
                shared["sabueso_status"] = "🔍 Buscando..."

            # Recopilar tickers de todas las fuentes
            t1 = _yahoo_screener("day_gainers",       50)
            t2 = _yahoo_screener("most_actives",      50)
            t3 = _yahoo_screener("small_cap_gainers", 50)
            t4 = _twelve_movers(30)

            nuevos = list(dict.fromkeys(t1+t2+t3+t4))[:80]

            if nuevos:
                with _lock:
                    # Combinar con tickers existentes y manuales
                    actuales  = set(shared["ws_tickers"])
                    watchlist = set(shared["watchlist"].keys())
                    combinado = list(actuales | set(nuevos) | watchlist)[:100]
                    shared["sabueso_tickers"] = nuevos
                    shared["sabueso_last"]    = datetime.now(ET)
                    shared["sabueso_status"]  = f"✅ {len(nuevos)} movers encontrados"

                # Actualizar suscripción WebSocket (no interrumpe la conexión)
                if ws.is_alive():
                    ws.update(combinado)
        except Exception as e:
            with _lock:
                shared["sabueso_status"] = f"⚠️ Error: {str(e)[:40]}"

        time.sleep(30)  # ejecutar cada 30 segundos


@st.cache_resource
def start_sabueso():
    t = threading.Thread(target=sabueso_loop, daemon=True, name="sabueso")
    t.start()
    return t

_sabueso_thread = start_sabueso()


# ─────────────────────────────────────────────────────────────────────
#  WATCHLIST MANUAL — evaluación de tickers del usuario
# ─────────────────────────────────────────────────────────────────────

def obtener_historial_alpaca(sym: str, minutos: int = 15) -> list:
    """
    Descarga historial de velas de 1min via Alpaca REST.
    Usado para construir el baseline de la watchlist manual.
    """
    try:
        start = datetime.now(ET) - timedelta(minutes=minutos+5)
        req   = StockBarsRequest(
            symbol_or_symbols=sym,
            timeframe=TimeFrame(1, TimeFrameUnit.Minute),
            start=start,
            feed="iex",
            adjustment="raw"
        )
        bars = data_cl.get_stock_bars(req)
        df   = bars[sym].df if hasattr(bars,"__getitem__") else pd.DataFrame()
        if df is None or len(df) < 2:
            return []
        df = df.reset_index()
        result = []
        for _, row in df.iterrows():
            result.append({
                "ts":     row.get("timestamp", datetime.now(ET)),
                "open":   float(row.get("open",  0)),
                "high":   float(row.get("high",  0)),
                "low":    float(row.get("low",   0)),
                "close":  float(row.get("close", 0)),
                "volume": float(row.get("volume",0)),
            })
        return result
    except Exception:
        return []


def evaluar_watchlist(sym: str) -> dict:
    """
    Evaluación completa de un ticker de la watchlist manual.
    Descarga historial, inicializa shared_state y calcula Force.
    Clasifica: 'BUENO' (>=65), 'REGULAR' (>=40), 'MALO' (<40)
    """
    # Obtener historial
    bars = obtener_historial_alpaca(sym, 15)

    precio = 0.0
    if bars:
        precio = bars[-1]["close"]
        # Inicializar datos en shared_state
        with _lock:
            shared["bars"][sym]   = bars
            shared["prices"][sym] = precio
            # HOD/LOD del historial
            hod_h = max(b["high"]  for b in bars)
            lod_h = min(b["low"]   for b in bars)
            shared["hod"][sym] = hod_h
            shared["lod"][sym] = lod_h
            # Open price = primera barra
            shared["open_price"][sym] = bars[0]["open"]
            # Reconstruir rolling window 5min desde barras
            if sym not in shared["rolling5"]:
                shared["rolling5"][sym] = deque(maxlen=500)
            now = datetime.now(ET)
            for b in bars:
                ts_b = b.get("ts", now)
                if not isinstance(ts_b, datetime):
                    ts_b = now
                shared["rolling5"][sym].append((ts_b, b["close"], b["volume"]))
    else:
        with _lock:
            precio = shared["prices"].get(sym, 0)

    if precio <= 0:
        return {"sym":sym,"force":0,"setup":"MALO","precio":0,"error":"Sin precio"}

    cambio_dia = 0.0
    with _lock:
        op = shared["open_price"].get(sym, precio)
    if op > 0:
        cambio_dia = (precio - op) / op * 100

    ev    = calcular_force(sym, precio, cambio_dia)
    force = ev["force"]

    setup = "BUENO" if force >= 65 else ("REGULAR" if force >= 40 else "MALO")

    return {
        "sym"       : sym,
        "force"     : force,
        "setup"     : setup,
        "precio"    : precio,
        "vel1"      : ev["vel1"],
        "vel5"      : ev["vel5"],
        "rvol"      : ev["rvol"],
        "tps"       : ev["tps"],
        "hod_dist"  : ev["hod_dist"],
        "hod_break" : ev["hod_break"],
        "cambio_dia": cambio_dia,
        "detalles"  : ev["detalles"],
        "ts"        : datetime.now(ET).strftime("%H:%M:%S"),
    }


def agregar_watchlist(tickers_txt: str):
    """Agrega tickers a la watchlist manual y los suscribe al WebSocket."""
    syms = [s.strip().upper() for s in tickers_txt.split(",") if s.strip()]
    for sym in syms:
        if not sym or not sym.isalpha() or not (1<len(sym)<=5):
            continue
        with st.spinner(f"📡 Analizando {sym}..."):
            ev = evaluar_watchlist(sym)
        with _lock:
            shared["watchlist"][sym] = ev

    # Suscribir nuevos tickers al WebSocket
    all_tickers = list(set(shared["ws_tickers"]) | set(syms))
    ws.update(all_tickers)


# ─────────────────────────────────────────────────────────────────────
#  SL / TP DINÁMICO
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
                tr_list.append(max(hl,hc,lc))
            atr = sum(tr_list[-14:]) / min(len(tr_list[-14:]),14)
            sup = min(b["low"] for b in bars[-10:])
        else:
            atr = precio * 0.015
            sup = precio * 0.97

        entrada = round(precio * 1.003, 4)   # market order: slippage ~0.3%
        sl      = round(max(precio - atr*atr_mult, sup*0.998, precio*0.93), 4)
        riesgo  = precio - sl
        tp      = round(precio + riesgo * min_rr, 4)
        rr      = round((tp-precio)/max(riesgo,1e-9), 2)
        return {"entrada":entrada,"sl":sl,"tp":tp,"rr":rr,"atr":round(atr,4)}
    except Exception:
        return {"entrada":round(precio*1.003,4),"sl":round(precio*0.97,4),
                "tp":round(precio*1.06,4),"rr":2.0,"atr":round(precio*0.015,4)}


# ─────────────────────────────────────────────────────────────────────
#  EJECUCIÓN DE ÓRDENES
# ─────────────────────────────────────────────────────────────────────
def market_buy(sym: str, qty: int, sl: float, tp: float) -> tuple:
    try:
        trading.submit_order(MarketOrderRequest(
            symbol=sym, qty=qty, side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC,
            take_profit=TakeProfitRequest(limit_price=round(tp,2)),
            stop_loss=StopLossRequest(stop_price=round(sl,2))
        ))
        return True, f"✅ MARKET BUY {qty}x {sym} | SL=${sl:.4f} TP=${tp:.4f}"
    except Exception as e:
        return False, f"❌ {e}"

def market_sell(sym: str, qty: int) -> tuple:
    try:
        trading.submit_order(MarketOrderRequest(
            symbol=sym, qty=qty, side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC))
        return True, f"✅ SELL {qty}x {sym}"
    except Exception as e:
        return False, f"❌ {e}"

def get_positions():
    try:    return trading.get_all_positions()
    except: return []

def get_account():
    try:    return trading.get_account()
    except: return None


# ─────────────────────────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────────────────────────
def fbar(force: int, triple: bool = False) -> str:
    color = ("#ff0000" if triple else
             "#ff4500" if force>=80 else
             "#ff8c00" if force>=65 else
             "#ffc107" if force>=40 else "#374151")
    label = f"{'🔥'*(force//25)} {force}/100"
    return (f'<div class="fbar-bg">'
            f'<div class="fbar-fill" style="width:{force}%;background:{color}">{label}</div>'
            f'</div>')


def badge_condiciones(hod: bool, rvol: bool, tape: bool) -> str:
    h = f'<span class="b-hod">{"✅" if hod else "—"} HOD BREAK</span>'
    r = f'<span class="b-rvol">{"✅" if rvol else "—"} RVOL</span>'
    t = f'<span class="b-tape">{"✅" if tape else "—"} TAPE</span>'
    return h + " " + r + " " + t


# ─────────────────────────────────────────────────────────────────────
#  ═══════════════════ INTERFAZ PRINCIPAL ═══════════════════
# ─────────────────────────────────────────────────────────────────────
st.markdown('<h1 class="hdr">⚡ THUNDER RADAR V100</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub">TRADE IDEAS LIBRE · SCALPING · WEBSOCKET TICK-BY-TICK · ALPACA PAPER</p>',
    unsafe_allow_html=True)

SESSION = get_session()
bm = {"REGULAR":"b-reg","PRE-MARKET":"b-pre","AFTER-HOURS":"b-aft","CERRADO":"b-cls"}
hora_et = datetime.now(ET).strftime("%H:%M:%S ET")
cuenta  = get_account()

h1,h2,h3 = st.columns(3)
with h1:
    ws_st = shared["ws_status"]
    css   = "sabueso-ok" if "🟢" in ws_st else ("sabueso-run" if "CONECT" in ws_st else "lbl")
    st.markdown(
        f'<span class="badge {bm.get(SESSION,"b-cls")}">● {SESSION}</span>'
        f' &nbsp;<span class="dot"></span>'
        f'<span class="{css}" style="font-size:.73em"> WS: {ws_st}</span>',
        unsafe_allow_html=True)
with h2:
    sab_st  = shared["sabueso_status"]
    sab_css = "sabueso-ok" if "✅" in sab_st else ("sabueso-run" if "🔍" in sab_st else "lbl")
    st.markdown(
        f'<span style="color:#8b949e">🕐 {hora_et}</span><br>'
        f'<span class="{sab_css}" style="font-size:.71em">🐕 {sab_st}</span>',
        unsafe_allow_html=True)
with h3:
    if cuenta:
        eq  = float(cuenta.equity)
        pnl = eq - float(cuenta.last_equity)
        col = "#00ff88" if pnl>=0 else "#ff4444"
        st.markdown(f'<span style="color:{col}">💰 ${eq:,.2f} | P&L {pnl:+,.2f}</span>',
                    unsafe_allow_html=True)

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ── AUDIO TRIGGER ────────────────────────────────────────────
audio_tipo = shared.get("audio_tipo","0")
if audio_tipo != "0":
    st.markdown(f"""
    <script>
    const el=document.getElementById('audio-trigger');
    if(el){{el.dataset.tipo='{audio_tipo}';}}
    </script>""", unsafe_allow_html=True)
    with _lock:
        shared["audio_tipo"] = "0"

# ─────────────────────────────────────────────────────────────────────
#  BARRA LATERAL
# ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ THUNDER RADAR V100")

    st.markdown("**📡 WebSocket + Sabueso**")
    if st.button("🚀 INICIAR SISTEMA", use_container_width=True):
        # Arrancar con top gainers inmediatos
        with st.spinner("Obteniendo top movers..."):
            t1 = _yahoo_screener("day_gainers",  40)
            t2 = _yahoo_screener("most_actives", 40)
            t3 = _twelve_movers(20)
            init_tickers = list(dict.fromkeys(t1+t2+t3))[:80]
        ws.start(init_tickers)
        with _lock:
            shared["ws_tickers"] = init_tickers
        st.success(f"✅ WebSocket iniciado con {len(init_tickers)} tickers")

    n_ws = len(shared["ws_tickers"])
    n_tk = shared["ws_ticks"]
    st.markdown(f'<span style="color:#8b949e;font-size:.75em">'
                f'{n_ws} tickers | {n_tk:,} ticks recibidos</span>',
                unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**💰 Filtros de Precio**")
    precio_min_f = st.number_input("Precio Mín $", value=0.01, step=0.01, min_value=0.01)
    precio_max_f = st.number_input("Precio Máx $", value=100.0, step=1.0,  max_value=100.0)

    st.markdown("**🚨 Triple Condición HOD**")
    rvol_min_f  = st.slider("RVOL mínimo", 1.5, 10.0, 3.0, 0.5,
                             help="3.0 = 300% del promedio (recomendado para scalping)")
    hod_dist_f  = st.slider("HOD distancia máx %", 0.1, 5.0, 1.0, 0.1,
                             help="Distancia máxima al máximo del día para considerar breakout")
    min_force_f = st.slider("Force mínimo alerta", 40, 95, 65, 5)
    spike_min_f = st.slider("Spike mínimo % (1min)", 0.5, 15.0, 2.0, 0.5)

    st.markdown("**🔒 Gestión de Riesgo**")
    atr_mult_f = st.slider("ATR × Stop Loss", 0.5, 4.0, 2.0, 0.5)
    min_rr_f   = st.slider("R:R mínimo",      1.5, 4.0, 2.0, 0.5)
    qty_dflt   = st.number_input("Acciones por defecto", value=1, min_value=1)

    st.markdown("---")
    auto_ref_f = st.toggle("🔁 Auto-refresh (8 seg)", value=True)

# Actualizar config dinámica — los sliders alimentan el WebSocket en tiempo real
with _lock:
    shared["cfg"] = {
        "precio_min": precio_min_f,
        "precio_max": precio_max_f,
        "rvol_min"  : rvol_min_f,
        "min_force" : min_force_f,
        "spike_min" : spike_min_f,
        "hod_dist_pct": hod_dist_f,
    }

# ─────────────────────────────────────────────────────────────────────
#  WATCHLIST MANUAL — entrada de tickers
# ─────────────────────────────────────────────────────────────────────
st.subheader("🔍 Manual Scanner — Ingresa tickers para evaluar")

wl_col1, wl_col2 = st.columns([3, 1])
with wl_col1:
    tickers_input = st.text_input(
        "Tickers (separados por comas)",
        placeholder="PHOE, GME, TSLA, NVDA ...",
        key="ticker_input",
        label_visibility="collapsed"
    )
with wl_col2:
    if st.button("➕ AÑADIR Y EVALUAR", use_container_width=True):
        if tickers_input.strip():
            agregar_watchlist(tickers_input)
            st.rerun()

if st.button("🗑️ Limpiar watchlist", use_container_width=False):
    with _lock:
        shared["watchlist"] = {}
    st.rerun()

# Mostrar watchlist manual
with _lock:
    wl_items = list(shared["watchlist"].items())

if wl_items:
    st.markdown("#### 📋 Manual Scanner — Evaluación en Tiempo Real")
    # Re-evaluar en tiempo real con datos del WebSocket
    for sym, ev_old in wl_items:
        with _lock:
            precio_ws = shared["prices"].get(sym, ev_old.get("precio",0))
        if precio_ws > 0:
            ev_new = calcular_force(sym, precio_ws, ev_old.get("cambio_dia",0))
            force  = ev_new["force"]
            setup  = "BUENO" if force>=65 else ("REGULAR" if force>=40 else "MALO")
        else:
            force  = ev_old.get("force",0)
            setup  = ev_old.get("setup","MALO")
            ev_new = {"vel1":0,"vel5":0,"rvol":1,"tps":0,"hod_dist":0,
                      "hod_break":False,"rvol_ok":False,"tape_ok":False,
                      "detalles":{}}

        card_cls = ("manual-good" if setup=="BUENO"
                    else "manual-mid" if setup=="REGULAR" else "manual-bad")
        setup_col = ("#00ff88" if setup=="BUENO"
                     else "#ffc107" if setup=="REGULAR" else "#ff4444")
        fb = fbar(force, ev_new.get("hod_break",False))
        bdg = badge_condiciones(ev_new.get("hod_break",False),
                                 ev_new.get("rvol_ok",False),
                                 ev_new.get("tape_ok",False))

        # SL/TP para botón de compra
        orden = calc_sltp(sym, precio_ws, atr_mult_f, min_rr_f)

        col_c1, col_c2 = st.columns([4, 1])
        with col_c1:
            st.markdown(f"""
            <div class="{card_cls}">
              <span class="tkr">{sym}</span>
              &nbsp;&nbsp;
              <span style="font-size:1.4em;font-weight:900;color:{setup_col}">
                {force}/100
              </span>
              &nbsp;&nbsp;
              <b style="color:{setup_col}">{setup}</b>
              &nbsp;&nbsp;{bdg}
              <br>{fb}<br>
              <span class="lbl">Precio</span> <b>${precio_ws:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">Vel 1min</span>
              <b style="color:{'#00ff88' if ev_new['vel1']>=0 else '#ff4444'}">{ev_new['vel1']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">Vel 5min</span>
              <b style="color:{'#00ff88' if ev_new['vel5']>=0 else '#ff4444'}">{ev_new['vel5']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">RVOL</span> {ev_new['rvol']:.1f}x
              &nbsp;|&nbsp;
              <span class="lbl">Tape</span> {ev_new['tps']:.1f}t/s
              &nbsp;|&nbsp;
              <span class="lbl">HOD dist</span> {ev_new['hod_dist']:+.2f}%
              &nbsp;|&nbsp;
              <span class="lbl">SL</span> <b style="color:#ff6b6b">${orden['sl']:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">TP</span> <b style="color:#00ff88">${orden['tp']:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">R:R</span> 1:{orden['rr']}
            </div>""", unsafe_allow_html=True)

        with col_c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"🟢 Comprar {sym}", key=f"buy_wl_{sym}",
                         use_container_width=True):
                ok, msg = market_buy(sym, qty_dflt, orden["sl"], orden["tp"])
                st.success(msg) if ok else st.error(msg)
            if st.button(f"🗑️ {sym}", key=f"del_wl_{sym}",
                         use_container_width=True):
                with _lock:
                    shared["watchlist"].pop(sym, None)
                st.rerun()

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  ALERT WINDOW — alarmas automáticas (HOD + RVOL + Tape)
# ─────────────────────────────────────────────────────────────────────
with _lock:
    alertas_now = list(shared["alertas"])

n_triple = sum(1 for a in alertas_now if a.get("triple_hod"))
st.subheader(f"🚨 Alert Window — {len(alertas_now)} alertas ({n_triple} Triple HOD)")

if alertas_now:
    for al in alertas_now[:10]:
        force   = al["force"]
        triple  = al.get("triple_hod", False)
        card_c  = "alert-card" if triple else "manual-mid"
        fb      = fbar(force, triple)
        bdg     = badge_condiciones(al.get("hod_break",False),
                                     al.get("rvol_ok",False),
                                     al.get("tape_ok",False))
        vc1     = "#00ff88" if al["vel1"]>=0 else "#ff4444"
        vc5     = "#00ff88" if al["vel5"]>=0 else "#ff4444"
        orden   = calc_sltp(al["ticker"], al["precio"], atr_mult_f, min_rr_f)

        col_a1, col_a2 = st.columns([4, 1])
        with col_a1:
            st.markdown(f"""
            <div class="{card_c}">
              <span class="tkr">{'🚨' if triple else '⚡'} {al['ticker']}</span>
              &nbsp;&nbsp;
              <span class="{'s10' if force>=80 else 's8' if force>=65 else 's6'}">{force}/100</span>
              &nbsp;&nbsp;
              <span style="color:#8b949e;font-size:.78em">{al['ts']}</span>
              &nbsp;&nbsp;{bdg}
              <br>{fb}<br>
              <span class="lbl">Precio</span> <b style="color:#fff">${al['precio']:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">HOD dist</span>
              <b style="color:{'#ff4500' if al['hod_dist']>=0 else '#8b949e'}">{al['hod_dist']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">RVOL</span>
              <b style="color:{'#ff8c00' if al['rvol']>=3 else '#ffc107'}">{al['rvol']:.1f}x</b>
              &nbsp;|&nbsp;
              <span class="lbl">Vel 1min</span>
              <b style="color:{vc1}">{al['vel1']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">Vel 5min</span>
              <b style="color:{vc5}">{al['vel5']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">Tape</span> {al['tps']:.1f}t/s
              <br>
              <span class="lbl">SL</span> <b style="color:#ff6b6b">${orden['sl']:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">TP</span> <b style="color:#00ff88">${orden['tp']:.4f}</b>
              &nbsp;|&nbsp;
              <span class="lbl">R:R</span> 1:{orden['rr']}
            </div>""", unsafe_allow_html=True)

        with col_a2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"🟢 Comprar\n{al['ticker']}",
                         key=f"buy_alert_{al['ticker']}_{al['ts_raw']}",
                         use_container_width=True):
                ok,msg = market_buy(al["ticker"], qty_dflt, orden["sl"], orden["tp"])
                st.success(msg) if ok else st.error(msg)

else:
    st.markdown("""<div class="ibox">
    🟡 Esperando alertas del WebSocket...<br>
    Las alertas aparecerán cuando una acción cumpla: <b>HOD Break</b> +
    <b>RVOL ≥ 3x</b> + <b>Tape acelerado</b> simultáneamente.
    </div>""", unsafe_allow_html=True)
    if ws.is_alive():
        st.toast("🟢 WebSocket activo — escaneando en background", icon="⚡")

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  TOP 5MIN RANKING — como "5 Minutes" de Webull/Trade Ideas
# ─────────────────────────────────────────────────────────────────────
with _lock:
    ranking_now = list(shared["ranking5"])

st.subheader(f"📈 Top 5min Ranking — {len(ranking_now)} stocks (actualización en vivo)")

if ranking_now:
    rank_data = []
    for i, r in enumerate(ranking_now[:20]):
        medallas = ["🥇","🥈","🥉"] + [""] * 17
        rank_data.append({
            "#"         : f"{medallas[i]} {i+1}",
            "Ticker"    : r["ticker"],
            "Precio $"  : round(r["precio"], 4),
            "Vel 5min %": round(r["vel5"], 2),
            "Vel 1min %": round(r["vel1"], 2),
            "RVOL"      : round(r["rvol"], 1),
            "Force"     : r["force"],
            "HOD dist"  : round(r.get("hod_dist",0), 2),
            "Ticks/s"   : round(r["tps"], 1),
            "Hora"      : r.get("ts","—"),
        })

    df_rank = pd.DataFrame(rank_data)

    def cv5(v): return f"color:{'#00ff88' if v>=0 else '#ff4444'};font-weight:bold"
    def cf(v):
        if v>=80: return "background-color:#7f1d1d;color:#ff4500;font-weight:900"
        elif v>=65: return "background-color:#92400e;color:#ffc107"
        elif v>=40: return "background-color:#1a2535;color:#c9d1d9"
        else: return "color:#8b949e"
    def cr(v):
        if v>=5:  return "color:#ff4500;font-weight:900"
        elif v>=3:return "color:#ff8c00;font-weight:700"
        elif v>=2:return "color:#ffc107"
        else: return "color:#8b949e"
    fmt_r = {
        "Precio $":"${:.4f}","Vel 5min %":"{:+.2f}%","Vel 1min %":"{:+.2f}%",
        "RVOL":"{:.1f}x","Force":"{:.0f}","HOD dist":"{:+.2f}%","Ticks/s":"{:.1f}"
    }
    try:
        styled = (df_rank.style
                  .map(cv5, subset=["Vel 5min %","Vel 1min %"])
                  .map(cf,  subset=["Force"])
                  .map(cr,  subset=["RVOL"])
                  .format(fmt_r))
    except Exception:
        try:
            styled = (df_rank.style
                      .applymap(cv5, subset=["Vel 5min %","Vel 1min %"])
                      .applymap(cf,  subset=["Force"])
                      .applymap(cr,  subset=["RVOL"])
                      .format(fmt_r))
        except Exception:
            styled = df_rank.style.format(fmt_r)

    st.dataframe(styled, use_container_width=True, hide_index=True, height=380)

    # Botones de compra rápida para el top 5
    st.markdown("**⚡ Compra 1-clic — Top 5:**")
    buy_cols = st.columns(5)
    for i, r in enumerate(ranking_now[:5]):
        orden_r = calc_sltp(r["ticker"], r["precio"], atr_mult_f, min_rr_f)
        with buy_cols[i]:
            label = (f"🟢 {r['ticker']}\n"
                     f"${r['precio']:.2f}\n"
                     f"+{r['vel5']:.1f}%/5m")
            if st.button(label, key=f"buy_rank_{r['ticker']}_{i}",
                         use_container_width=True):
                ok,msg = market_buy(r["ticker"],qty_dflt,orden_r["sl"],orden_r["tp"])
                st.success(msg) if ok else st.error(msg)
else:
    st.info("El ranking se construye automáticamente cuando el WebSocket recibe datos de precio.")

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
#  PORTAFOLIO ACTIVO
# ─────────────────────────────────────────────────────────────────────
st.subheader("💼 Portafolio Activo — P&L en Tiempo Real")
posiciones = get_positions()
if posiciones:
    rows = []
    for p in posiciones:
        pp = float(p.unrealized_plpc)*100
        pu = float(p.unrealized_pl)
        ico = "🟢" if pp>=0 else "🔴"
        rows.append({
            "Ticker":p.symbol,"Qty":p.qty,
            "Entrada $":round(float(p.avg_entry_price),4),
            "Actual $": round(float(p.current_price),4),
            "P&L %":f"{ico} {pp:+.2f}%","P&L $":f"${pu:+.2f}",
            "Valor $":f"${float(p.market_value):,.2f}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    pc1,pc2,pc3 = st.columns([2,1,1])
    with pc1:
        tc = st.selectbox("Cerrar posición", [r["Ticker"] for r in rows])
    with pc2:
        if st.button("🔴 Cerrar"):
            qty_pos = int([r["Qty"] for r in rows if r["Ticker"]==tc][0])
            ok,msg = market_sell(tc, qty_pos)
            st.success(msg) if ok else st.error(msg)
    with pc3:
        if st.button("🔴 Cerrar TODO"):
            for pos in posiciones:
                market_sell(pos.symbol, int(pos.qty))
            st.warning("Cerrando todo...")
else:
    st.info("Sin posiciones abiertas.")

# ─────────────────────────────────────────────────────────────────────
#  AUTO-REFRESH
# ─────────────────────────────────────────────────────────────────────
if auto_ref_f:
    time.sleep(8)  # UI se refresca cada 8 segundos para mostrar datos WebSocket
    st.rerun()

st.markdown('<hr class="n">', unsafe_allow_html=True)
st.markdown("""<div style="text-align:center;color:#8b949e;font-size:.68em;
font-family:'Share Tech Mono',monospace">
⚡ THUNDER RADAR V100 — WEBSOCKET · SABUESO AUTOMÁTICO · ALPACA PAPER — Solo uso educativo<br>
Triple Condición HOD: HOD Breakout + RVOL ≥ 3x + Tape Speed<br>
Los resultados pasados no garantizan rendimientos futuros. Opera con responsabilidad.
</div>""", unsafe_allow_html=True)
