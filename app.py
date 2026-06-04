"""
╔══════════════════════════════════════════════════════════════════════════╗
║              THUNDER RADAR V108 — ARQUITECTURA PROFESIONAL              ║
╠══════════════════════════════════════════════════════════════════════════╣
║  BASE: V107 intacta (momentum, spikes, EMAs, SuperTrend, VWAP, ATR)    ║
║                                                                          ║
║  MÓDULO 1: Market Data híbrido Alpaca Bars + yfinance fallback          ║
║  MÓDULO 2: Low Float Detection via Finnhub (Float, MarketCap, Shares)   ║
║  MÓDULO 3: Monitor Catalizadores — noticias 24h via Finnhub             ║
║  MÓDULO 4: Scoring Multidimensional 100pts parametrizable (sidebar)     ║
║  MÓDULO 5: Alertas audibles + visuales (st.toast + HTML5 audio)         ║
╚══════════════════════════════════════════════════════════════════════════╝

requirements.txt:
    streamlit>=1.32.0
    yfinance>=0.2.40
    pandas>=2.0.0
    numpy>=1.24.0
    requests>=2.31.0
    alpaca-py>=0.20.0
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import requests
import time
import random
import warnings
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")

# ── DEPENDENCIAS OPCIONALES ─────────────────────────────────────────────
try:
    import yfinance as yf
    YF_OK = True
except Exception:
    YF_OK = False

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest, TakeProfitRequest, StopLossRequest,
        TrailingStopOrderRequest)
    from alpaca.trading.enums import OrderSide, TimeInForce
    ALPACA_OK = True
except Exception:
    ALPACA_OK = False

# ════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN DE PÁGINA
# ════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="⚡ Thunder Radar V108",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .main, .block-container {
    font-family: 'Inter', sans-serif !important;
    background-color: #F5F7FA !important;
    color: #1A2B4A !important;
}
p, span, div, label, li, td, th { color: #1A2B4A !important; }
h1, h2, h3, h4, h5 { color: #0D1F3C !important; font-weight: 700 !important; }

[data-testid="stSidebar"] {
    background-color: #E8EEF7 !important;
    border-right: 2px solid #C5D3E8 !important;
}
[data-testid="stSidebar"] * { color: #0D1F3C !important; }
[data-testid="stSidebar"] input {
    background: #FFFFFF !important; color: #0D1F3C !important;
    border: 1.5px solid #A0B4CC !important; border-radius: 6px !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: #1A56DB !important; color: #FFFFFF !important;
    border: none !important; border-radius: 6px !important; font-weight: 700 !important;
}
[data-testid="stSidebar"] .stButton > button:hover { background: #1E40AF !important; }

div[data-testid="metric-container"] {
    background: #FFFFFF !important; border: 1.5px solid #C5D3E8 !important;
    border-radius: 10px !important; padding: 10px !important;
    box-shadow: 0 1px 4px rgba(26,43,74,0.08) !important;
}
div[data-testid="metric-container"] label { color: #4A6080 !important; font-size: 0.78em !important; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #0D1F3C !important; font-weight: 700 !important; }

.stButton > button {
    border-radius: 8px !important; font-weight: 600 !important;
    font-size: 0.85em !important; border: 1.5px solid #C5D3E8 !important;
    background: #FFFFFF !important; color: #1A2B4A !important;
    transition: all 0.15s !important; padding: 6px 14px !important;
}
.stButton > button:hover { background: #1A56DB !important; color: #FFFFFF !important; border-color: #1A56DB !important; }

div[data-testid="column"]:nth-of-type(1) .stButton > button {
    background: #1A56DB !important; color: #FFFFFF !important;
    border-color: #1A56DB !important; font-size: 0.82em !important; padding: 10px 8px !important;
}
div[data-testid="column"]:nth-of-type(2) .stButton > button {
    background: #059669 !important; color: #FFFFFF !important;
    border-color: #059669 !important; font-size: 0.82em !important; padding: 10px 8px !important;
}
div[data-testid="column"]:nth-of-type(3) .stButton > button {
    background: #7C3AED !important; color: #FFFFFF !important;
    border-color: #7C3AED !important; font-size: 0.82em !important; padding: 10px 8px !important;
}
button[kind="primary"] {
    background: #DC2626 !important; color: #FFFFFF !important;
    border: none !important; font-weight: 700 !important;
}
button[kind="primary"]:hover { background: #B91C1C !important; }

.stDataFrame { border: 1.5px solid #C5D3E8 !important; border-radius: 10px !important; background: #FFFFFF !important; }
[data-testid="stDataFrameResizable"] { background: #FFFFFF !important; }

div[data-testid="stExpander"] {
    background: #FFFFFF !important; border: 1.5px solid #C5D3E8 !important;
    border-radius: 10px !important; box-shadow: 0 1px 4px rgba(26,43,74,0.06) !important;
    margin-bottom: 8px !important;
}
div[data-testid="stExpander"] summary { color: #0D1F3C !important; font-weight: 600 !important; }
div[data-testid="stAlert"] { border-radius: 8px !important; }
input, .stTextInput input {
    background: #FFFFFF !important; color: #0D1F3C !important;
    border: 1.5px solid #A0B4CC !important; border-radius: 6px !important;
}
hr { border-color: #C5D3E8 !important; margin: 10px 0 !important; }
[data-testid="stSlider"] * { color: #1A2B4A !important; }
[data-testid="stToggle"] * { color: #1A2B4A !important; }
.stCaption, small, [data-testid="stCaption"] { color: #4A6080 !important; }
[data-testid="stProgressBar"] > div { background: #1A56DB !important; }
[data-testid="stSpinner"] * { color: #1A56DB !important; }

/* Score 100pts badge */
.score-badge {
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-weight: 800; font-size: 0.9em; color: #fff;
}
.score-high { background: #059669; }
.score-mid  { background: #D97706; }
.score-low  { background: #DC2626; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
#  CONSTANTES
# ════════════════════════════════════════════════════════════════════════
ET   = ZoneInfo("America/New_York")
AK   = "PKOKUMRZBCA2YJKVZIATSPGV5J"
AS_  = "2UBriZpW7NooR1EvtowC63GcarFt7rEQFD9ofti9Ah6N"

# Finnhub — clave gratuita (sustituir con la tuya en st.secrets["finnhub_key"])
FINNHUB_API_KEY = "d8gn0rpr01qhjpmopmt0d8gn0rpr01qhjpmopmtg"
FINNHUB_KEY = FINNHUB_API_KEY  # alias

ALPACA_DATA = "https://data.alpaca.markets"

UNIVERSO_A = [
    "BJDX","PMI","DXST","VSA","LOBO","JZ","TGHL","HKIT","ABTS","WOK",
    "GURE","BVC","ICG","DBGI","OH","PRFX","OLOX","STG","REPL","AMST",
    "INM","WNW","MTVA","NCI","SNTG","MLGO","BFRI","SINT","ADAG","BXRX",
    "MGRX","CLNN","RCAT","ATXI","NKGN","ACRX","PRPH","MICS","CODA","LGCL",
    "NVAX","AGEN","MNMD","HIMS","CRSP","EDIT","SNDL","TLRY","MDJH","SRPT",
    "ACAD","RXRX","ARWR","BEAM","VERV","NTLA","FATE","BLUE",
    "COIN","HOOD","MSTR","RIOT","MARA","HUT","CIFR","BTBT","CLSK",
    "WULF","CORZ","IREN","BTDR","SDIG",
    "RIVN","LCID","CHPT","BLNK","PLUG","FCEL","NIO","XPEV","LI",
    "NKLA","WKHS","FSR","GOEV",
    "ASTS","LUNR","RKLB","ACHR","JOBY","IONQ","RGTI","SPCE",
    "SOFI","UPST","AFRM","ROOT","OPEN","DAVE","MQ","CLOV",
    "BABA","JD","PDD","BILI","IQ","TIGR","FUTU",
    "PLTR","DDOG","SNOW","CRWD","ZS","NET","CFLT","GTLB",
    "NVDA","AMD","SMCI","INTC","MU","QCOM","AVGO","MRVL","WOLF","ON",
    "TSLA","AAPL","META","AMZN","GOOGL","NFLX","MSFT","SNAP",
    "PINS","RBLX","UBER","DASH","ABNB","DKNG","GME","AMC",
    "PTON","DOCU","ZM","LYFT","ROKU","TWLO","PARA","WBD","SIRI",
    "SOXL","TQQQ","FNGU","LABU","UVXY","SQQQ","SPXS","TNA","TECL",
]
UNIVERSO_B = [
    "VRNS","LMND","ACMR","LAZR","INVZ","OUST","LIDR","AEVA","MVST",
    "XOS","HYZN","HYLN","FOXO","PAVS","BKKT","PAYO","STEP","RELY",
    "FLNC","STEM","SPWR","ENPH","SEDG","RUN","NOVA","ARRY","SHLS",
    "GFAI","BBAI","SOUN","AITX","WIMI","TAOP","CLFD","AUVI",
    "BTMX","FRGE","EBON","GRIID","NCTY","CANG","LIZI","AIXI",
    "KPLT","MLGO","CODA","NKGN","ATXI","CLNN","RCAT","BFRI",
]

# ════════════════════════════════════════════════════════════════════════
#  SESSION STATE — V107 + nuevos campos V108
# ════════════════════════════════════════════════════════════════════════
_DEFAULTS = {
    # V107 original
    "gainers":[], "movers5":[], "explosiones":[],
    "manual":{},  "top500":[],
    "status":"✅ Listo. Pulsa un botón de escaneo o usa el Scanner Manual.",
    "last_scan":None, "ciclos":0,
    "pm":0.05, "pM":500.0, "vm":5000.0, "cm":0.5,
    "tn":30,   "vel":1,
    "sl_p":2.0, "rr":2.0, "trailing_pct":2.0, "usd":2000.0,
    "sim":False,
    # V108 nuevos
    "alertas_enviadas": set(),   # M5: anti-repetición
    "fh_key": FINNHUB_API_KEY,   # M1: clave Finnhub
    # M4: parámetros scoring 100pts
    "sc_gap_thr":    30.0,   "sc_gap_pts":   20,
    "sc_float_thr":  20.0,   "sc_float_pts": 20,
    "sc_rvol_thr":   5.0,    "sc_rvol_pts":  20,
    "sc_news_pts":   20,
    "sc_vwap_pts":   20,
    "sc_alert_thr":  80,     # M5: umbral alerta
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

def _cfg(k): return st.session_state[k]

# ════════════════════════════════════════════════════════════════════════
#  UTILIDADES
# ════════════════════════════════════════════════════════════════════════
def now_et():
    return datetime.now(ET)

def sesion():
    h = now_et().hour + now_et().minute / 60.0
    if   4.0  <= h < 9.5:  return "PRE-MARKET"
    elif 9.5  <= h < 16.0: return "REGULAR"
    elif 16.0 <= h < 20.0: return "AFTER-HOURS"
    return "CERRADO"

# ════════════════════════════════════════════════════════════════════════
#  MÓDULO 1 — MARKET DATA HÍBRIDO (Alpaca Bars + yfinance fallback)
# ════════════════════════════════════════════════════════════════════════
def _alpaca_bars(sym: str, timeframe: str = "1Min", limit: int = 80):
    """
    Descarga barras OHLCV via Alpaca Data API v2.
    Más estable que yfinance en entornos de producción.
    """
    try:
        now  = now_et()
        start = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end   = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        r = requests.get(
            f"{ALPACA_DATA}/v2/stocks/{sym}/bars",
            headers={
                "APCA-API-KEY-ID":     AK,
                "APCA-API-SECRET-KEY": AS_,
                "Accept": "application/json",
            },
            params={"timeframe": timeframe, "start": start,
                    "end": end, "limit": limit,
                    "feed": "iex", "adjustment": "raw"},
            timeout=12,
        )
        if r.status_code == 200:
            bars = r.json().get("bars", [])
            if bars and len(bars) >= 3:
                df = pd.DataFrame(bars)
                df = df.rename(columns={
                    "t":"Datetime","o":"Open","h":"High",
                    "l":"Low","c":"Close","v":"Volume"})
                df["Datetime"] = pd.to_datetime(df["Datetime"])
                df = df.sort_values("Datetime").reset_index(drop=True)
                for col in ["Open","High","Low","Close","Volume"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df.dropna(subset=["Close","Volume"])
                if len(df) >= 3:
                    return df
    except Exception:
        pass
    return None

def _yf_bars(sym: str, interval: str = "1m", bars: int = 80):
    """
    Fallback: descarga via yfinance individual (nunca batch).
    """
    if not YF_OK: return None
    for attempt in range(3):
        try:
            tk = yf.Ticker(sym)
            df = tk.history(period="1d", interval=interval,
                            prepost=True, auto_adjust=True, timeout=12)
            if df is None or df.empty or len(df) < 3:
                time.sleep(0.3*(attempt+1)); continue
            df = df.reset_index()
            df.columns = [str(c).split()[0] for c in df.columns]
            need = {"Open","High","Low","Close","Volume"}
            if not need.issubset(set(df.columns)): continue
            df = df.dropna(subset=["Close","Volume"])
            if len(df) >= 3: return df.tail(bars)
        except Exception:
            if attempt < 2: time.sleep(0.4*(attempt+1))
    return None

def _dl(sym: str, interval: str = "1m", bars: int = 80):
    """
    Orquestador híbrido: intenta Alpaca primero, yfinance como fallback.
    """
    tf_map = {"1m":"1Min","2m":"2Min","5m":"5Min"}
    tf = tf_map.get(interval, "1Min")
    df = _alpaca_bars(sym, tf, bars)
    if df is not None and len(df) >= 3:
        return df
    return _yf_bars(sym, interval, bars)

def _precio_rapido(sym: str) -> float:
    try:
        # Intento 1: Alpaca snapshot
        r = requests.get(
            f"{ALPACA_DATA}/v2/stocks/{sym}/snapshot",
            headers={"APCA-API-KEY-ID":AK,"APCA-API-SECRET-KEY":AS_,"Accept":"application/json"},
            params={"feed":"iex"}, timeout=6)
        if r.status_code == 200:
            p = float(r.json().get("latestTrade",{}).get("p",0) or 0)
            if p > 0: return p
    except: pass
    try:
        # Intento 2: yfinance fast_info
        if YF_OK:
            p = float(yf.Ticker(sym).fast_info.last_price or 0)
            if p > 0: return p
    except: pass
    try:
        df = _dl(sym,"1m",3)
        if df is not None and not df.empty:
            return float(df["Close"].iloc[-1])
    except: pass
    return 0.0

# ════════════════════════════════════════════════════════════════════════
#  MÓDULO 2 — LOW FLOAT DETECTION (Finnhub Company Profile)
# ════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600)   # Cache 1 hora — fundamentales no cambian en la jornada
def finnhub_perfil(sym: str, fh_key: str) -> dict:
    """
    Obtiene Float, Shares Outstanding y Market Cap desde Finnhub.
    Cacheado con st.cache_data para no saturar la API.
    """
    resultado = {"float_m": None, "shares_m": None, "mcap_m": None}
    if not fh_key or fh_key.startswith("d0fhh"):
        # Clave demo — intenta igualmente pero sin garantía
        pass
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": sym, "token": fh_key},
            timeout=8,
        )
        if r.status_code == 200:
            d = r.json()
            shares = float(d.get("shareOutstanding", 0) or 0)
            mcap   = float(d.get("marketCapitalization", 0) or 0)
            # Finnhub da shareOutstanding en millones
            resultado["shares_m"] = round(shares, 2) if shares > 0 else None
            resultado["mcap_m"]   = round(mcap / 1000, 2) if mcap > 0 else None
            # Float no está en profile2; approximar desde shareOutstanding
            # (en penny stocks suele ser ~shares si no hay restricciones)
            resultado["float_m"]  = resultado["shares_m"]
    except Exception:
        pass
    # Segundo intento: endpoint de métricas básicas para el float real
    try:
        r2 = requests.get(
            "https://finnhub.io/api/v1/stock/metric",
            params={"symbol": sym, "metric": "all", "token": fh_key},
            timeout=8,
        )
        if r2.status_code == 200:
            m = r2.json().get("metric", {})
            float_v = float(m.get("float", 0) or 0)
            if float_v > 0:
                resultado["float_m"] = round(float_v, 2)
    except Exception:
        pass
    return resultado

def _fmt_float(val):
    """Formatea millones de acciones de forma legible."""
    if val is None: return "—"
    if val < 1:     return f"{val*1000:.0f}K"
    if val < 1000:  return f"{val:.1f}M"
    return f"{val/1000:.1f}B"

# ════════════════════════════════════════════════════════════════════════
#  MÓDULO 3 — MONITOR DE CATALIZADORES (Finnhub Company News)
# ════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=900)   # Cache 15 min — noticias cambian poco
def finnhub_noticias(sym: str, fh_key: str) -> list:
    """
    Obtiene noticias de las últimas 24h desde Finnhub.
    Retorna lista de dicts con headline, source, url, datetime.
    """
    try:
        hoy   = now_et().strftime("%Y-%m-%d")
        ayer  = (now_et() - timedelta(days=1)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": sym, "from": ayer, "to": hoy, "token": fh_key},
            timeout=8,
        )
        if r.status_code == 200:
            news = r.json()
            if isinstance(news, list) and news:
                return news[:5]  # Máximo 5 noticias
    except Exception:
        pass
    return []

def _tiene_noticias(sym: str, fh_key: str) -> tuple:
    """Retorna (bool tiene_noticias, str titular_principal)"""
    news = finnhub_noticias(sym, fh_key)
    if news:
        return True, news[0].get("headline","")[:120]
    return False, ""

# ════════════════════════════════════════════════════════════════════════
#  MÓDULO 4 — SCORING MULTIDIMENSIONAL 100 PUNTOS
# ════════════════════════════════════════════════════════════════════════
def calcular_score_100(
    cambio_d: float,
    float_m,
    rvol: float,
    tiene_noticia: bool,
    precio_sobre_vwap: bool,
    # Parámetros configurables desde sidebar
    gap_thr: float,    gap_pts: int,
    float_thr: float,  float_pts: int,
    rvol_thr: float,   rvol_pts: int,
    news_pts: int,
    vwap_pts: int,
) -> int:
    """
    Score de 0 a 100 puntos completamente parametrizable.
    Cada condición suma sus puntos configurados por el usuario.
    """
    score = 0
    if cambio_d >= gap_thr:             score += gap_pts
    if float_m is not None and float_m < float_thr:  score += float_pts
    if rvol >= rvol_thr:                score += rvol_pts
    if tiene_noticia:                   score += news_pts
    if precio_sobre_vwap:               score += vwap_pts
    return min(100, max(0, score))

# ════════════════════════════════════════════════════════════════════════
#  MÓDULO 5 — ALERTAS AUDIBLES + VISUALES (anti-repetición)
# ════════════════════════════════════════════════════════════════════════
_BEEP_HTML = """
<audio id="tr_beep" autoplay>
  <source src="data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAA
EAAQARAAIAIgAEABAAAgAGAAsAAAA=" type="audio/wav">
</audio>
<script>
(function(){
  var ctx = new (window.AudioContext||window.webkitAudioContext)();
  var osc = ctx.createOscillator();
  var gain = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.setValueAtTime(880, ctx.currentTime);
  osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.12);
  gain.gain.setValueAtTime(0.35, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
  osc.connect(gain); gain.connect(ctx.destination);
  osc.start(ctx.currentTime);
  osc.stop(ctx.currentTime + 0.35);
})();
</script>
"""

def disparar_alerta(sym: str, score: int):
    """
    M5: Lanza toast + beep HTML5 la primera vez que un ticker cruza el umbral.
    Usa session_state para evitar repeticiones en cada rerun.
    """
    clave = f"{sym}_{score//10*10}"  # Agrupa por decenas para no repetir
    if clave not in st.session_state.alertas_enviadas:
        st.session_state.alertas_enviadas.add(clave)
        st.toast(
            f"🚨 ¡Alerta! **{sym}** — Score: **{score}/100**\n"
            f"Cruza umbral de {_cfg('sc_alert_thr')} puntos",
            icon="🔥"
        )
        # Sonido HTML5 — funciona en todos los navegadores modernos
        components.html(_BEEP_HTML, height=0, scrolling=False)

def verificar_alertas(entries: list):
    """Revisa todas las filas y dispara alertas si cruzan el umbral."""
    thr = _cfg("sc_alert_thr")
    for e in entries:
        s = e.get("Score", 0)
        if s >= thr:
            disparar_alerta(e["sym"], s)

# ════════════════════════════════════════════════════════════════════════
#  ALPACA TRADING — igual que V107
# ════════════════════════════════════════════════════════════════════════
@st.cache_resource
def get_trading():
    if not ALPACA_OK: return None
    try: return TradingClient(AK, AS_, paper=True)
    except: return None

trading = get_trading()

def get_cuenta():
    if not trading: return None
    try: return trading.get_account()
    except: return None

def get_posiciones():
    if not trading: return []
    try: return trading.get_all_positions()
    except: return []

def alpaca_comprar(sym, usd, sl, tp, trailing_pct=None):
    if not trading:
        return False, "❌ alpaca-py no instalado. Añade 'alpaca-py' a requirements.txt"
    pr = _precio_rapido(sym)
    if pr <= 0: return False, f"❌ Sin precio para {sym}"
    qty = max(1, int(usd // pr))
    sl  = round(max(sl, pr*0.005), 2)
    tp  = round(max(tp, pr*1.001), 2)
    try:
        if trailing_pct and trailing_pct > 0:
            trading.submit_order(TrailingStopOrderRequest(
                symbol=sym, qty=qty, side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC, trail_percent=trailing_pct))
        else:
            trading.submit_order(MarketOrderRequest(
                symbol=sym, qty=qty, side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
                take_profit=TakeProfitRequest(limit_price=tp),
                stop_loss=StopLossRequest(stop_price=sl)))
        return True, f"✅ COMPRA {qty}×{sym} ≈${usd:,.0f} | SL=${sl:.4f} | TP=${tp:.4f}"
    except Exception as e:
        return False, f"❌ Alpaca: {str(e)[:180]}"

def alpaca_vender(sym, qty):
    if not trading: return False, "❌ Alpaca no disponible"
    try:
        trading.submit_order(MarketOrderRequest(
            symbol=sym, qty=abs(int(float(qty))),
            side=OrderSide.SELL, time_in_force=TimeInForce.GTC))
        return True, f"✅ VENTA {qty}×{sym}"
    except Exception as e: return False, f"❌ {str(e)[:120]}"

def alpaca_exit_all():
    if not trading: return False, "❌ Alpaca no disponible"
    msgs = []
    try: trading.cancel_orders(); msgs.append("✅ Órdenes canceladas")
    except Exception as e: msgs.append(f"⚠️ {e}")
    try:
        for p in trading.get_all_positions():
            try:
                trading.submit_order(MarketOrderRequest(
                    symbol=p.symbol, qty=abs(int(float(p.qty))),
                    side=OrderSide.SELL, time_in_force=TimeInForce.GTC))
                msgs.append(f"✅ SELL {p.qty}×{p.symbol}")
            except Exception as e: msgs.append(f"⚠️ {e}")
    except Exception as e: msgs.append(f"⚠️ {e}")
    return True, " | ".join(msgs) if msgs else "✅ Sin posiciones"

# ════════════════════════════════════════════════════════════════════════
#  CANDIDATOS — Yahoo screener (igual que V107)
# ════════════════════════════════════════════════════════════════════════
_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

def _yahoo_screener(scr_id="day_gainers", count=200):
    ua = random.choice(_UAS)
    hdr = {"User-Agent":ua,"Accept":"application/json","Referer":"https://finance.yahoo.com/"}
    for base in ["https://query2.finance.yahoo.com","https://query1.finance.yahoo.com"]:
        for att in range(3):
            try:
                r = requests.get(f"{base}/v1/finance/screener/predefined/saved",
                    headers=hdr, params={"scrIds":scr_id,"count":count,
                    "formatted":"false","lang":"en-US","region":"US"}, timeout=15)
                if r.status_code == 429:
                    time.sleep(2**att + random.uniform(0,1)); continue
                if r.status_code != 200: break
                q = r.json().get("finance",{}).get("result",[{}])[0].get("quotes",[])
                if q: return q
            except: time.sleep(1)
    return []

# ════════════════════════════════════════════════════════════════════════
#  INDICADORES TÉCNICOS — intactos de V107
# ════════════════════════════════════════════════════════════════════════
def _ema(s,n):
    n=max(2,min(n,max(2,len(s)-1)))
    return s.ewm(span=n,adjust=False).mean()

def _rsi(s,n=14):
    if len(s)<4: return 50.0
    d=s.diff()
    g=d.where(d>0,0.0).rolling(min(n,max(1,len(s)-1))).mean()
    l=(-d.where(d<0,0.0)).rolling(min(n,max(1,len(s)-1))).mean()
    rs=g/l.replace(0,1e-9)
    v=float((100-100/(1+rs)).fillna(50).iloc[-1])
    return round(max(0.0,min(100.0,v)),1)

def _atr(df,n=14):
    try:
        hl=df["High"]-df["Low"]
        hc=(df["High"]-df["Close"].shift()).abs()
        lc=(df["Low"]-df["Close"].shift()).abs()
        a=pd.concat([hl,hc,lc],axis=1).max(axis=1).rolling(min(n,max(1,len(df)-1))).mean()
        v=float(a.iloc[-1])
        return round(v,6) if not np.isnan(v) else round(float(df["Close"].iloc[-1])*0.015,6)
    except: return round(float(df["Close"].iloc[-1])*0.015,6)

def _vwap(df):
    try:
        tp=(df["High"]+df["Low"]+df["Close"])/3
        cv=df["Volume"].replace(0,np.nan).fillna(1).cumsum()
        vwp=(tp*df["Volume"]).cumsum()/cv
        return round(float(vwp.iloc[-1]),6)
    except: return round(float(df["Close"].iloc[-1]),6)

def _supertrend(df,n=10,m=3.0):
    try:
        if len(df)<n+2:
            p=float(df["Close"].iloc[-1]); return 1,round(p*0.97,6)
        hl=df["High"]-df["Low"]
        hc=(df["High"]-df["Close"].shift()).abs()
        lc=(df["Low"]-df["Close"].shift()).abs()
        a=pd.concat([hl,hc,lc],axis=1).max(axis=1).rolling(n).mean()
        mid=(df["High"]+df["Low"])/2
        ub=mid+m*a; lb=mid-m*a
        d=pd.Series(1,index=df.index,dtype=float)
        for i in range(1,len(df)):
            c=df["Close"].iloc[i]
            if c>ub.iloc[i-1]: d.iloc[i]=1
            elif c<lb.iloc[i-1]: d.iloc[i]=-1
            else: d.iloc[i]=d.iloc[i-1]
        sv=lb.iloc[-1] if d.iloc[-1]==1 else ub.iloc[-1]
        return int(d.iloc[-1]),round(float(sv),6)
    except:
        p=float(df["Close"].iloc[-1]); return 1,round(p*0.97,6)

def _macd_h(s):
    try:
        m=_ema(s,12)-_ema(s,26)
        return round(float((m-_ema(m,9)).iloc[-1]),6)
    except: return 0.0

def _sr(df,n=20):
    nn=min(n,len(df))
    sup=round(float(df["Low"].rolling(nn).min().iloc[-1]),6)
    res=round(float(df["High"].rolling(nn).max().iloc[-1]),6)
    return sup,res

# ════════════════════════════════════════════════════════════════════════
#  PUNTUACIONES 5D — intactas de V107
# ════════════════════════════════════════════════════════════════════════
def calcular_scores(precio,ema9,ema20,vwap_v,st_dir,
                    rsi_v,mh,rvol,roc1,roc5,atr_v,
                    c1,o1,h1,l1,cambio_d):
    # TA
    ta=0.0
    if precio>vwap_v:  ta+=1.5
    if precio>ema9:    ta+=1.5
    if precio>ema20:   ta+=1.0
    if st_dir==1:      ta+=2.0
    if 50<rsi_v<=70:   ta+=1.0
    elif rsi_v>70:     ta+=0.5
    if mh>0:           ta+=1.0
    if rvol>=1.5:      ta+=0.5
    if roc1>0:         ta+=0.5
    if roc5>1:         ta+=0.5
    ta=round(min(10,max(1,ta)),1)
    # TB
    tb=0.0
    if precio<vwap_v:          tb+=1.5
    if precio<ema9:            tb+=1.5
    if precio<ema20:           tb+=1.0
    if st_dir==-1:             tb+=2.0
    if rsi_v<40:               tb+=1.0
    elif rsi_v<30:             tb+=1.5
    if mh<0:                   tb+=1.0
    if rvol>=1.5 and roc1<0:   tb+=0.5
    if roc1<0:                 tb+=0.5
    if roc5<-1:                tb+=0.5
    tb=round(min(10,max(1,tb)),1)
    # TV
    if   rvol>=10: tv=10.0
    elif rvol>=5:  tv=9.0
    elif rvol>=3:  tv=7.5+(rvol-3)*0.75
    elif rvol>=2:  tv=6.0+(rvol-2)*1.5
    elif rvol>=1.5:tv=4.5+(rvol-1.5)*3.0
    elif rvol>=1:  tv=3.0+(rvol-1.0)*3.0
    else:          tv=max(1.0,rvol*3.0)
    tv=round(min(10,max(1,tv)),1)
    # TE
    rng=h1-l1; cpo=abs(c1-o1); pct_c=cpo/max(rng,1e-9)
    te=0.0
    if roc5>5:    te+=4.0
    elif roc5>3:  te+=3.0
    elif roc5>1.5:te+=2.0
    elif roc5>.5: te+=1.0
    if rvol>=3:   te+=2.5
    elif rvol>=2: te+=1.5
    elif rvol>=1.5:te+=0.8
    if pct_c>=.7: te+=2.0
    elif pct_c>=.5:te+=1.2
    if c1>o1:     te+=0.5
    te=round(min(10,max(1,te)),1)
    # TC
    tc=ta*0.5
    if 55<=rsi_v<=75:   tc+=2.5
    elif 50<=rsi_v<55:  tc+=1.5
    elif 75<rsi_v<=85:  tc+=1.0
    elif rsi_v>85:      tc-=1.0
    elif rsi_v<40:      tc-=2.0
    if tv>=7 and ta>=7: tc+=1.5
    if te>=7:           tc+=1.0
    if cambio_d>50:     tc+=0.5
    elif cambio_d>20:   tc+=0.3
    if st_dir==1:       tc+=0.5
    if tb>ta:           tc-=1.5
    if rsi_v>90:        tc-=2.0
    tc=round(min(10,max(1,tc)),1)
    explosion=(roc5>1.5 and rvol>=2.0 and pct_c>=0.50 and c1>o1)
    if   tc>=8 and ta>=7:   rec="🟢 COMPRAR AHORA — Momentum fuerte"
    elif tc>=6.5 and ta>=6: rec="🟢 COMPRAR — Buena configuración"
    elif tc>=5 and ta>=5:   rec="🟡 VIGILAR — Confirmar con volumen"
    elif tb>=7:             rec="🔴 EVITAR — Presión bajista fuerte"
    elif tb>=5:             rec="🟠 PRECAUCIÓN — Presión bajista"
    else:                   rec="⚪ NEUTRAL — Sin señal clara"
    return dict(ta=ta,tb=tb,tv=tv,te=te,tc=tc,
                rec=rec,explosion=explosion,pct_c=round(pct_c*100,1))

# ════════════════════════════════════════════════════════════════════════
#  ANÁLISIS COMPLETO — V107 + campos nuevos V108
# ════════════════════════════════════════════════════════════════════════
def analizar_ticker(sym: str, interval: str = "1m") -> dict:
    ts_now = now_et().strftime("%H:%M:%S")
    df = _dl(sym, interval, 80)
    if df is None or len(df) < 4:
        if interval == "1m": df = _dl(sym, "5m", 40)
    if df is None or len(df) < 4:
        return {"sym":sym,"error":f"Sin datos para '{sym}'.","ts":ts_now}
    try:
        precio  = round(float(df["Close"].iloc[-1]),6)
        open_d  = float(df["Open"].iloc[0])
        cambio  = round((precio-open_d)/max(open_d,1e-9)*100,2)
        vol_ult = float(df["Volume"].iloc[-1])
        vol_avg = float(df["Volume"].mean()) if len(df)>1 else vol_ult
        rvol    = round(vol_ult/max(vol_avg,1),2)
        vol_tot = float(df["Volume"].sum())
        liq_m   = round(vol_ult*precio/1_000_000,3)

        rsi_v=_rsi(df["Close"]); atr_v=_atr(df)
        ema9=round(float(_ema(df["Close"],9).iloc[-1]),6)
        ema20=round(float(_ema(df["Close"],20).iloc[-1]),6)
        vwap_v=_vwap(df); st_dir,st_val=_supertrend(df)
        mh=_macd_h(df["Close"]); sup,res=_sr(df)

        roc1=roc5=0.0
        if len(df)>=2:
            roc1=round((float(df["Close"].iloc[-1])-float(df["Close"].iloc[-2]))
                       /max(float(df["Close"].iloc[-2]),1e-9)*100,3)
        if len(df)>=6:
            roc5=round((float(df["Close"].iloc[-1])-float(df["Close"].iloc[-6]))
                       /max(float(df["Close"].iloc[-6]),1e-9)*100,3)

        c1=float(df["Close"].iloc[-1]); o1=float(df["Open"].iloc[-1])
        h1=float(df["High"].iloc[-1]);  l1=float(df["Low"].iloc[-1])

        sc=calcular_scores(precio,ema9,ema20,vwap_v,st_dir,
                           rsi_v,mh,rvol,roc1,roc5,atr_v,c1,o1,h1,l1,cambio)

        velas=("🕯️↑↑↑" if roc5>3 else "🕯️↑↑" if roc5>1.5
               else "🕯️↑" if roc5>0 else "🕯️↓↓" if roc5<-1 else "🕯️→")
        proy=(round(precio+(res-precio)*min(1,sc["ta"]/10),6)
              if res>precio else round(precio*(1+sc["ta"]/100),6))

        sl_atr=round(precio-2.0*atr_v,6)
        tp_atr=round(precio+4.0*atr_v,6)
        trailing_sl=round(2.0*atr_v/max(precio,1e-9)*100,2)

        # M2: fundamentales (cacheado)
        fh_key = _cfg("fh_key")
        perfil = finnhub_perfil(sym, fh_key)

        # M3: noticias (cacheado)
        tiene_noticia, titular = _tiene_noticias(sym, fh_key)

        # M4: score 100 puntos
        sobre_vwap = precio > vwap_v
        score_100 = calcular_score_100(
            cambio_d=cambio,
            float_m=perfil["float_m"],
            rvol=rvol,
            tiene_noticia=tiene_noticia,
            precio_sobre_vwap=sobre_vwap,
            gap_thr=_cfg("sc_gap_thr"),   gap_pts=_cfg("sc_gap_pts"),
            float_thr=_cfg("sc_float_thr"),float_pts=_cfg("sc_float_pts"),
            rvol_thr=_cfg("sc_rvol_thr"),  rvol_pts=_cfg("sc_rvol_pts"),
            news_pts=_cfg("sc_news_pts"),
            vwap_pts=_cfg("sc_vwap_pts"),
        )

        return {
            "sym":sym,"precio":precio,"cambio_dia":cambio,
            "roc1":roc1,"roc5":roc5,"rvol":rvol,
            "rsi":rsi_v,"atr":atr_v,"vwap":vwap_v,
            "ema9":ema9,"ema20":ema20,"st_dir":st_dir,"st_val":st_val,
            "macd_h":mh,"sup":sup,"res":res,
            "ta":sc["ta"],"tb":sc["tb"],"tv":sc["tv"],
            "te":sc["te"],"tc":sc["tc"],
            "proy":proy,"explosion":sc["explosion"],"pct_c":sc["pct_c"],
            "velas":velas,"vol_ult":int(vol_ult),"vol_tot":int(vol_tot),
            "liq_m":liq_m,"recomendacion":sc["rec"],
            "sl":sl_atr,"tp":tp_atr,"trailing_sl_pct":trailing_sl,
            # V108 nuevos
            "float_m":perfil["float_m"],
            "shares_m":perfil["shares_m"],
            "mcap_m":perfil["mcap_m"],
            "tiene_noticia":tiene_noticia,
            "titular":titular,
            "score_100":score_100,
            "sobre_vwap":sobre_vwap,
            "ts":now_et().strftime("%H:%M:%S"),"error":None,
        }
    except Exception as e:
        return {"sym":sym,"error":f"Error: {str(e)[:80]}","ts":ts_now}

# ════════════════════════════════════════════════════════════════════════
#  MOTOR DE ESCANEO — V107 + Score 100pts + Fundamentales
# ════════════════════════════════════════════════════════════════════════
def ejecutar_escaneo(prog_bar, prog_txt, modo="completo"):
    pm=_cfg("pm"); pM=_cfg("pM"); vm=_cfg("vm"); cm=_cfg("cm")
    tn=_cfg("tn"); vel=_cfg("vel")
    interval=f"{vel}m" if vel>=2 else "1m"

    candidatos={}
    prog_txt.markdown("📡 **Conectando con Yahoo Finance screener...**")
    prog_bar.progress(5)

    for scr_id in ["day_gainers","most_actives","small_cap_gainers"]:
        for q in _yahoo_screener(scr_id,200):
            s=q.get("symbol","").strip().upper()
            if not s or "." in s or len(s)>7: continue
            p=float(q.get("regularMarketPrice",0) or 0)
            v=float(q.get("regularMarketVolume",0) or 0)
            c=float(q.get("regularMarketChangePercent",0) or 0)
            if p>0 and s not in candidatos:
                candidatos[s]={"price":p,"chg":c,"vol":v}
        time.sleep(0.3)

    prog_bar.progress(20)
    prog_txt.markdown(f"📡 **{len(candidatos)} screener** + universo")

    universo=UNIVERSO_A[:]
    if modo in ("completo","top500"): universo+=UNIVERSO_B
    for s in universo:
        if s not in candidatos:
            candidatos[s]={"price":0,"chg":0,"vol":0}

    lista_scr=sorted([(s,d) for s,d in candidatos.items() if d["price"]>0],
                     key=lambda x:-x[1]["chg"])
    lista_uni=[(s,d) for s,d in candidatos.items() if d["price"]==0]

    cola=(lista_scr[:100] if modo=="momentum"
          else lista_scr+lista_uni if modo=="top500"
          else lista_scr[:70]+lista_uni[:50])
    cola=cola[:min(len(cola),tn*3+30)]

    gainers_r=[]; movers5_r=[]; exp_r=[]; top500_r=[]
    procesados=0

    for sym,snap in cola:
        procesados+=1
        prog_bar.progress(min(96, 20+int(procesados/len(cola)*76)))
        prog_txt.markdown(f"🔍 **[{procesados}/{len(cola)}]** `{sym}`...")

        if snap["price"]>0:
            if not (pm<=snap["price"]<=pM): continue
            if snap["chg"]<cm: continue

        ev=analizar_ticker(sym,interval)
        if ev.get("error"): continue

        precio=ev["precio"]; vol_tot=ev["vol_tot"]; cambio_d=ev["cambio_dia"]
        if not (pm<=precio<=pM): continue
        if vol_tot<vm: continue
        if cambio_d<cm: continue

        row={
            "sym":sym,
            "Score":ev["score_100"],        # M4 — columna prioritaria
            "Precio $":round(precio,4),
            "Cambio %":round(cambio_d,2),
            "TA":ev["ta"],"TB":ev["tb"],"TV":ev["tv"],"TE":ev["te"],"TC":ev["tc"],
            "RSI":ev["rsi"],"RVOL":round(ev["rvol"],1),
            "ROC 5m %":round(ev["roc5"],2),
            "Vol (M)":round(vol_tot/1_000_000,2),
            "Velas":ev["velas"],
            "Float":_fmt_float(ev.get("float_m")),   # M2
            "MCap(M$)":f"${ev.get('mcap_m') or '—'}M",  # M2
            "📰":("📰 Sí" if ev.get("tiene_noticia") else "—"),  # M3
            "Proy $":round(ev["proy"],4),
            # Internos
            "_sl":ev["sl"],"_tp":ev["tp"],"_tsl":ev["trailing_sl_pct"],
            "_cd":cambio_d,"_r5":ev["roc5"],"_exp":ev["explosion"],
            "_rec":ev["recomendacion"],"_tc":ev["tc"],
            "_titular":ev.get("titular",""),
            "_score":ev["score_100"],
        }
        gainers_r.append(row); top500_r.append(row)
        if abs(ev["roc5"])>=0.3: movers5_r.append(row)
        if ev["explosion"]:      exp_r.append(row)
        time.sleep(0.04)

    # Ordenar por Score 100 como criterio principal
    gainers_r.sort(key=lambda x:(-x["_score"],-x["_cd"]))
    movers5_r.sort(key=lambda x:(-x["_score"],-x["_r5"]))
    exp_r.sort(key=lambda x:(-x["_score"],-x["_r5"]))
    top500_r.sort(key=lambda x:-x["_score"])

    st.session_state.gainers    =gainers_r[:tn]
    st.session_state.movers5    =movers5_r[:tn]
    st.session_state.explosiones=(exp_r+st.session_state.explosiones)[:50]
    st.session_state.top500     =top500_r[:500]
    st.session_state.last_scan  =now_et()
    st.session_state.ciclos    +=1

    ng=len(gainers_r); nm=len(movers5_r); ne=len(exp_r)
    st.session_state.status=(
        f"✅ {ng} gainers · {nm} movers · {ne} explosiones"
        f" — {now_et().strftime('%H:%M:%S ET')}")
    prog_bar.progress(100)
    prog_txt.markdown("✅ **Completado**")

    # M5: verificar alertas en todos los resultados
    verificar_alertas(gainers_r + movers5_r + exp_r)

# ════════════════════════════════════════════════════════════════════════
#  SIMULACIÓN — V107 + campos V108
# ════════════════════════════════════════════════════════════════════════
def generar_simulacion():
    tn=_cfg("tn")
    SYMS=["BJDX","PMI","DXST","VSA","TGHL","HKIT","JZ","ABTS","WOK","GURE",
          "BVC","ICG","DBGI","OH","PRFX","OLOX","STG","TSLA","NVDA","GME",
          "AMC","MSTR","PLTR","RIVN","COIN","HOOD","MARA","NIO","SOFI",
          "SNDL","SPCE","RIOT","IONQ","RGTI","ASTS","RKLB","AMD","SMCI",
          "AAPL","META","SNAP","RBLX","UBER","DASH","LGCL","LOBO"]
    gl=[]; ml=[]; el=[]; t5=[]
    for s in SYMS:
        pr=round(random.uniform(0.05,80),4)
        cd=round(random.uniform(1,400),2)
        r5=round(random.uniform(-2,25),2)
        rv=round(random.uniform(0.5,12),1)
        ri=round(random.uniform(28,88),1)
        at=round(pr*random.uniform(0.010,0.030),6)
        vol=int(random.uniform(50_000,50_000_000))
        float_sim=round(random.uniform(0.5,200),1)
        tiene_n=random.random()>0.6
        sc=calcular_scores(pr,pr*0.98,pr*0.95,pr*0.97,1,
                           ri,random.uniform(-0.003,0.003),
                           rv,r5/5,r5,at,pr,pr*0.99,pr*1.02,pr*0.98,cd)
        score_100=calcular_score_100(
            cd,float_sim,rv,tiene_n,pr>pr*0.97,
            _cfg("sc_gap_thr"),_cfg("sc_gap_pts"),
            _cfg("sc_float_thr"),_cfg("sc_float_pts"),
            _cfg("sc_rvol_thr"),_cfg("sc_rvol_pts"),
            _cfg("sc_news_pts"),_cfg("sc_vwap_pts"),
        )
        velas="🕯️↑↑↑" if r5>3 else "🕯️↑↑" if r5>1 else "🕯️↑" if r5>0 else "🕯️↓"
        row={
            "sym":s,"Score":score_100,
            "Precio $":pr,"Cambio %":cd,
            "TA":sc["ta"],"TB":sc["tb"],"TV":sc["tv"],
            "TE":sc["te"],"TC":sc["tc"],
            "RSI":ri,"RVOL":rv,"ROC 5m %":r5,
            "Vol (M)":round(vol/1_000_000,2),"Velas":velas,
            "Float":_fmt_float(float_sim),
            "MCap(M$)":f"${round(float_sim*pr,1)}M",
            "📰":("📰 Sí" if tiene_n else "—"),
            "Proy $":round(pr*(1+sc["ta"]/100),4),
            "_sl":round(pr-2*at,6),"_tp":round(pr+4*at,6),
            "_tsl":round(2*at/max(pr,1e-9)*100,2),
            "_cd":cd,"_r5":r5,"_exp":sc["explosion"],
            "_rec":sc["rec"],"_tc":sc["tc"],"_score":score_100,
            "_titular":"Noticia de ejemplo: earnings positivos" if tiene_n else "",
        }
        gl.append(row); t5.append(row)
        if abs(r5)>=0.3: ml.append(row)
        if row["_exp"]: el.append(row)
    gl.sort(key=lambda x:(-x["_score"],-x["_cd"]))
    ml.sort(key=lambda x:(-x["_score"],-x["_r5"]))
    t5.sort(key=lambda x:-x["_score"])
    st.session_state.gainers    =gl[:tn]
    st.session_state.movers5    =ml[:tn]
    st.session_state.explosiones=(el+st.session_state.explosiones)[:50]
    st.session_state.top500     =t5[:500]
    st.session_state.last_scan  =now_et()
    st.session_state.ciclos    +=1
    st.session_state.status=(
        f"🟠 SIM: {len(gl)} gainers · {len(ml)} movers · "
        f"{len(el)} explosiones — {now_et().strftime('%H:%M:%S')}")
    verificar_alertas(gl+ml+el)

# ════════════════════════════════════════════════════════════════════════
#  HELPERS UI
# ════════════════════════════════════════════════════════════════════════
_COLS=["sym","Score","Precio $","Cambio %","TA","TB","TV","TE","TC",
       "RSI","RVOL","ROC 5m %","Vol (M)","Float","MCap(M$)","📰","Velas","Proy $"]

def _mk_df(entries):
    if not entries: return pd.DataFrame()
    rows=[{"Ticker" if c=="sym" else c: e.get(c,e.get("sym",""))
           for c in _COLS} for e in entries]
    return pd.DataFrame(rows)

def _style_df(df):
    if df.empty: return df.style
    def c_score(v):
        v=int(v) if str(v).isdigit() else 0
        if v>=80: return "color:#065F46;font-weight:800;background:#D1FAE5;font-size:1.05em"
        if v>=60: return "color:#065F46;font-weight:700"
        if v>=40: return "color:#92400E;font-weight:600"
        return "color:#991B1B"
    def c_ta(v):
        if v>=8: return "color:#065F46;font-weight:800;background:#D1FAE5"
        if v>=6: return "color:#065F46;font-weight:600"
        if v>=4: return "color:#374151"
        return "color:#991B1B"
    def c_tb(v):
        if v>=8: return "color:#991B1B;font-weight:800;background:#FEE2E2"
        if v>=6: return "color:#991B1B;font-weight:600"
        return "color:#374151"
    def c_tc(v):
        if v>=8: return "color:#1E40AF;font-weight:800;font-size:1.05em"
        if v>=6: return "color:#1E40AF;font-weight:700"
        if v>=4: return "color:#92400E"
        return "color:#991B1B"
    def c_pct(v):
        if v>50: return "color:#065F46;font-weight:700"
        if v>10: return "color:#065F46;font-weight:600"
        if v>0:  return "color:#065F46"
        return "color:#991B1B"
    def c_rv(v):
        if v>=5: return "color:#7C2D12;font-weight:700"
        if v>=3: return "color:#C2410C;font-weight:600"
        if v>=2: return "color:#B45309;font-weight:600"
        return "color:#374151"
    def c_news(v):
        return "color:#1E40AF;font-weight:700" if "Sí" in str(v) else "color:#9CA3AF"
    fmt={
        "Precio $":"${:.4f}","Cambio %":"{:+.2f}%",
        "TA":"{:.1f}","TB":"{:.1f}","TV":"{:.1f}","TE":"{:.1f}","TC":"{:.1f}",
        "RSI":"{:.0f}","RVOL":"{:.1f}×","ROC 5m %":"{:+.2f}%",
        "Vol (M)":"{:.2f}M","Proy $":"${:.4f}",
    }
    try:
        s=(df.style
           .map(c_score, subset=["Score"])
           .map(c_ta,    subset=["TA","TV","TE"])
           .map(c_tb,    subset=["TB"])
           .map(c_tc,    subset=["TC"])
           .map(c_pct,   subset=["Cambio %"])
           .map(c_rv,    subset=["RVOL"])
           .map(c_news,  subset=["📰"])
           .format({k:v for k,v in fmt.items() if k in df.columns})
           .set_properties(**{"text-align":"center","font-size":"0.82em",
                               "background-color":"#FFFFFF","color":"#1A2B4A"})
           .set_table_styles([{
               "selector":"thead th",
               "props":[("background","#EEF2FF"),("color","#1E3A5F"),
                        ("font-size","0.78em"),("font-weight","700"),
                        ("border-bottom","2px solid #C5D3E8"),
                        ("padding","7px 9px"),("text-align","center")]
           },{"selector":"tbody tr:nth-child(even)","props":[("background","#F8FAFF")]},
             {"selector":"tbody tr:hover","props":[("background","#DBEAFE")]}]))
    except:
        s=df.style.format({k:v for k,v in fmt.items() if k in df.columns})
    return s

def _barra(label,val,low_good=False):
    pct=int((val-1)/9*100)
    color=("#059669" if (val<=3 if low_good else val>=7)
           else "#D97706" if (val<=5 if low_good else val>=5) else "#DC2626")
    return (f'<div style="margin:4px 0">'
            f'<small style="color:#4A6080;font-size:.73em;font-weight:600">{label}</small>'
            f'<div style="background:#E5E7EB;border-radius:5px;height:18px;margin-top:3px;overflow:hidden;border:1px solid #D1D5DB">'
            f'<div style="width:{pct}%;height:100%;background:{color};font-size:.69em;font-weight:700;color:#fff;'
            f'display:flex;align-items:center;justify-content:center;min-width:28px">{val:.1f}</div>'
            f'</div></div>')

def _botones_compra_rapida(entries, prefijo):
    top5=entries[:5]
    if not top5: return
    st.markdown("**⚡ Compra 1-clic — Top 5:**")
    cols=st.columns(5)
    for i,e in enumerate(top5):
        sym=e["sym"]; pr=e["Precio $"]
        sl=e.get("_sl",round(pr*(1-st.session_state.sl_p/100),4))
        tp=e.get("_tp",round(pr*(1+st.session_state.sl_p/100*st.session_state.rr),4))
        tsl=e.get("_tsl",st.session_state.trailing_pct)
        sc_=e.get("Score",0); cd=e.get("Cambio %",0)
        with cols[i]:
            lbl=f"🟢 {sym}\n${pr:.2f} | {cd:+.1f}%\nScore:{sc_} · TC:{e.get('TC',5):.0f}"
            if st.button(lbl,key=f"{prefijo}_{sym}_{i}",use_container_width=True):
                if not st.session_state.sim:
                    ok,msg=alpaca_comprar(sym,st.session_state.usd,sl,tp,tsl)
                    if ok: st.success(msg)
                    else:  st.error(msg)
                else:
                    st.info(f"🟠 Sim: COMPRARÍA {sym} a ${pr:.4f}")

# ════════════════════════════════════════════════════════════════════════
#  ═══════════════ INTERFAZ PRINCIPAL ════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════
ses   =sesion()
hora  =now_et().strftime("%H:%M:%S ET")
ls_dt =st.session_state.last_scan
ls_str=ls_dt.strftime("%H:%M:%S ET") if ls_dt else "—"
cuenta=get_cuenta()

# ── HEADER ──────────────────────────────────────────────────────────────
h1c,h2c,h3c,h4c=st.columns([3.5,1,1,1.3])
with h1c:
    st.markdown("## ⚡ Thunder Radar V108")
    st.caption("NYSE · NASDAQ · Alpaca Data + Finnhub · Pre-Market · Regular · After-Hours")
with h2c:
    ico={"REGULAR":"🟢","PRE-MARKET":"🟡","AFTER-HOURS":"🔵","CERRADO":"⚫"}
    st.metric("Sesión",f"{ico.get(ses,'⚫')} {ses}")
with h3c:
    st.metric("Hora ET",hora)
with h4c:
    if cuenta:
        eq=float(cuenta.equity or 0)
        pnl=eq-float(cuenta.last_equity or eq)
        st.metric("Cuenta Paper",f"${eq:,.0f}",delta=f"${pnl:+,.0f}")
    else:
        st.metric("Paper","alpaca-py requerido" if not ALPACA_OK else "Sin conexión")

st.divider()

# ── STATUS ──────────────────────────────────────────────────────────────
sc1,sc2,sc3=st.columns([5,1,1])
with sc1:
    s=st.session_state.status
    if "✅" in s:    st.success(s)
    elif "🟠" in s:  st.warning(s)
    elif "⚠️" in s: st.error(s)
    else:             st.info(s)
with sc2: st.metric("Ciclos",st.session_state.ciclos)
with sc3: st.metric("Último scan",ls_str)

st.divider()

# ════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ Thunder Radar V108")
    st.caption("Panel de control")

    if st.button("🔴 EXIT ALL — CERRAR TODO",use_container_width=True):
        ok,msg=alpaca_exit_all()
        if ok: st.success(msg[:200])
        else:  st.error(msg[:200])

    st.divider()
    new_sim=st.toggle("🟠 Modo Simulación",value=st.session_state.sim)
    st.session_state.sim=new_sim
    if new_sim:
        st.warning("⚠️ Datos ficticios activos")
        if st.button("🎲 Simular ahora",use_container_width=True):
            generar_simulacion(); st.rerun()

    st.divider()
    st.markdown("**📡 Filtros de Escaneo**")
    st.session_state.pm=st.number_input("Precio Mín $",value=st.session_state.pm,step=0.05,min_value=0.01,format="%.2f")
    st.session_state.pM=st.number_input("Precio Máx $",value=st.session_state.pM,step=10.0,max_value=9999.0)

    vm_opts=[0,5_000,10_000,50_000,100_000,500_000,1_000_000]
    vm_lbls=["Sin filtro","5K","10K","50K","100K","500K","1M"]
    vm_idx=st.select_slider("Vol mín",options=list(range(len(vm_opts))),
                             value=2,format_func=lambda x:vm_lbls[x])
    st.session_state.vm=float(vm_opts[vm_idx])
    st.caption(f"Volumen mínimo: **{vm_lbls[vm_idx]}**")

    st.session_state.cm=st.slider("Cambio mín %",-5.0,30.0,st.session_state.cm,0.5)
    st.session_state.tn=st.slider("Top N por panel",5,50,st.session_state.tn,5)

    st.divider()
    st.markdown("**🕯️ Intervalo Velas**")
    st.session_state.vel=st.select_slider("Velocidad",options=[1,2,5],
                                           format_func=lambda x:f"{x}min",
                                           value=st.session_state.vel)

    st.divider()
    st.markdown("**💰 Parámetros de Trade**")
    st.session_state.sl_p=st.slider("Stop Loss %",0.5,15.0,st.session_state.sl_p,0.5)
    st.session_state.rr  =st.slider("R:R mínimo",1.0,5.0,st.session_state.rr,0.5)
    st.session_state.trailing_pct=st.slider("Trailing Stop %",0.5,10.0,st.session_state.trailing_pct,0.5)
    st.session_state.usd =st.number_input("$ por trade",value=st.session_state.usd,step=100.0,min_value=50.0)

    # ── M4: SCORING 100 PUNTOS ─────────────────────────────────────────
    st.divider()
    st.markdown("**⚡ Configuración de Scoring Dinámico**")
    st.caption("Configura umbrales y puntos de cada condición")

    with st.expander("⚙️ Ajustar scoring", expanded=False):
        c1s,c2s=st.columns(2)
        with c1s:
            st.session_state.sc_gap_thr=st.number_input(
                "Gap mín %",value=st.session_state.sc_gap_thr,step=5.0,min_value=0.0)
            st.session_state.sc_float_thr=st.number_input(
                "Float máx (M)",value=st.session_state.sc_float_thr,step=5.0,min_value=0.1)
            st.session_state.sc_rvol_thr=st.number_input(
                "RVOL mín",value=st.session_state.sc_rvol_thr,step=0.5,min_value=0.5)
        with c2s:
            st.session_state.sc_gap_pts=st.number_input(
                "Pts Gap",value=st.session_state.sc_gap_pts,step=5,min_value=0,max_value=40)
            st.session_state.sc_float_pts=st.number_input(
                "Pts Float",value=st.session_state.sc_float_pts,step=5,min_value=0,max_value=40)
            st.session_state.sc_rvol_pts=st.number_input(
                "Pts RVOL",value=st.session_state.sc_rvol_pts,step=5,min_value=0,max_value=40)
        st.session_state.sc_news_pts=st.slider(
            "Pts Noticias",0,40,st.session_state.sc_news_pts,5)
        st.session_state.sc_vwap_pts=st.slider(
            "Pts VWAP",0,40,st.session_state.sc_vwap_pts,5)
        total_max=(st.session_state.sc_gap_pts+st.session_state.sc_float_pts+
                   st.session_state.sc_rvol_pts+st.session_state.sc_news_pts+
                   st.session_state.sc_vwap_pts)
        st.caption(f"Máximo posible: **{total_max} pts** (se normaliza a 100)")

    # ── M5: UMBRAL DE ALERTAS ──────────────────────────────────────────
    st.divider()
    st.markdown("**🔔 Alertas Audibles**")
    st.session_state.sc_alert_thr=st.slider(
        "Umbral alerta (Score)",0,100,st.session_state.sc_alert_thr,5)
    st.caption(f"Alerta cuando Score ≥ **{st.session_state.sc_alert_thr}**")
    if st.button("🔕 Resetear alertas enviadas",use_container_width=True):
        st.session_state.alertas_enviadas=set()
        st.success("✅ Alertas reiniciadas")

    # ── M1: API KEY FINNHUB ────────────────────────────────────────────
    st.divider()
    st.markdown("**🔑 API Keys**")
    fh_input=st.text_input("Finnhub API Key",
                            value=st.session_state.fh_key,
                            type="password",
                            help="Gratis en finnhub.io — necesaria para Float y Noticias")
    if fh_input: st.session_state.fh_key=fh_input

    st.divider()
    auto_r  =st.toggle("🔄 Auto-refresh",value=False)
    auto_int=st.select_slider("Intervalo",options=[15,30,45,60],
                               format_func=lambda x:f"{x}s",value=30)

    if st.button("🔄 Reiniciar todo",use_container_width=True):
        st.session_state.gainers=[];  st.session_state.movers5=[]
        st.session_state.explosiones=[];st.session_state.manual={}
        st.session_state.top500=[];   st.session_state.ciclos=0
        st.session_state.status="🔄 Reiniciado."
        st.rerun()

# ════════════════════════════════════════════════════════════════════════
#  BOTONES DE ESCANEO
# ════════════════════════════════════════════════════════════════════════
st.markdown("### 🎛️ Controles de Escaneo")
b1,b2,b3,b4=st.columns(4)

with b1:
    btn_completo=st.button("🚀 ESCANEO COMPLETO\nGainers + Movers + Spikes",
                            use_container_width=True,key="btn_completo")
    st.caption("Yahoo + universo · ~3-5 min")
with b2:
    btn_top500=st.button("📊 TOP 500\nMejores por Score 100pts",
                          use_container_width=True,key="btn_top500")
    st.caption("Top 500 clasificados")
with b3:
    btn_momentum=st.button("⚡ MOMENTUM / SPIKES\nMovers últimos 5 min",
                            use_container_width=True,key="btn_momentum")
    st.caption("Detecta despegues ahora")
with b4:
    if st.session_state.sim:
        if st.button("🎲 SIMULAR DATOS\nModo práctica",
                     use_container_width=True,key="btn_sim4"):
            generar_simulacion(); st.rerun()
    else:
        btn_rescan=st.button("🔄 RE-ESCANEAR\nRepetir último",
                              use_container_width=True,key="btn_rescan")
        if btn_rescan: btn_completo=True

if (btn_completo or btn_top500 or btn_momentum) and not st.session_state.sim:
    modo=("momentum" if btn_momentum else "top500" if btn_top500 else "completo")
    nombres={"completo":"Escaneo Completo","top500":"Top 500","momentum":"Momentum"}
    st.info(f"⏳ **{nombres[modo]}** en ejecución... ~2-5 min. No cierres la página.")
    pb=st.progress(0); pt=st.empty()
    try:
        ejecutar_escaneo(pb,pt,modo)
        st.success("✅ Escaneo completado")
    except Exception as e:
        st.error(f"⚠️ Error: {e}")
    time.sleep(0.5); st.rerun()

st.divider()

# ════════════════════════════════════════════════════════════════════════
#  SCANNER MANUAL — BLOQUEANTE
# ════════════════════════════════════════════════════════════════════════
st.markdown("### 🔬 Scanner Manual — Análisis Completo")
st.caption("Hasta 20 tickers · Alpaca Data + yfinance fallback · Fundamentales + Noticias")

ci,cb,cc=st.columns([5,1.5,1])
with ci:
    manual_txt=st.text_input("Tickers",
        placeholder="BJDX, PMI, TGHL, NVDA, TSLA ...",
        label_visibility="collapsed",key="man_input")
with cb:
    run_man=st.button("🔬 ANALIZAR AHORA",type="primary",
                      use_container_width=True,key="btn_analizar")
with cc:
    if st.button("🗑️ Limpiar",use_container_width=True,key="btn_limpiar_man"):
        st.session_state.manual={}; st.rerun()

if run_man and manual_txt.strip():
    syms_m=list(dict.fromkeys(
        s.strip().upper() for s in manual_txt.replace(","," ").split()
        if s.strip() and 1<=len(s.strip())<=8
    ))[:20]
    if syms_m:
        vel=_cfg("vel"); interval=f"{vel}m" if vel>=2 else "1m"
        resultados={}
        with st.spinner(f"🔬 Analizando {len(syms_m)} ticker(s)..."):
            pb2=st.progress(0)
            for idx,sym in enumerate(syms_m):
                pb2.progress(int((idx+1)/len(syms_m)*100))
                resultados[sym]=analizar_ticker(sym,interval)
        st.session_state.manual=resultados
        # M5: alertas en resultados manuales
        for sym,ev in resultados.items():
            if not ev.get("error") and ev.get("score_100",0)>=_cfg("sc_alert_thr"):
                disparar_alerta(sym,ev["score_100"])
        st.rerun()

manual_res=st.session_state.get("manual",{})
if manual_res:
    for sym,ev in manual_res.items():
        if ev.get("error"):
            st.error(f"**{sym}**: {ev['error']}"); continue

        ta=ev["ta"]; tb=ev["tb"]; tv=ev.get("tv",5)
        te=ev.get("te",5); tc=ev.get("tc",5)
        score_100=ev.get("score_100",0)
        tend="ALCISTA" if ta>tb else ("BAJISTA" if tb>ta else "NEUTRAL")
        is_exp=ev.get("explosion",False)
        icon="⚡" if is_exp else ("🟢" if tc>=7 else "🟡" if tc>=5 else "🔴")

        with st.expander(
            f"{icon} **{sym}** | Score: **{score_100}/100** | {tend} | "
            f"TA:{ta} TB:{tb} TV:{tv} TE:{te} TC:{tc} | "
            f"${ev['precio']:.4f} | {ev['cambio_dia']:+.2f}%",
            expanded=(is_exp or len(manual_res)==1)
        ):
            # Score badge visual
            badge_cls=("score-high" if score_100>=80
                       else "score-mid" if score_100>=50 else "score-low")
            sc_color=("#059669" if score_100>=80
                      else "#D97706" if score_100>=50 else "#DC2626")
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">'
                f'<div style="background:{sc_color};color:#fff;padding:6px 18px;'
                f'border-radius:20px;font-weight:800;font-size:1.15em">'
                f'⭐ Score: {score_100}/100</div>'
                f'{"<div style=\"background:#1E40AF;color:#fff;padding:5px 14px;border-radius:20px;font-weight:700\">📰 NOTICIA ACTIVA</div>" if ev.get("tiene_noticia") else ""}'
                f'</div>',
                unsafe_allow_html=True)

            if ev.get("tiene_noticia") and ev.get("titular"):
                st.info(f"📰 **Último catalizador:** {ev['titular']}")

            # M2: fundamentales
            f_col1,f_col2,f_col3=st.columns(3)
            f_col1.metric("Float",_fmt_float(ev.get("float_m")))
            f_col2.metric("Shares Out.",_fmt_float(ev.get("shares_m")))
            f_col3.metric("Market Cap",f"${ev.get('mcap_m') or '—'}M")

            # Barras 5D
            bc1,bc2=st.columns(2)
            with bc1:
                st.markdown(
                    _barra("📈 Tendencia Alcista (TA)",ta)+
                    _barra("📉 Tendencia Bajista (TB)",tb,low_good=True)+
                    _barra("🔥 Volumen Relativo (TV)",tv),
                    unsafe_allow_html=True)
            with bc2:
                st.markdown(
                    _barra("⚡ Explosión / Spike (TE)",te)+
                    _barra("🎯 Compra Inmediata (TC)",tc),
                    unsafe_allow_html=True)

            rec=ev.get("recomendacion","—")
            rc=("#065F46" if "COMPRAR" in rec else "#991B1B" if "EVITAR" in rec else "#92400E")
            bg=("#D1FAE5" if "COMPRAR" in rec else "#FEE2E2" if "EVITAR" in rec else "#FEF3C7")
            st.markdown(
                f'<div style="background:{bg};border:1.5px solid {rc};'
                f'border-radius:8px;padding:10px 14px;margin:8px 0;'
                f'color:{rc};font-weight:700;font-size:1em">{rec}</div>',
                unsafe_allow_html=True)

            if is_exp:
                st.success("⚡ **EXPLOSIÓN** — ROC5>1.5% · RVOL≥2× · Vela alcista sólida")

            m1,m2,m3,m4,m5,m6=st.columns(6)
            m1.metric("💲 Precio",   f"${ev['precio']:.4f}")
            m2.metric("📊 RSI",      f"{ev['rsi']:.0f}")
            m3.metric("🔥 RVOL",     f"{ev['rvol']:.1f}×")
            m4.metric("⚡ ROC 1min", f"{ev['roc1']:+.2f}%")
            m5.metric("🚀 ROC 5min", f"{ev['roc5']:+.2f}%")
            m6.metric("📈 Cambio",   f"{ev['cambio_dia']:+.2f}%")

            m7,m8,m9,m10,m11,m12=st.columns(6)
            m7.metric("VWAP",        f"${ev['vwap']:.4f}")
            m8.metric("EMA-9",       f"${ev['ema9']:.4f}")
            m9.metric("EMA-20",      f"${ev['ema20']:.4f}")
            m10.metric("SuperTrend", "🟢↑" if ev["st_dir"]==1 else "🔴↓")
            m11.metric("Soporte",    f"${ev['sup']:.4f}")
            m12.metric("Resistencia",f"${ev['res']:.4f}")

            m13,m14,m15,m16=st.columns(4)
            m13.metric("ATR",        f"{ev['atr']:.6f}")
            m14.metric("Vol Última", f"{ev['vol_ult']/1_000_000:.2f}M")
            m15.metric("Liq (M$)",   f"${ev['liq_m']:.2f}M")
            m16.metric("Proyección", f"${ev['proy']:.4f}")

            mhc="#065F46" if ev["macd_h"]>0 else "#991B1B"
            st.markdown(
                f"**MACD Hist:** <span style='color:{mhc};font-weight:700'>{ev['macd_h']:+.6f}</span>"
                f" · **Cuerpo vela:** {ev.get('pct_c',0):.0f}%"
                f" · Actualizado: **{ev['ts']}**",
                unsafe_allow_html=True)

            sl_p_v=st.session_state.sl_p; rr_v=st.session_state.rr
            tsl_v=st.session_state.trailing_pct; usd_v=st.session_state.usd
            sim_now=st.session_state.sim; pr_m=ev["precio"]
            sl_m=round(pr_m*(1-sl_p_v/100),6)
            sl_ema=round(ev.get("ema9",pr_m)*0.998,6) if ev.get("ema9",0)<pr_m else sl_m
            sl_f=round(max(sl_m,sl_ema,pr_m*0.005),6)
            rsk=max(pr_m-sl_f,1e-9); tp_f=round(pr_m+rsk*rr_v,6)
            tsl_f=ev.get("trailing_sl_pct",tsl_v)

            st.markdown(
                f'<div style="background:#EFF6FF;border:1.5px solid #BFDBFE;'
                f'border-radius:8px;padding:10px 14px;margin:6px 0;color:#1E3A5F">'
                f'📍 <b>SL fijo:</b> <code>${sl_f:.4f}</code> &nbsp;'
                f'🎯 <b>TP:</b> <code>${tp_f:.4f}</code> &nbsp;'
                f'🔄 <b>Trailing Stop:</b> <code>{tsl_f:.2f}%</code> &nbsp;'
                f'<b>R:R = 1:{rr_v:.1f}</b></div>',
                unsafe_allow_html=True)

            bc_col,_=st.columns([1,2])
            with bc_col:
                if st.button(f"🟢 COMPRAR {sym} ≈${usd_v:,.0f}",
                             key=f"mb_{sym}",type="primary"):
                    if not sim_now:
                        ok,msg=alpaca_comprar(sym,float(usd_v),sl_f,tp_f,tsl_f)
                        if ok: st.success(msg)
                        else:  st.error(msg)
                    else:
                        st.info(f"🟠 Sim: COMPRARÍA {sym} a ${pr_m:.4f}")

st.divider()

# ════════════════════════════════════════════════════════════════════════
#  PANEL 1 — TOP GAINERS
# ════════════════════════════════════════════════════════════════════════
gainers=st.session_state.gainers
st.markdown("### 📈 Panel 1 — Top Gainers del Día")
st.caption(f"Ordenado por Score 100pts · {ls_str} · {ses}")

if gainers:
    df_g=_mk_df(gainers)
    st.dataframe(_style_df(df_g),use_container_width=True,
                 hide_index=True,height=min(560,65+33*len(df_g)))
    # Expandir noticias si existe
    tickers_noticia=[e for e in gainers if e.get("📰","")!="—"]
    if tickers_noticia:
        with st.expander(f"📰 Noticias activas ({len(tickers_noticia)} tickers)",expanded=False):
            for e in tickers_noticia[:10]:
                if e.get("_titular"):
                    st.markdown(f"**{e['sym']}:** {e['_titular']}")
    _botones_compra_rapida(gainers,"g")
else:
    st.info(f"📡 **Sesión: {ses}** · Pulsa **🚀 ESCANEO COMPLETO** o activa **Simulación**.")

st.divider()

# ════════════════════════════════════════════════════════════════════════
#  PANEL 2 — TOP MOVERS 5 MIN
# ════════════════════════════════════════════════════════════════════════
movers5=st.session_state.movers5
st.markdown("### 🔥 Panel 2 — Top Movers Últimos 5 Minutos")
st.caption(f"Spikes · Score 100pts · {ls_str}")

if movers5:
    df_m5=_mk_df(movers5)
    st.dataframe(_style_df(df_m5),use_container_width=True,
                 hide_index=True,height=min(540,65+33*len(df_m5)))
    _botones_compra_rapida(movers5,"m")
else:
    st.info("Los movers aparecen aquí tras el escaneo.")

st.divider()

# ════════════════════════════════════════════════════════════════════════
#  PANEL 3 — EXPLOSIONES
# ════════════════════════════════════════════════════════════════════════
explosiones=st.session_state.explosiones
st.markdown("### ⚡ Panel 3 — Explosiones Detectadas (Spikes)")
st.caption("ROC >1.5% en 5min + RVOL ≥2.0 + Vela alcista sólida")

if explosiones:
    df_ex=_mk_df(explosiones)
    st.dataframe(_style_df(df_ex),use_container_width=True,
                 hide_index=True,height=min(480,65+33*len(df_ex)))
    _botones_compra_rapida(explosiones,"e")
    if st.button("🗑️ Limpiar explosiones",key="limpiar_exp"):
        st.session_state.explosiones=[]; st.rerun()
else:
    st.info("⚡ Explosiones: precio +1.5% en 5min · RVOL ≥2× · Vela alcista sólida")

st.divider()

# ════════════════════════════════════════════════════════════════════════
#  PANEL 4 — TOP 500 POR SCORE
# ════════════════════════════════════════════════════════════════════════
top500=st.session_state.top500
if top500:
    st.markdown(f"### 🏆 Panel 4 — Top {min(500,len(top500))} por Score 100pts")
    st.caption("Criterio principal: Score multidimensional (Gap+Float+RVOL+Noticias+VWAP)")
    df_t5=_mk_df(top500[:100])
    st.dataframe(_style_df(df_t5),use_container_width=True,hide_index=True,height=400)
    if len(top500)>100:
        with st.expander(f"📋 Ver todos ({len(top500)} tickers)"):
            df_all=_mk_df(top500)
            st.dataframe(_style_df(df_all),use_container_width=True,
                         hide_index=True,height=600)
    st.divider()

# ════════════════════════════════════════════════════════════════════════
#  PORTAFOLIO ALPACA PAPER
# ════════════════════════════════════════════════════════════════════════
st.markdown("### 💼 Portafolio Activo — Alpaca Paper")
posiciones=get_posiciones()
if posiciones:
    rows_p=[]; total_pnl=0.0
    for p in posiciones:
        pp=float(p.unrealized_plpc or 0)*100
        pu=float(p.unrealized_pl   or 0); total_pnl+=pu
        rows_p.append({
            "Ticker":p.symbol,"Qty":p.qty,
            "Entrada $":round(float(p.avg_entry_price or 0),4),
            "Actual $" :round(float(p.current_price   or 0),4),
            "P&L %"    :f"{'▲' if pp>=0 else '▼'} {pp:+.2f}%",
            "P&L $"    :f"${pu:+,.2f}",
        })
    pm1,pm2=st.columns(2)
    pm1.metric("Total P&L",f"${total_pnl:+,.2f}")
    pm2.metric("Posiciones",len(posiciones))
    st.dataframe(pd.DataFrame(rows_p),use_container_width=True,hide_index=True)
    pc1,pc2,pc3=st.columns([2,1,1])
    with pc1:
        tk_c=st.selectbox("Posición a cerrar",[r["Ticker"] for r in rows_p])
    with pc2:
        if st.button("🔴 Cerrar",key="cerrar_pos"):
            qty_p=abs(int(float([r["Qty"] for r in rows_p if r["Ticker"]==tk_c][0])))
            ok,msg=alpaca_vender(tk_c,qty_p)
            if ok: st.success(msg)
            else:  st.error(msg)
    with pc3:
        if st.button("🔴 CERRAR TODAS",key="cerrar_todas"):
            ok,msg=alpaca_exit_all()
            if ok: st.success(msg[:200])
            else:  st.error(msg[:200])
else:
    st.info("Sin posiciones abiertas en Alpaca Paper.")

st.divider()
st.markdown(
    '<div style="text-align:center;color:#4A6080;font-size:.68em;padding:6px 0">'
    '⚡ Thunder Radar V108 · Alpaca Data API + yfinance · Finnhub · Alpaca Paper Trading<br>'
    'NYSE · NASDAQ · Solo uso educativo — Los resultados pasados no garantizan rendimientos futuros'
    '</div>',unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
#  AUTO-REFRESH
# ════════════════════════════════════════════════════════════════════════
if auto_r:
    if "auto_ts" not in st.session_state:
        st.session_state.auto_ts=time.time()
    elapsed=time.time()-st.session_state.auto_ts
    restante=max(0,auto_int-elapsed)
    if restante>0:
        st.info(f"🔄 Auto-refresh en {int(restante)}s...")
        time.sleep(min(restante,5)); st.rerun()
    else:
        st.session_state.auto_ts=time.time()
        if st.session_state.sim: generar_simulacion()
        else:
            pb3=st.progress(0); pt3=st.empty()
            try: ejecutar_escaneo(pb3,pt3,"completo")
            except Exception as e:
                st.session_state.status=f"⚠️ Auto-refresh: {e}"
        st.rerun()
