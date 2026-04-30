"""
THUNDER RADAR V94 FINAL
========================
PROBLEMA RESUELTO: El pre-filtro con zonas horarias fallaba silenciosamente.
SOLUCIÓN: Cálculo de cambio% SIN manejo de fechas ni timezones.
  → cambio% = (último precio - precio de hace 30 velas) / precio_30_velas_antes
  → Funciona en CUALQUIER sesión: pre-market, regular, after-hours
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from datetime import datetime
import pytz
import time
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────
st.set_page_config(page_title="⚡ THUNDER RADAR V94", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');
html,body,[class*="css"]{background:#030810!important;color:#c9d1d9!important;
    font-family:'Share Tech Mono',monospace;}
h1,h2,h3{font-family:'Orbitron',sans-serif!important;}
.stButton>button{width:100%;border-radius:4px;font-weight:bold;
    font-family:'Orbitron',sans-serif;letter-spacing:1px;
    border:1px solid #30363d;transition:all .2s;}
.stButton>button:hover{transform:translateY(-1px);box-shadow:0 0 16px #00ff8866;}
div[data-testid="metric-container"]{background:linear-gradient(135deg,#0a0f1a,#141b27);
    border:1px solid #1e2739;border-radius:8px;padding:12px;}
.card-fire{background:linear-gradient(135deg,#061510,#0a0f1a);
    border:2px solid #00ff88;border-radius:10px;
    padding:14px 18px;margin:6px 0;box-shadow:0 0 22px #00ff8855;}
.card-hot{background:linear-gradient(135deg,#100a06,#0a0f1a);
    border:2px solid #ff8c00;border-radius:10px;
    padding:12px 16px;margin:4px 0;box-shadow:0 0 10px #ff8c0033;}
.card-watch{background:#090b0f;border:1px solid #ffc10733;
    border-radius:8px;padding:9px 13px;margin:3px 0;}
.s10{color:#00ff88;font-size:1.9em;font-weight:900;font-family:'Orbitron',sans-serif;}
.s8{color:#39ff14;font-size:1.5em;font-weight:800;}
.s6{color:#ffc107;font-size:1.3em;font-weight:700;}
.tkr{font-family:'Orbitron',sans-serif;font-size:1.3em;font-weight:900;color:#fff;}
.lbl{color:#8b949e;font-size:.74em;}
.hdr{text-align:center;font-family:'Orbitron',sans-serif;font-size:2.2em;font-weight:900;
    background:linear-gradient(90deg,#00ff88,#00d4ff,#ff4500);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:3px;}
.sub{text-align:center;color:#8b949e;font-size:.78em;letter-spacing:3px;}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.74em;font-weight:bold;}
.b-reg{background:#15803d;color:#fff;}.b-pre{background:#7c3aed;color:#fff;}
.b-aft{background:#0369a1;color:#fff;}.b-cls{background:#374151;color:#fff;}
.dot{display:inline-block;width:9px;height:9px;background:#00ff88;border-radius:50%;
    margin-right:5px;animation:blink 1s infinite;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.1}}
hr.n{border:none;border-top:1px solid #00ff8822;margin:12px 0;}
.ibox{background:#0a0f1a;border:1px solid #00ff8833;border-radius:8px;
    padding:10px 14px;margin:6px 0;font-size:.79em;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────
# ALPACA
# ─────────────────────────────────────────────────────
ALPACA_KEY    = "PKOKUMRZBCA2YJKVZIATSPGV5J"
ALPACA_SECRET = "2UBriZpW7NooR1EvtowC63GcarFt7rEQFD9ofti9Ah6N"

@st.cache_resource
def get_alpaca():
    return TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)
alpaca = get_alpaca()

# ─────────────────────────────────────────────────────
# SESIÓN
# ─────────────────────────────────────────────────────
def get_session():
    tz = pytz.timezone("US/Eastern")
    now = datetime.now(tz)
    h = now.hour + now.minute / 60.0
    if   4.0  <= h < 9.5:  return "PRE-MARKET"
    elif 9.5  <= h < 16.0: return "REGULAR"
    elif 16.0 <= h < 20.0: return "AFTER-HOURS"
    else:                   return "CERRADO"

SESSION = get_session()

# ─────────────────────────────────────────────────────
# UNIVERSO BASE (stocks conocidos por alta volatilidad)
# + Twelve Data para expandir
# ─────────────────────────────────────────────────────
BASE_VOLATILES = list(dict.fromkeys([
    # Top Gainers frecuentes en Webull (los que realmente se mueven)
    "BIYA","NEXR","ATER","BBBY","SBLX","SNBR","YJ","ILLR","SCAG",
    "BLIV","ABTS","DLHC","WSHP","MYSE","ONFO","CTNT","RAIN","CPHI",
    "NCRA","LVLU","HNST","RCAT","CRKN","BSLK","GPUS","GFAI","SGBX",
    "INPX","RSSS","ISPC","UCAR","ABLV","YXT","ZBAI","MTEX","MGRT",
    "BRIA","EDTK","TGHL","ZSPC","PBM","APCX","NXTP","INEO","LCFY",
    "BUDA","MNTS","ASTR","SPIR","PAVS","TCRT","VRPX","ILUS","VISL",
    # Meme/momentum clásicos
    "GME","AMC","KOSS","BB","NOK","BBIG","SPCE","MULN","IDEX","CENN",
    "MVIS","PROG","NAKD","EXPR","KPLT","CELH","SKIN","NKLA","WKHS",
    # Biotech volátil (mucho movimiento pre-market)
    "OCGN","CLOV","SNDL","TLRY","AGEN","ADXS","MNMD","ATAI","BPMC",
    "PRAX","ARVN","LGVN","VVOS","SYRA","QNRX","CRTX","IINN","BFRI",
    "NVAX","MRNA","BNTX","SRPT","ACAD","HIMS","FATE","CRSP","EDIT",
    "ACMR","PCVX","REPL","SAGE","ATNF","PRST","ASLN","ASRT","ATIF",
    # Cripto-proxy
    "COIN","HOOD","MSTR","RIOT","MARA","HUT","CIFR","BTBT","CLSK",
    "WULF","IREN","BITF","BTCS","CORZ","ARBK","SATO","MIGI",
    # EV
    "RIVN","LCID","CHPT","BLNK","PLUG","FCEL","GOEV","FSR","NIO",
    "XPEV","LI","SOLO","HYLN","AYRO",
    # China ADR
    "BABA","JD","PDD","TCOM","TIGR","FUTU","BILI","IQ","DOYU","HUYA",
    "GOTU","TUYA","TAL","DIDI","YMM","LAIX",
    # Space/Quantum/Drones
    "ASTS","LUNR","RKLB","ACHR","JOBY","IONQ","RGTI","QUBT",
    # Fintech small
    "SOFI","UPST","AFRM","ROOT","OPFI","DAVE","GHLD","CURO",
    # Large cap tech
    "AAPL","MSFT","NVDA","TSLA","AMD","META","AMZN","GOOGL","NFLX",
    "INTC","AVGO","QCOM","MU","SMCI","PLTR","CRM","NOW","SNOW","DDOG",
    "CRWD","OKTA","NET","HUBS","BILL","ZS",
    # Retail/Consumer especulativos
    "PTON","DOCU","ZM","TDOC","LYFT","UBER","DASH","ABNB","DKNG",
    "RBLX","U","SNAP","PINS","PARA","WBD","ROKU","FUBO","SIRI",
    # Más micro/small caps volátiles
    "MRIN","AULT","ATIF","ATOM","ATOS","AUPH","AUVI","AVXL","AXSM",
    "ADXS","ALVR","AMPIO","APDN","ARQQ","ARVL","AVAH","AVCO","AVDL",
    "AVEO","AVIR","AVPT","AVRO","AVTE","BCTX","AGRX","AKBA","ALLT",
]))

@st.cache_data(ttl=3600)
def cargar_twelve() -> list:
    """Carga TODOS los stocks de NYSE+NASDAQ+AMEX via Twelve Data (gratis)."""
    tickers = []
    for exc in ["NYSE", "NASDAQ", "AMEX"]:
        try:
            r = requests.get(
                "https://api.twelvedata.com/stocks",
                params={"exchange": exc, "type": "Common Stock", "format": "JSON"},
                timeout=12
            )
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    s = item.get("symbol", "").strip().upper()
                    if s and s.isalpha() and 2 <= len(s) <= 5:
                        tickers.append(s)
        except Exception:
            pass
    result = list(dict.fromkeys(tickers))
    return result if len(result) > 500 else BASE_VOLATILES

# ─────────────────────────────────────────────────────
# EXTRACTOR SEGURO DE DATAFRAME
# ─────────────────────────────────────────────────────
def xdf(raw, t, n):
    try:
        if n == 1:
            df = raw.copy()
        elif isinstance(raw.columns, pd.MultiIndex) and t in raw.columns.get_level_values(0):
            df = raw[t].copy()
        else:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        for c in ["Close", "High", "Low", "Open", "Volume"]:
            if c not in df.columns:
                return None
        df = df.dropna(subset=["Close", "Volume"])
        return df if len(df) >= 3 else None
    except Exception:
        return None

# ─────────────────────────────────────────────────────
# PASO 1: RANKING RÁPIDO
# ─────────────────────────────────────────────────────
# CLAVE: calcula cambio% usando las últimas N velas
# SIN manejo de fechas ni timezones → no falla nunca.
# N velas atrás = ~2.5 horas de datos de 5min
# ─────────────────────────────────────────────────────
def ranking_rapido(universo: list, precio_min: float, precio_max: float,
                   top_n: int = 200) -> pd.DataFrame:
    activos = []
    total = len(universo)
    lote  = 100
    pb    = st.progress(0.0, text="📡 Ranking: descargando datos 5min...")

    for i in range(0, total, lote):
        chunk = universo[i:i+lote]
        pb.progress(min((i+lote)/total, 1.0),
                    text=f"📡 Ranking {min(i+lote,total)}/{total}...")
        try:
            raw = yf.download(
                chunk, period="1d", interval="5m",
                group_by="ticker", prepost=True,
                progress=False, auto_adjust=True, threads=True, timeout=20
            )
            for t in chunk:
                try:
                    df = xdf(raw, t, len(chunk))
                    if df is None or len(df) < 4:
                        continue

                    precio = float(df["Close"].iloc[-1])
                    if not (precio_min <= precio <= precio_max):
                        continue

                    # Cambio % SIN timezones:
                    # Usamos las últimas 30 velas (= ~2.5 horas de 5min)
                    # Si hay menos, usamos las que haya
                    lookback = min(30, len(df) - 1)
                    precio_base = float(df["Close"].iloc[-(lookback+1)])
                    cambio_pct  = (precio - precio_base) / max(precio_base, 1e-9) * 100

                    # RVOL: vol última vela vs promedio del día
                    vol_ult  = float(df["Volume"].iloc[-1])
                    vol_prom = float(df["Volume"].mean())
                    rvol     = vol_ult / max(vol_prom, 1)

                    # Velocidad: % cambio en última vela de 5min
                    vel_5m = (float(df["Close"].iloc[-1]) - float(df["Close"].iloc[-2])) \
                             / max(float(df["Close"].iloc[-2]), 1e-9) * 100

                    # Score de ranking simple
                    score = abs(cambio_pct) * 0.5 + rvol * 0.3 + abs(vel_5m) * 0.2

                    activos.append({
                        "Ticker"    : t,
                        "Precio $"  : round(precio, 4),
                        "Δ %"       : round(cambio_pct, 2),
                        "Vel 5m %"  : round(vel_5m, 2),
                        "RVOL"      : round(rvol, 1),
                        "Vol"       : int(float(df["Volume"].sum())),
                        "_score"    : score,
                    })
                except Exception:
                    continue
        except Exception:
            continue

    pb.empty()

    if not activos:
        return pd.DataFrame()

    df_r = pd.DataFrame(activos).sort_values("_score", ascending=False).reset_index(drop=True)
    return df_r.head(top_n)

# ─────────────────────────────────────────────────────
# SUPERTREND
# ─────────────────────────────────────────────────────
def calc_supertrend(df, periodo=10, mult=3.0):
    try:
        h = df["H"]; l = df["L"]; c = df["C"]
        n = len(df)
        if n < periodo + 2:
            df["st_dir"] = 1; df["st_val"] = c * 0.98; df["st_cross"] = 0
            return df

        hl = h - l
        hc = (h - c.shift(1)).abs()
        lc = (l - c.shift(1)).abs()
        atr = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(periodo).mean()

        mid  = (h + l) / 2
        ub_r = mid + mult * atr
        lb_r = mid - mult * atr
        ub = ub_r.copy(); lb = lb_r.copy()

        for i in range(1, n):
            ub.iloc[i] = min(ub_r.iloc[i], ub.iloc[i-1]) \
                if c.iloc[i-1] <= ub.iloc[i-1] else ub_r.iloc[i]
            lb.iloc[i] = max(lb_r.iloc[i], lb.iloc[i-1]) \
                if c.iloc[i-1] >= lb.iloc[i-1] else lb_r.iloc[i]

        d = pd.Series(1.0, index=df.index)
        for i in range(1, n):
            if d.iloc[i-1] == 1:
                d.iloc[i] = 1 if c.iloc[i] >= lb.iloc[i] else -1
            else:
                d.iloc[i] = -1 if c.iloc[i] <= ub.iloc[i] else 1

        df["st_dir"]   = d.values
        df["st_val"]   = np.where(d == 1, lb.values, ub.values)
        df["st_cross"] = (d != d.shift(1)).fillna(False).astype(int).values
        return df
    except Exception:
        df["st_dir"] = 1; df["st_val"] = df.get("C", df["Close"]) * 0.98
        df["st_cross"] = 0
        return df

# ─────────────────────────────────────────────────────
# INDICADORES TÉCNICOS 1min
# ─────────────────────────────────────────────────────
def indicadores(df_raw: pd.DataFrame, st_per: int, st_mult: float):
    try:
        df = df_raw.copy()

        def s(col):
            x = pd.to_numeric(df[col], errors="coerce").squeeze()
            return x.iloc[:, 0] if isinstance(x, pd.DataFrame) else x

        C, H, L, O, V = s("Close"), s("High"), s("Low"), s("Open"), s("Volume").fillna(0)
        df["C"] = C.values; df["H"] = H.values
        df["L"] = L.values; df["O"] = O.values; df["V"] = V.values
        n = len(df)
        if n < 3: return None

        # EMAs
        df["e9"]  = df["C"].ewm(span=min(9,  n), adjust=False).mean()
        df["e20"] = df["C"].ewm(span=min(20, n), adjust=False).mean()

        # VWAP
        tp = (df["H"] + df["L"] + df["C"]) / 3
        cv = df["V"].cumsum()
        df["vwap"] = np.where(cv > 0, (tp * df["V"]).cumsum() / cv, df["C"])

        # RSI
        d  = df["C"].diff()
        g  = d.where(d > 0, 0.0).rolling(min(14, n)).mean()
        ls = (-d.where(d < 0, 0.0)).rolling(min(14, n)).mean()
        df["rsi"] = (100 - 100 / (1 + g / ls.replace(0, np.nan))).fillna(50)

        # MACD
        df["macd"]   = (df["C"].ewm(span=min(12, n), adjust=False).mean()
                       - df["C"].ewm(span=min(26, n), adjust=False).mean())
        df["macd_s"] = df["macd"].ewm(span=min(9, n), adjust=False).mean()
        df["macd_h"] = df["macd"] - df["macd_s"]

        # ATR
        hl = df["H"] - df["L"]
        hc = (df["H"] - df["C"].shift(1)).abs()
        lc = (df["L"] - df["C"].shift(1)).abs()
        df["atr"] = pd.concat([hl, hc, lc], axis=1).max(axis=1)\
                       .rolling(min(14, n)).mean().fillna(df["C"] * 0.01)

        # Soporte / Resistencia dinámicos
        w = min(20, n)
        df["sup"] = df["L"].rolling(w).min().fillna(df["C"] * 0.97)
        df["res"] = df["H"].rolling(w).max().fillna(df["C"] * 1.03)

        # RVOL — últimas 10 velas
        wv = min(10, n - 1)
        df["vavg"] = df["V"].rolling(wv).mean().fillna(df["V"].mean())
        df["rvol"] = (df["V"] / df["vavg"].replace(0, 1)).fillna(1)

        # Velocidad 1min, 2min, 3min y aceleración
        df["v1"] = df["C"].pct_change(1) * 100
        df["v2"] = df["C"].pct_change(2) * 100
        df["v3"] = df["C"].pct_change(3) * 100
        df["ac"] = df["v1"] - df["v1"].shift(1)

        # Supertrend
        df = calc_supertrend(df, st_per, st_mult)

        return df
    except Exception:
        return None

# ─────────────────────────────────────────────────────
# MOTOR DE SEÑAL
# ─────────────────────────────────────────────────────
def gv(row, col, default=0.0):
    try:
        v = float(row[col])
        return default if (np.isnan(v) or np.isinf(v)) else v
    except Exception:
        return default

def motor_senal(df, session: str, cambio_rank: float):
    if df is None or len(df) < 3:
        return 1, 1, "⚪ NEUTRO", {}, 0.0, 0.0, 1

    a = df.iloc[-1]
    p = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
    b = df.iloc[-3] if len(df) > 2 else p

    precio = gv(a, "C")
    if precio <= 0:
        return 1, 1, "⚪ NEUTRO", {}, 0.0, 0.0, 1

    up = dn = 0.0
    det = {}

    # 1. RVOL (peso 25%)
    rv = gv(a, "rvol", 1)
    if rv >= 10:
        up += 2.5; det["RVOL"] = f"🔥🔥🔥 {rv:.1f}x EXPLOSIVO"
    elif rv >= 5:
        up += 2.0; det["RVOL"] = f"🔥🔥 {rv:.1f}x Muy alto"
    elif rv >= 2.5:
        up += 1.4; det["RVOL"] = f"🔥 {rv:.1f}x Elevado"
    elif rv >= 1.3:
        up += 0.7; det["RVOL"] = f"▲ {rv:.1f}x Sobre promedio"
    else:
        det["RVOL"] = f"→ {rv:.1f}x Normal"

    # 2. VELOCIDAD última vela 1min (peso 25%)
    v1 = gv(a, "v1")
    if v1 >= 3:
        up += 2.5; det["VEL"] = f"🚀🚀 {v1:+.2f}%/min COHETE"
    elif v1 >= 1:
        up += 1.8; det["VEL"] = f"🚀 {v1:+.2f}%/min Fuerte"
    elif v1 >= 0.2:
        up += 1.0; det["VEL"] = f"▲ {v1:+.2f}%/min Positivo"
    elif v1 >= 0.03:
        up += 0.4; det["VEL"] = f"▲ {v1:+.2f}%/min Leve"
    elif v1 <= -3:
        dn += 2.5; det["VEL"] = f"💥 {v1:+.2f}%/min CAÍDA"
    elif v1 <= -1:
        dn += 1.8; det["VEL"] = f"▼▼ {v1:+.2f}%/min Bajando"
    elif v1 <= -0.03:
        dn += 0.6; det["VEL"] = f"▼ {v1:+.2f}%/min Leve baja"
    else:
        det["VEL"] = f"→ {v1:+.2f}%/min Plano"

    # 3. ACELERACIÓN (peso 20%)
    va, vb = gv(a, "v1"), gv(p, "v1")
    if va > 0 and vb >= 0 and va > vb:
        up += 2.0; det["ACEL"] = f"⚡ Acelerando {vb:+.2f}%→{va:+.2f}%"
    elif va > 0 and va > vb:
        up += 1.0; det["ACEL"] = f"▲ Vel subiendo {vb:+.2f}%→{va:+.2f}%"
    elif va < 0 and vb <= 0 and va < vb:
        dn += 2.0; det["ACEL"] = f"⚡ Cayendo {vb:+.2f}%→{va:+.2f}%"
    elif va < 0 and va < vb:
        dn += 1.0; det["ACEL"] = f"▼ Caída {vb:+.2f}%→{va:+.2f}%"
    else:
        det["ACEL"] = "→ Sin aceleración"

    # 4. SUPERTREND (peso 20%)
    st_dir  = gv(a, "st_dir", 1)
    st_val  = gv(a, "st_val", precio)
    st_crux = int(gv(a, "st_cross", 0))
    dist    = abs(precio - st_val) / max(precio, 1e-9) * 100

    if st_dir == 1:
        up += 2.0
        det["SUPERT"] = f"✅ ALCISTA — soporte ${st_val:.4f} ({dist:.1f}%↓)"
        if st_crux:
            up += 1.5; det["SUPERT"] += " 🔔 CRUCE ALCISTA"
    else:
        dn += 2.0
        det["SUPERT"] = f"❌ BAJISTA — resist ${st_val:.4f} ({dist:.1f}%↑)"
        if st_crux:
            dn += 1.5; det["SUPERT"] += " 🔔 CRUCE BAJISTA"

    # 5. TÉCNICO: VWAP + EMA + MACD + RSI (peso 10%)
    vwap = gv(a, "vwap", precio)
    e9   = gv(a, "e9", precio)
    e20  = gv(a, "e20", precio)
    rsi  = gv(a, "rsi", 50)
    mh   = gv(a, "macd_h", 0)
    mhp  = gv(p, "macd_h", 0)

    pts = ((0.3 if precio > vwap else 0) + (0.3 if e9 > e20 else 0) +
           (0.3 if mh > mhp and mh > 0 else 0) + (0.2 if 50 < rsi < 80 else 0) +
           (-0.3 if rsi >= 80 or rsi <= 20 else 0))
    if pts >= 0.7:
        up += 1.0; det["TEC"] = f"▲▲ Técnico alcista (RSI={rsi:.0f})"
    elif pts >= 0.3:
        up += 0.5; det["TEC"] = f"▲ Técnico parcial (RSI={rsi:.0f})"
    elif pts <= -0.2:
        dn += 0.5; det["TEC"] = f"▼ Técnico bajista (RSI={rsi:.0f})"
    else:
        det["TEC"] = f"→ Neutro (RSI={rsi:.0f})"

    # BONUS: Ranking 5min (ya viene del ranking)
    if cambio_rank >= 10:
        up += 1.5; det["RANK"] = f"🔥 Δ={cambio_rank:+.1f}% TOP GAINER"
    elif cambio_rank >= 5:
        up += 1.0; det["RANK"] = f"▲ Δ={cambio_rank:+.1f}%"
    elif cambio_rank >= 1:
        up += 0.4; det["RANK"] = f"▲ Δ={cambio_rank:+.1f}%"
    elif cambio_rank <= -5:
        dn += 1.0; det["RANK"] = f"▼ Δ={cambio_rank:+.1f}%"
    else:
        det["RANK"] = f"→ Δ={cambio_rank:+.1f}%"

    # Patrón de velas
    c1 = gv(df.iloc[-1], "C"); o1 = gv(df.iloc[-1], "O", c1)
    c2 = gv(df.iloc[-2], "C", c1) if len(df) > 1 else c1
    o2 = gv(df.iloc[-2], "O", c2) if len(df) > 1 else c2
    c3 = gv(df.iloc[-3], "C", c2) if len(df) > 2 else c2
    o3 = gv(df.iloc[-3], "O", c3) if len(df) > 2 else c3

    if (c1>o1) and (c2>o2) and (c3>o3) and (c1>c2>c3):
        up += 0.8; det["VELAS"] = "🟢🟢🟢 3 verdes"
    elif (c1>o1) and (c2>o2) and (c1>c2):
        up += 0.4; det["VELAS"] = "🟢🟢 2 verdes"
    elif (c1<o1) and (c2<o2) and (c3<o3) and (c1<c2<c3):
        dn += 0.8; det["VELAS"] = "🔴🔴🔴 3 rojas"
    elif (c1<o1) and (c2<o2):
        dn += 0.4; det["VELAS"] = "🔴🔴 2 rojas"
    else:
        det["VELAS"] = "→ Sin patrón"

    # Normalizar 1-10
    mx = 2.5 + 2.5 + 2.0 + 3.5 + 1.0 + 1.5 + 0.8
    su = max(1, min(10, round(max(up, 0) / mx * 10)))
    sd = max(1, min(10, round(max(dn, 0) / mx * 10)))

    if   su >= 9: senal = "🚀 DESPEGUE — COMPRA AHORA"
    elif su >= 7: senal = "⚡ EXPLOSIÓN ALCISTA"
    elif su >= 5: senal = "📈 IMPULSO ALCISTA"
    elif sd >= 9: senal = "💥 CAÍDA FUERTE"
    elif sd >= 7: senal = "📉 SEÑAL BAJISTA"
    elif sd >= 5: senal = "▼ BAJISTA"
    else:         senal = "⚪ NEUTRO"

    return su, sd, senal, det, rv, v1, int(st_dir)

# ─────────────────────────────────────────────────────
# SL / TP DINÁMICO
# ─────────────────────────────────────────────────────
def calc_sltp(df, precio, senal, msl, mtp):
    try:
        a   = df.iloc[-1]
        atr = gv(a, "atr", precio * 0.015)
        sup = gv(a, "sup", precio * 0.97)
        res = gv(a, "res", precio * 1.03)
        stv = gv(a, "st_val", 0)
        if sup <= 0 or sup >= precio: sup = precio * 0.97
        if res <= 0 or res <= precio: res = precio * 1.03
        alcista = any(x in senal for x in
                      ["DESPEGUE","COMPRA","ALCISTA","IMPULSO","EXPLOS"])
        if alcista:
            sl_base = max(precio - atr * msl, sup * 0.998)
            if 0 < stv < precio:
                sl_base = max(sl_base, stv * 0.997)
            sl = round(sl_base, 4)
            tp = round(min(precio + atr * mtp, res * 0.999), 4)
        else:
            sl = round(min(precio + atr * msl, res * 1.002), 4)
            tp = round(max(precio - atr * mtp, sup * 1.001), 4)
        if sl <= 0: sl = round(precio * 0.97, 4)
        if tp <= 0: tp = round(precio * 1.06, 4)
        rr = round(abs(tp - precio) / max(abs(precio - sl), 1e-9), 2)
        return sl, tp, rr
    except Exception:
        return round(precio * 0.97, 4), round(precio * 1.06, 4), 2.0

# ─────────────────────────────────────────────────────
# ESCANEO 1MIN — Motor de señal completo
# ─────────────────────────────────────────────────────
def escanear_1min(ranking_df: pd.DataFrame,
                  precio_min: float, precio_max: float,
                  rvol_min: float, vel_min: float,
                  msl: float, mtp: float,
                  session: str, st_per: int, st_mult: float,
                  top_n: int) -> pd.DataFrame:

    if ranking_df.empty:
        return pd.DataFrame()

    tickers    = ranking_df["Ticker"].tolist()
    cambio_map = dict(zip(ranking_df["Ticker"], ranking_df["Δ %"]))

    resultados = []
    total = len(tickers)
    lote  = 50
    dfs   = {}
    pb    = st.progress(0.0, text="⚡ Descargando datos 1min...")

    # Descarga 1min
    for i in range(0, total, lote):
        chunk = tickers[i:i+lote]
        pb.progress(min((i+lote)/total*0.45, 0.45),
                    text=f"📡 1min {min(i+lote,total)}/{total}...")
        try:
            raw = yf.download(
                chunk, period="1d", interval="1m",
                group_by="ticker", prepost=True,
                progress=False, auto_adjust=True, threads=True, timeout=25
            )
            for t in chunk:
                dfs[t] = xdf(raw, t, len(chunk))
        except Exception:
            for t in chunk:
                try:
                    s = yf.download(t, period="1d", interval="1m",
                                    prepost=True, progress=False,
                                    auto_adjust=True, threads=False, timeout=12)
                    dfs[t] = xdf(s, t, 1)
                except Exception:
                    dfs[t] = None

    # Análisis
    for idx, t in enumerate(tickers):
        pb.progress(0.45 + (idx+1)/total*0.55,
                    text=f"🔬 {t} ({idx+1}/{total})...")
        try:
            raw_df = dfs.get(t)
            if raw_df is None or len(raw_df) < 5:
                continue

            df = indicadores(raw_df, st_per, st_mult)
            if df is None:
                continue

            precio = float(df["C"].iloc[-1])
            if not (precio_min <= precio <= precio_max):
                continue

            rv   = float(df["rvol"].iloc[-1]) if not np.isnan(df["rvol"].iloc[-1]) else 0
            vel1 = float(df["v1"].iloc[-1])   if not np.isnan(df["v1"].iloc[-1])   else 0
            cambio_ses = cambio_map.get(t, 0.0)

            # ── FILTROS ADAPTATIVOS ──
            # En pre/after: muy permisivos (volumen bajo)
            # En regular: más exigentes
            if session == "REGULAR":
                pasa = (rv >= rvol_min) and (abs(vel1) >= vel_min)
            else:
                # Pre/after: basta con UNO de los dos criterios
                pasa = (rv >= max(1.1, rvol_min * 0.35)) \
                    or (abs(vel1) >= max(0.02, vel_min * 0.25)) \
                    or (abs(cambio_ses) >= 1.0)  # o si el ranking ya muestra movimiento
            if not pasa:
                continue

            su, sd, senal, det, rv, vel1, st_dir = motor_senal(df, session, cambio_ses)

            if session == "REGULAR" and su < 3 and sd < 3:
                continue

            _sl, _tp, rr = calc_sltp(df, precio, senal, msl, mtp)

            open_d   = float(df["O"].iloc[0]) if float(df["O"].iloc[0]) > 0 else precio
            cambio_d = (precio - open_d) / max(open_d, 1e-9) * 100
            rsi   = float(df["rsi"].iloc[-1])
            sup   = float(df["sup"].iloc[-1])
            res   = float(df["res"].iloc[-1])
            vel2  = float(df["v2"].iloc[-1])  if not np.isnan(df["v2"].iloc[-1]) else 0
            ac    = float(df["ac"].iloc[-1])  if not np.isnan(df["ac"].iloc[-1])   else 0
            stv   = float(df["st_val"].iloc[-1]) if "st_val" in df.columns else 0
            st_tx = "🟢 ALCISTA" if st_dir == 1 else "🔴 BAJISTA"

            resultados.append({
                "Ticker"   : t,
                "Precio $" : round(precio, 4),
                "RVOL"     : round(rv, 1),
                "Vel 1m %" : round(vel1, 2),
                "Vel 2m %" : round(vel2, 2),
                "Acel"     : round(ac, 3),
                "Supertrend": st_tx,
                "ST $"     : round(stv, 4),
                "Δ Rank %" : round(cambio_ses, 2),
                "Δ Día %"  : round(cambio_d, 2),
                "Score 🐂" : su,
                "Score 🐻" : sd,
                "Señal"    : senal,
                "RSI"      : round(rsi, 1),
                "Soporte $": round(sup, 4),
                "Resist $" : round(res, 4),
                "SL $"     : _sl,
                "TP $"     : _tp,
                "R:R"      : rr,
                "_det"     : det,
                "_df"      : df,
            })
        except Exception:
            continue

    pb.empty()
    if not resultados:
        return pd.DataFrame()

    df_res = pd.DataFrame(resultados)
    df_res = df_res.sort_values(
        ["Score 🐂", "RVOL", "Vel 1m %"],
        ascending=[False, False, False]
    ).reset_index(drop=True)
    return df_res.head(top_n)

# ─────────────────────────────────────────────────────
# ALPACA HELPERS
# ─────────────────────────────────────────────────────
def get_cuenta():
    try:    return alpaca.get_account()
    except: return None

def get_pos():
    try:    return alpaca.get_all_positions()
    except: return []

def cerrar(sym):
    try:    alpaca.close_position(sym); return True, f"✅ Cerrada {sym}"
    except Exception as e: return False, str(e)

def buy(sym, qty, sl, tp):
    try:
        alpaca.submit_order(MarketOrderRequest(
            symbol=sym, qty=qty, side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC,
            take_profit=TakeProfitRequest(limit_price=round(float(tp), 2)),
            stop_loss=StopLossRequest(stop_price=round(float(sl), 2))
        ))
        return True, f"✅ BUY {qty}x {sym} | SL=${sl} TP=${tp}"
    except Exception as e: return False, f"❌ {e}"

def sell(sym, qty):
    try:
        alpaca.submit_order(MarketOrderRequest(
            symbol=sym, qty=qty, side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC
        ))
        return True, f"✅ SELL {qty}x {sym}"
    except Exception as e: return False, f"❌ {e}"

# ═════════════════════════════════════════════════════
#  INTERFAZ PRINCIPAL
# ═════════════════════════════════════════════════════
st.markdown('<h1 class="hdr">⚡ THUNDER RADAR V94</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub">RANKING REAL · SUPERTREND · RVOL · SL/TP DINÁMICO · ALPACA PAPER</p>',
    unsafe_allow_html=True)

badge_map = {"REGULAR":"b-reg","PRE-MARKET":"b-pre",
             "AFTER-HOURS":"b-aft","CERRADO":"b-cls"}
tz_et   = pytz.timezone("US/Eastern")
hora_et = datetime.now(tz_et).strftime("%H:%M:%S ET")
cuenta  = get_cuenta()

hc1, hc2, hc3 = st.columns(3)
with hc1:
    st.markdown(
        f'<span class="badge {badge_map.get(SESSION,"b-cls")}">● {SESSION}</span>'
        f' &nbsp;<span class="dot"></span>'
        f'<span style="color:#8b949e;font-size:.74em">EN VIVO</span>',
        unsafe_allow_html=True)
with hc2:
    st.markdown(f'<span style="color:#8b949e">🕐 {hora_et}</span>',
                unsafe_allow_html=True)
with hc3:
    if cuenta:
        eq  = float(cuenta.equity)
        pnl = eq - float(cuenta.last_equity)
        col = "#00ff88" if pnl >= 0 else "#ff4444"
        st.markdown(
            f'<span style="color:{col}">💰 ${eq:,.2f} | P&L {pnl:+,.2f}</span>',
            unsafe_allow_html=True)

# Info sesión
sesion_info = {
    "PRE-MARKET":  ("🌅 PRE-MARKET (04:00-09:29 ET) — Detecta gaps de apertura. "
                    "Stocks como BIYA +125% aparecen aquí. Filtros ultra-sensibles.", "#7c3aed"),
    "REGULAR":     ("📈 MERCADO REGULAR (09:30-15:59 ET) — "
                    "Máxima volatilidad. Motor a plena potencia.", "#15803d"),
    "AFTER-HOURS": ("🌆 AFTER-HOURS (16:00-19:59 ET) — "
                    "Reacciones a earnings y noticias. Filtros sensibles.", "#0369a1"),
    "CERRADO":     ("🌙 MERCADO CERRADO — Pre-market abre 4:00 AM ET. "
                    "Puedes hacer el ranking ahora.", "#374151"),
}
msg_s, col_s = sesion_info.get(SESSION, ("", "#374151"))
st.markdown(f'<div class="ibox"><b style="color:{col_s}">{msg_s}</b></div>',
            unsafe_allow_html=True)
st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────
# BARRA LATERAL
# ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ CONFIGURACIÓN")

    modo = st.selectbox("Modo", [
        "🔥 Todo el mercado",
        "💎 Penny + Small ($0.05-$10)",
        "📈 Large Cap ($10+)",
        "🎯 Mis Tickers",
    ])

    st.markdown("---")
    precio_min_f = st.number_input("Precio Mín $", value=0.05,  step=0.05, min_value=0.01)
    precio_max_f = st.number_input("Precio Máx $", value=500.0, step=10.0)

    st.markdown("**⚡ Motor de Aceleración**")
    dflt_rv = 1.2 if SESSION in ("PRE-MARKET","AFTER-HOURS","CERRADO") else 2.0
    dflt_vl = 0.05 if SESSION in ("PRE-MARKET","AFTER-HOURS","CERRADO") else 0.10

    rvol_min = st.slider("RVOL mínimo", 1.0, 15.0, dflt_rv, 0.1,
                         help="1.2 para pre/after-hours. 2.0 para mercado regular.")
    vel_min  = st.slider("Velocidad mín %/vela", 0.0, 3.0, dflt_vl, 0.01,
                         help="0.05% es suficiente en pre-market.")

    st.markdown("**📊 Supertrend**")
    st_per  = st.slider("Período", 5, 20, 10, 1)
    st_mult = st.slider("Multiplicador ATR", 1.0, 5.0, 3.0, 0.5)

    st.markdown("**📋 Tamaño del ranking**")
    n_rank  = st.slider("Top del ranking (Paso 1)", 50, 400, 150, 25,
                        help="Los N stocks más activos pasan al escaneo 1min")
    top_n_f = st.slider("Resultados finales", 10, 80, 40, 5)

    st.markdown("**🔒 SL / TP**")
    atr_sl = st.slider("ATR × Stop Loss",   0.5, 5.0, 2.0, 0.5)
    atr_tp = st.slider("ATR × Take Profit", 1.0, 8.0, 4.0, 0.5)

    if modo == "🎯 Mis Tickers":
        txt = st.text_area("Tickers",
                           "BIYA,NEXR,ATER,BBBY,SBLX,YJ,BRIA,GME,AMC,COIN,MARA",
                           height=70)
        manual = [x.strip().upper() for x in txt.split(",") if x.strip()]
    else:
        manual = []

    st.markdown("---")
    modo_auto = st.toggle("🤖 Auto-Trade", value=False)
    if modo_auto:
        auto_score = st.slider("Score mín", 6, 10, 7)
        auto_qty   = st.number_input("Acciones/orden", value=1, min_value=1)
        max_pos    = st.number_input("Máx posiciones", value=3, min_value=1)
        st.warning("⚠️ Ejecuta órdenes en Paper.")

    auto_ref = st.toggle("🔁 Auto-escaneo", value=False)
    ref_seg  = 45 if SESSION == "REGULAR" else 60

# ─────────────────────────────────────────────────────
# ESTADO
# ─────────────────────────────────────────────────────
for k, v in [("universo", BASE_VOLATILES), ("ranking_df", pd.DataFrame()),
             ("df_scan", pd.DataFrame()), ("last_scan", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────
# SECCIÓN UNIVERSO
# ─────────────────────────────────────────────────────
st.subheader("📡 Paso 1 — Ranking de Stocks Activos AHORA")
st.markdown("""<div class="ibox">
<b style="color:#00ff88">¿Por qué el ranking es clave?</b>
El programa descarga datos de 5min para TODO el universo y calcula cuáles tienen
<b>mayor movimiento en las últimas 2.5 horas</b>.
Así encuentra stocks como <b>BIYA, NEXR, ATER</b> que despegan
<b>antes</b> de aparecer en Webull Top Gainers.
</div>""", unsafe_allow_html=True)

u1, u2, u3 = st.columns([2, 1, 1])
with u1:
    if st.button("🌐 Cargar universo NYSE+NASDAQ+AMEX (Twelve Data)",
                 use_container_width=True):
        with st.spinner("🌐 Descargando lista completa de stocks..."):
            u = cargar_twelve()
            st.session_state.universo = u
            st.session_state.ranking_df = pd.DataFrame()
        st.success(f"✅ {len(u):,} stocks cargados")
with u2:
    n_u = len(st.session_state.universo)
    col_u = "#00ff88" if n_u > 500 else "#ffc107"
    st.markdown(f'<span style="color:{col_u}">📊 {n_u:,} stocks</span>',
                unsafe_allow_html=True)
with u3:
    n_r = len(st.session_state.ranking_df)
    col_r = "#00ff88" if n_r > 0 else "#8b949e"
    st.markdown(f'<span style="color:{col_r}">🏆 {n_r} en ranking</span>',
                unsafe_allow_html=True)

# Universo según modo
if   modo == "🎯 Mis Tickers":             universo_base = manual
elif modo == "💎 Penny + Small ($0.05-$10)": universo_base = st.session_state.universo
elif modo == "📈 Large Cap ($10+)":         universo_base = st.session_state.universo
else:                                        universo_base = st.session_state.universo

r1, r2 = st.columns([3, 1])
with r1:
    hacer_rank = st.button(
        f"🏆 CALCULAR RANKING — Top {n_rank} más activos ({len(universo_base):,} stocks)",
        use_container_width=True)
with r2:
    if st.button("🗑️ Limpiar", use_container_width=True):
        st.session_state.ranking_df = pd.DataFrame()
        st.session_state.df_scan    = pd.DataFrame()
        st.rerun()

if hacer_rank:
    rk = ranking_rapido(universo_base, precio_min_f, precio_max_f, n_rank)
    st.session_state.ranking_df = rk
    if not rk.empty:
        st.success(f"✅ {len(rk)} candidatos seleccionados")
    else:
        st.error("❌ Sin resultados. Verifica conexión o amplía los filtros de precio.")

# Mostrar ranking
if not st.session_state.ranking_df.empty:
    rdf = st.session_state.ranking_df
    st.markdown(f"**🏆 Top {min(20, len(rdf))} más activos AHORA:**")
    cols_r = ["Ticker","Precio $","Δ %","Vel 5m %","RVOL","Vol"]
    rdf_s  = rdf[cols_r].head(20).copy()

    def cr_d(v):
        return f"color:{'#00ff88' if v>=0 else '#ff4444'};font-weight:bold"
    fmt_r = {"Precio $":"${:.4f}","Δ %":"{:+.2f}%",
              "Vel 5m %":"{:+.2f}%","RVOL":"{:.1f}x","Vol":"{:,.0f}"}
    try:
        rs = rdf_s.style.map(cr_d, subset=["Δ %","Vel 5m %"]).format(fmt_r)
    except Exception:
        try:
            rs = rdf_s.style.applymap(cr_d, subset=["Δ %","Vel 5m %"]).format(fmt_r)
        except Exception:
            rs = rdf_s.style.format(fmt_r)
    st.dataframe(rs, use_container_width=True, hide_index=True, height=350)

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────
# PORTAFOLIO
# ─────────────────────────────────────────────────────
st.subheader("💼 Portafolio Activo — P&L en Tiempo Real")
posiciones = get_pos()
if posiciones:
    rows = []
    for p in posiciones:
        pp = float(p.unrealized_plpc) * 100
        pu = float(p.unrealized_pl)
        ico = "🟢" if pp >= 0 else "🔴"
        rows.append({
            "Ticker": p.symbol, "Qty": p.qty,
            "Entrada $": round(float(p.avg_entry_price), 4),
            "Actual $":  round(float(p.current_price), 4),
            "P&L %":     f"{ico} {pp:+.2f}%",
            "P&L $":     f"${pu:+.2f}",
            "Valor $":   f"${float(p.market_value):,.2f}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    px1, px2, px3 = st.columns([2, 1, 1])
    with px1: tc = st.selectbox("Ticker a cerrar", [r["Ticker"] for r in rows])
    with px2:
        if st.button("🔴 Cerrar pos."):
            ok, msg = cerrar(tc)
            st.success(msg) if ok else st.error(msg)
    with px3:
        if st.button("🔴 Cerrar TODO"):
            [cerrar(p.symbol) for p in posiciones]
            st.warning("Cerrando...")
else:
    st.info("Sin posiciones. ¡Detecta el despegue! 🚀")

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────
# PASO 2 — ESCANEO 1min
# ─────────────────────────────────────────────────────
st.subheader("🔭 Paso 2 — Motor de Señal (1min · Supertrend · RVOL · Aceleración)")

sb1, sb2, sb3 = st.columns([2, 1, 1])
with sb1:
    iniciar = st.button("🚀 INICIAR ESCANEO DE DESPEGUES",
                        use_container_width=True)
with sb2:
    if st.button("🔄 Refresh UI", use_container_width=True):
        st.rerun()
with sb3:
    if st.session_state.last_scan:
        ts_s = (datetime.fromtimestamp(st.session_state.last_scan)
                .astimezone(tz_et).strftime("%H:%M:%S ET"))
        st.markdown(f'<span style="color:#8b949e;font-size:.74em">Último: {ts_s}</span>',
                    unsafe_allow_html=True)

# Lista para escaneo
if modo == "🎯 Mis Tickers":
    lista_scan = manual
    rank_scan  = pd.DataFrame({"Ticker": manual, "Δ %": [0]*len(manual)})
elif not st.session_state.ranking_df.empty:
    lista_scan = st.session_state.ranking_df["Ticker"].tolist()
    rank_scan  = st.session_state.ranking_df
else:
    lista_scan = BASE_VOLATILES[:200]
    rank_scan  = pd.DataFrame({"Ticker": lista_scan, "Δ %": [0]*len(lista_scan)})
    st.warning("⚠️ Sin ranking — usando lista base. Haz el **🏆 RANKING** para mejores resultados.")

st.info(f"📊 Escaneando **{len(lista_scan)} stocks** | {SESSION} | "
        f"RVOL≥{rvol_min}x | Vel≥{vel_min}%/min")

debe = iniciar or (
    auto_ref and st.session_state.last_scan is not None
    and (time.time() - st.session_state.last_scan) >= ref_seg
)

if debe:
    if not lista_scan:
        st.error("❌ Sin tickers. Calcula el ranking primero.")
    else:
        with st.spinner("⚡ Analizando despegues..."):
            df_scan = escanear_1min(
                rank_scan, precio_min_f, precio_max_f,
                rvol_min, vel_min, atr_sl, atr_tp,
                SESSION, st_per, st_mult, top_n_f
            )
        st.session_state.df_scan   = df_scan
        st.session_state.last_scan = time.time()
        ts_ok = datetime.now(tz_et).strftime("%H:%M:%S ET")
        n = len(df_scan)
        if n > 0:
            st.success(f"✅ {ts_ok} — **{n} señales detectadas**")
        else:
            st.warning(
                f"⚠️ {ts_ok} — Sin señales. "
                "Baja RVOL a 1.1x y Velocidad a 0.0% para ver todos los stocks."
            )

df_scan = st.session_state.df_scan

# ─────────────────────────────────────────────────────
# RESULTADOS
# ─────────────────────────────────────────────────────
if not df_scan.empty:
    despegues = df_scan[df_scan["Score 🐂"] >= 7]
    impulsos  = df_scan[(df_scan["Score 🐂"] >= 5) & (df_scan["Score 🐂"] < 7)]

    # Tarjetas de despegue
    if not despegues.empty:
        st.markdown(f"### 🚀 DESPEGUES — {len(despegues)} señales")
        for _, row in despegues.iterrows():
            s    = int(row["Score 🐂"])
            cls  = "s10" if s == 10 else ("s8" if s >= 8 else "s6")
            rv   = float(row["RVOL"])
            vc   = "#00ff88" if row["Vel 1m %"] >= 0 else "#ff4444"
            dc   = "#00ff88" if row["Δ Rank %"] >= 0  else "#ff4444"
            stc  = "#00ff88" if "ALCISTA" in str(row["Supertrend"]) else "#ff4444"
            card = "card-fire" if s >= 7 else "card-hot"
            rcl  = ("color:#ff4500;font-weight:900" if rv >= 10
                    else ("color:#ff8c00;font-weight:700" if rv >= 5
                          else "color:#ffc107"))

            st.markdown(f"""
            <div class="{card}">
              <span class="tkr">⚡ {row['Ticker']}</span>
              &nbsp;&nbsp;<span class="{cls}">{s}/10</span>
              &nbsp;&nbsp;<span style="color:#a78bfa;font-size:.85em">{row['Señal']}</span>
              &nbsp;&nbsp;<span style="color:{stc};font-size:.80em">{row['Supertrend']}</span>
              <br>
              <span class="lbl">Precio</span>
              <b style="color:#fff">${row['Precio $']}</b>
              &nbsp;|&nbsp;
              <span class="lbl">RVOL</span>
              <b style="{rcl}">{rv:.1f}x</b>
              &nbsp;|&nbsp;
              <span class="lbl">Vel 1min</span>
              <b style="color:{vc}">{row['Vel 1m %']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">Vel 2min</span>
              <b style="color:{vc}">{row['Vel 2m %']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">Δ Sesión</span>
              <b style="color:{dc}">{row['Δ Rank %']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">RSI</span> {row['RSI']}
              &nbsp;|&nbsp;
              <span class="lbl">ST$</span> {row['ST $']}
              <br>
              <span class="lbl">SL</span>
              <b style="color:#ff6b6b">${row['SL $']}</b>
              &nbsp;|&nbsp;
              <span class="lbl">TP</span>
              <b style="color:#00ff88">${row['TP $']}</b>
              &nbsp;|&nbsp;
              <span class="lbl">R:R</span> {row['R:R']}x
            </div>""", unsafe_allow_html=True)

    # Impulsos
    if not impulsos.empty:
        with st.expander(f"👁️ IMPULSOS EN FORMACIÓN ({len(impulsos)} — score 5-6)"):
            for _, row in impulsos.iterrows():
                vc  = "#00ff88" if row["Vel 1m %"] >= 0 else "#ff4444"
                stc = "#00ff88" if "ALCISTA" in str(row["Supertrend"]) else "#ff4444"
                st.markdown(f"""
                <div class="card-watch">
                  <b class="tkr" style="font-size:1.05em">{row['Ticker']}</b>
                  &nbsp;<span class="s6">{int(row['Score 🐂'])}/10</span>
                  &nbsp;<span style="color:#8b949e;font-size:.78em">{row['Señal']}</span>
                  &nbsp;<span style="color:{stc};font-size:.76em">{row['Supertrend']}</span>
                  &nbsp;|&nbsp;${row['Precio $']}
                  &nbsp;|&nbsp;<b>RVOL</b> {row['RVOL']}x
                  &nbsp;|&nbsp;<b style="color:{vc}">{row['Vel 1m %']:+.2f}%/min</b>
                  &nbsp;|&nbsp;<b>RSI</b> {row['RSI']}
                  &nbsp;|&nbsp;<b style="color:#ff6b6b">SL</b>${row['SL $']}
                  &nbsp;<b style="color:#00ff88">TP</b>${row['TP $']}
                </div>""", unsafe_allow_html=True)

    # Tabla completa
    st.markdown("### 📋 Tabla Completa del Radar")
    cols_t = ["Ticker","Precio $","RVOL","Vel 1m %","Vel 2m %","Acel",
              "Supertrend","ST $","Δ Rank %","Δ Día %",
              "Score 🐂","Score 🐻","Señal","RSI",
              "Soporte $","Resist $","SL $","TP $","R:R"]
    df_sh = df_scan[cols_t].copy()

    def cs(v):
        if v >= 8:   return "background-color:#15803d;color:white"
        elif v >= 6: return "background-color:#1d4ed8;color:white"
        elif v >= 4: return "background-color:#92400e;color:white"
        else:        return "background-color:#7f1d1d;color:white"

    def cv(v):
        return f"color:{'#00ff88' if v>=0 else '#ff4444'};font-weight:bold"

    def cr(v):
        if v >= 10:  return "color:#ff4500;font-weight:900"
        elif v >= 5: return "color:#ff8c00;font-weight:700"
        elif v >= 2: return "color:#ffc107;font-weight:bold"
        else:        return "color:#8b949e"

    fmt_t = {
        "Precio $":"${:.4f}","RVOL":"{:.1f}x","Vel 1m %":"{:+.2f}%",
        "Vel 2m %":"{:+.2f}%","Acel":"{:+.3f}","ST $":"${:.4f}",
        "Δ Rank %":"{:+.2f}%","Δ Día %":"{:+.2f}%","RSI":"{:.1f}",
        "Soporte $":"${:.4f}","Resist $":"${:.4f}",
        "SL $":"${:.4f}","TP $":"${:.4f}","R:R":"{:.2f}"
    }
    try:
        styled = (df_sh.style
                  .map(cs, subset=["Score 🐂","Score 🐻"])
                  .map(cv, subset=["Vel 1m %","Vel 2m %","Δ Rank %","Δ Día %"])
                  .map(cr, subset=["RVOL"])
                  .format(fmt_t))
    except Exception:
        try:
            styled = (df_sh.style
                      .applymap(cs, subset=["Score 🐂","Score 🐻"])
                      .applymap(cv, subset=["Vel 1m %","Vel 2m %","Δ Rank %","Δ Día %"])
                      .applymap(cr, subset=["RVOL"])
                      .format(fmt_t))
        except Exception:
            styled = df_sh.style.format(fmt_t)
    st.dataframe(styled, use_container_width=True, hide_index=True, height=430)

    # Auto-trade
    if modo_auto:
        st.markdown("### 🤖 Auto-Trade")
        np_ = len(get_pos())
        for _, row in df_scan[df_scan["Score 🐂"] >= auto_score].iterrows():
            if np_ >= max_pos:
                st.warning(f"Máx {max_pos} posiciones.")
                break
            ok, msg = buy(row["Ticker"], auto_qty, row["SL $"], row["TP $"])
            if ok: np_ += 1
            st.write(msg)

    # Ejecución manual
    st.markdown('<hr class="n">', unsafe_allow_html=True)
    st.markdown("### 🛒 Ejecución Manual")
    ce1, ce2 = st.columns([1, 2])
    with ce1:
        t_op  = st.selectbox("Ticker", df_scan["Ticker"].tolist())
        rsel  = df_scan[df_scan["Ticker"] == t_op].iloc[0]
        qty_m = st.number_input("Cantidad", value=1, min_value=1, step=1)
        sl_m  = st.number_input("SL $", value=float(rsel["SL $"]),
                                step=0.001, format="%.4f")
        tp_m  = st.number_input("TP $", value=float(rsel["TP $"]),
                                step=0.001, format="%.4f")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("🟢 COMPRAR", use_container_width=True):
                ok, msg = buy(t_op, qty_m, sl_m, tp_m)
                st.success(msg) if ok else st.error(msg)
        with b2:
            if st.button("🔴 VENDER", use_container_width=True):
                ok, msg = sell(t_op, qty_m)
                st.success(msg) if ok else st.error(msg)

    with ce2:
        st.markdown(f"### 📊 {t_op} — Detalle")
        stc2 = "#00ff88" if "ALCISTA" in str(rsel["Supertrend"]) else "#ff4444"
        st.markdown(
            f'<b style="color:{stc2}">{rsel["Supertrend"]}</b> '
            f'— Línea ST: <b>${rsel["ST $"]}</b>',
            unsafe_allow_html=True)
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Precio $",  f"${rsel['Precio $']:.4f}")
        m2.metric("RVOL",      f"{rsel['RVOL']:.1f}x")
        m3.metric("Vel 1min",  f"{rsel['Vel 1m %']:+.2f}%")
        m4.metric("Score 🐂",  f"{rsel['Score 🐂']}/10")
        m5,m6,m7,m8 = st.columns(4)
        m5.metric("RSI",       f"{rsel['RSI']}")
        m6.metric("SL $",      f"${rsel['SL $']:.4f}")
        m7.metric("TP $",      f"${rsel['TP $']:.4f}")
        m8.metric("R:R",       f"{rsel['R:R']}x")
        det = rsel.get("_det", {})
        if det:
            st.markdown("**📌 Motor de señal:**")
            for k, v in det.items():
                c = ("#00ff88" if any(x in v for x in
                                     ["▲","🚀","⚡","🔥","✅","🟢"])
                     else ("#ff4444" if any(x in v for x in
                                          ["▼","💥","❌","🔴"])
                           else "#ffc107"))
                st.markdown(
                    f'<span style="color:{c};font-size:.79em">'
                    f'<b>{k}</b>: {v}</span>',
                    unsafe_allow_html=True)

elif st.session_state.last_scan is not None:
    st.warning("""
    ⚠️ **Sin señales. Prueba esto:**
    1. Baja **RVOL mínimo** a **1.1x**
    2. Baja **Velocidad mínima** a **0.0%**
    3. Haz el **🏆 RANKING** primero
    4. Verifica que el mercado esté activo (regular: 9:30-16:00 ET)
    """)
else:
    st.markdown("""
    ### 📋 Flujo recomendado:

    **1️⃣** Pulsa **🌐 Cargar universo** (una vez al día)

    **2️⃣** Pulsa **🏆 CALCULAR RANKING** → selecciona los 150 más activos AHORA

    **3️⃣** Pulsa **🚀 INICIAR ESCANEO** → detecta despegues con Supertrend + RVOL

    > Los stocks como BIYA +125%, NEXR +62%, ATER +55%
    > aparecen en el **ranking** porque ya tienen movimiento,
    > y el **escaneo** detecta el momento exacto de aceleración.
    """)

# Auto-refresh
if auto_ref:
    time.sleep(ref_seg)
    st.rerun()

st.markdown('<hr class="n">', unsafe_allow_html=True)
st.markdown("""<div style="text-align:center;color:#8b949e;font-size:.69em;
font-family:'Share Tech Mono',monospace">
⚡ THUNDER RADAR V94 — PAPER TRADING — Solo uso educativo y experimental<br>
Los resultados pasados no garantizan rendimientos futuros. Opera con responsabilidad.
</div>""", unsafe_allow_html=True)
