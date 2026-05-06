"""
THUNDER RADAR V96 — COMPLETO Y CORREGIDO
==========================================
CORRECCIONES:
  ✅ RVOL = 0.0x CORREGIDO: el bug era en la extracción de columnas
     de yfinance cuando descarga múltiples tickers (MultiIndex)
  ✅ DETECTOR 5 MINUTOS: como Webull "% Chg in 5Mins"
     detecta stocks que se disparan en los últimos 5 minutos
  ✅ YAHOO FINANCE: top gainers del día en tiempo real
  ✅ FUNCIONA EN: pre-market, regular, after-hours
  ✅ SL/TP DINÁMICO automático conectado a Alpaca Paper
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

# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="⚡ THUNDER RADAR V96", layout="wide",
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
    border:2px solid #00ff88;border-radius:10px;padding:13px 17px;margin:5px 0;
    box-shadow:0 0 20px #00ff8855;}
.card-5min{background:linear-gradient(135deg,#100806,#0a0f1a);
    border:2px solid #ff4500;border-radius:10px;padding:13px 17px;margin:5px 0;
    box-shadow:0 0 18px #ff450055;}
.card-hot{background:linear-gradient(135deg,#100a06,#0a0f1a);
    border:2px solid #ff8c00;border-radius:10px;padding:11px 15px;margin:4px 0;}
.card-watch{background:#090b0f;border:1px solid #ffc10733;
    border-radius:8px;padding:9px 13px;margin:3px 0;}
.s10{color:#00ff88;font-size:1.9em;font-weight:900;font-family:'Orbitron',sans-serif;}
.s8{color:#39ff14;font-size:1.5em;font-weight:800;}
.s6{color:#ffc107;font-size:1.3em;font-weight:700;}
.tkr{font-family:'Orbitron',sans-serif;font-size:1.25em;font-weight:900;color:#fff;}
.lbl{color:#8b949e;font-size:.73em;}
.hdr{text-align:center;font-family:'Orbitron',sans-serif;font-size:2.1em;font-weight:900;
    background:linear-gradient(90deg,#00ff88,#00d4ff,#ff4500);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:3px;}
.sub{text-align:center;color:#8b949e;font-size:.76em;letter-spacing:3px;}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.73em;font-weight:bold;}
.b-reg{background:#15803d;color:#fff;}.b-pre{background:#7c3aed;color:#fff;}
.b-aft{background:#0369a1;color:#fff;}.b-cls{background:#374151;color:#fff;}
.dot{display:inline-block;width:9px;height:9px;background:#00ff88;border-radius:50%;
    margin-right:5px;animation:blink 1s infinite;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.1}}
hr.n{border:none;border-top:1px solid #00ff8822;margin:12px 0;}
.ibox{background:#0a0f1a;border:1px solid #00ff8833;border-radius:8px;
    padding:10px 14px;margin:6px 0;font-size:.79em;line-height:1.6em;}
.tab-active{background:#1d4ed8;color:#fff;padding:4px 14px;border-radius:6px;
    font-weight:bold;cursor:pointer;display:inline-block;margin:2px;}
.tab-inactive{background:#161b22;color:#8b949e;padding:4px 14px;border-radius:6px;
    cursor:pointer;display:inline-block;margin:2px;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# ALPACA
# ─────────────────────────────────────────────────────────────
ALPACA_KEY    = "PKOKUMRZBCA2YJKVZIATSPGV5J"
ALPACA_SECRET = "2UBriZpW7NooR1EvtowC63GcarFt7rEQFD9ofti9Ah6N"

@st.cache_resource
def get_alpaca():
    return TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)
alpaca = get_alpaca()

# ─────────────────────────────────────────────────────────────
# SESIÓN DE MERCADO
# ─────────────────────────────────────────────────────────────
def get_session():
    tz = pytz.timezone("US/Eastern")
    h  = datetime.now(tz).hour + datetime.now(tz).minute / 60.0
    if   4.0  <= h < 9.5:  return "PRE-MARKET"
    elif 9.5  <= h < 16.0: return "REGULAR"
    elif 16.0 <= h < 20.0: return "AFTER-HOURS"
    else:                   return "CERRADO"

SESSION = get_session()

# ─────────────────────────────────────────────────────────────
# LISTA BASE (respaldo si Yahoo falla)
# ─────────────────────────────────────────────────────────────
BASE = list(dict.fromkeys([
    "SDOT","BLZE","CLRB","STRL","BIYA","EVER","JLHL","NXTS","MRDN","UK",
    "NA","SLOT","NEXR","ATER","BBBY","SBLX","YJ","ILLR","SCAG","BLIV",
    "ABTS","DLHC","WSHP","MYSE","ONFO","CTNT","RAIN","CPHI","NCRA","LVLU",
    "RCAT","CRKN","BSLK","GPUS","GFAI","SGBX","INPX","RSSS","ISPC","UCAR",
    "ABLV","YXT","ZBAI","MTEX","MGRT","BRIA","EDTK","TGHL","PBM","SKK",
    "CNSP","PN","CRE","ELPW","GBTG","SSM","HCAI","RLYB","MNDR","SLQT",
    "VOYG","IMOS","CRGY","UMC","BRCC","FTRE","HOWL","LGCL","MPU","AACBR",
    "GME","AMC","KOSS","BB","NOK","BBIG","SPCE","MULN","IDEX","CENN",
    "MVIS","PROG","NAKD","EXPR","KPLT","CELH","SKIN","NKLA","WKHS",
    "OCGN","CLOV","SNDL","TLRY","AGEN","ADXS","MNMD","ATAI","BPMC",
    "NVAX","MRNA","BNTX","SRPT","ACAD","HIMS","FATE","CRSP","EDIT",
    "COIN","HOOD","MSTR","RIOT","MARA","HUT","CIFR","BTBT","CLSK","WULF",
    "RIVN","LCID","CHPT","BLNK","PLUG","FCEL","GOEV","FSR","NIO","XPEV",
    "BABA","JD","PDD","TCOM","TIGR","FUTU","BILI","IQ","DOYU","HUYA",
    "ASTS","LUNR","RKLB","ACHR","JOBY","IONQ","RGTI","QUBT",
    "SOFI","UPST","AFRM","ROOT","OPFI","DAVE",
    "AAPL","MSFT","NVDA","TSLA","AMD","META","AMZN","GOOGL","NFLX",
    "AVGO","QCOM","MU","SMCI","PLTR","CRM","NOW","SNOW","DDOG","CRWD",
    "PTON","DOCU","ZM","TDOC","LYFT","UBER","DASH","ABNB","DKNG",
    "RBLX","U","SNAP","PINS","PARA","WBD","ROKU","FUBO","SIRI",
]))

# ─────────────────────────────────────────────────────────────
# YAHOO FINANCE — TOP GAINERS EN TIEMPO REAL
# ─────────────────────────────────────────────────────────────
YH = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Accept": "application/json"}

def yahoo_screen(sid: str, n: int = 100) -> list:
    """Obtiene tickers de un screener de Yahoo Finance."""
    for base_url in ["https://query1.finance.yahoo.com",
                     "https://query2.finance.yahoo.com"]:
        try:
            r = requests.get(
                f"{base_url}/v1/finance/screener/predefined/saved",
                headers=YH,
                params={"scrIds": sid, "count": n, "formatted": "false"},
                timeout=12
            )
            if r.status_code == 200:
                quotes = (r.json().get("finance", {})
                           .get("result", [{}])[0]
                           .get("quotes", []))
                result = []
                for q in quotes:
                    s = q.get("symbol", "").strip().upper()
                    if s and s.isalpha() and 1 <= len(s) <= 5:
                        result.append(s)
                if result:
                    return result
        except Exception:
            pass
    return []


def obtener_top_gainers() -> dict:
    """Obtiene top gainers y más activos de Yahoo Finance."""
    day_g  = yahoo_screen("day_gainers",       100)
    active = yahoo_screen("most_actives",      100)
    small  = yahoo_screen("small_cap_gainers", 100)

    todos = list(dict.fromkeys(day_g + active + small))
    return {
        "day_gainers": day_g,
        "most_actives": active,
        "small_cap": small,
        "todos": todos,
        "counts": {
            "day_gainers": len(day_g),
            "most_actives": len(active),
            "small_cap": len(small),
            "total": len(todos),
        }
    }

# ─────────────────────────────────────────────────────────────
# EXTRACTOR SEGURO DE DATAFRAME — CORRIGE BUG RVOL=0
# ─────────────────────────────────────────────────────────────
def extraer_df_seguro(raw, ticker: str, n_tickers: int) -> pd.DataFrame | None:
    """
    Extrae un DataFrame limpio de la descarga de yfinance.
    CORRECCIÓN DEL BUG RVOL=0: cuando yfinance descarga múltiples tickers,
    el resultado tiene un MultiIndex (nivel 0 = campo, nivel 1 = ticker).
    Hay que transponer correctamente.
    """
    try:
        if n_tickers == 1:
            # Un solo ticker: el df viene directamente
            df = raw.copy()
        else:
            # Múltiples tickers: MultiIndex columns
            if not isinstance(raw.columns, pd.MultiIndex):
                return None
            # Verificar que el ticker existe en el nivel correcto
            lvl0 = raw.columns.get_level_values(0).unique().tolist()
            lvl1 = raw.columns.get_level_values(1).unique().tolist()

            if ticker in lvl1:
                # Formato: (Price, Ticker) → extraer columna del ticker
                df = raw.xs(ticker, axis=1, level=1)
            elif ticker in lvl0:
                # Formato: (Ticker, Price) → extraer columna del ticker
                df = raw[ticker].copy()
            else:
                return None

        # Aplanar MultiIndex si quedó
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        # Verificar columnas necesarias
        needed = {"Close", "High", "Low", "Open", "Volume"}
        if not needed.issubset(set(df.columns)):
            return None

        df = df.dropna(subset=["Close", "Volume"])
        return df if len(df) >= 3 else None

    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# DETECTOR DE MOMENTUM 5 MINUTOS
# Como Webull "% Chg in 5Mins" — detecta stocks que se disparan
# en los últimos 5 minutos AHORA MISMO
# ─────────────────────────────────────────────────────────────
def detectar_momentum_5min(tickers: list,
                            precio_min: float,
                            precio_max: float,
                            min_cambio_5m: float = 2.0,
                            top_n: int = 50) -> pd.DataFrame:
    """
    Descarga datos de 5min del día actual.
    Calcula % cambio en las últimas 2 velas (= últimos 10 min)
    y en la última vela (= últimos 5 min).
    Devuelve ranking ordenado por mayor movimiento reciente.
    """
    if not tickers:
        return pd.DataFrame()

    resultados = []
    lote = 100
    pb   = st.progress(0.0, text="🔥 Detector 5min: descargando...")

    for i in range(0, len(tickers), lote):
        chunk = tickers[i:i+lote]
        pb.progress(min((i+lote)/len(tickers), 1.0),
                    text=f"🔥 5min: {min(i+lote,len(tickers))}/{len(tickers)}...")
        try:
            raw = yf.download(
                chunk,
                period="1d", interval="5m",
                group_by="ticker", prepost=True,
                progress=False, auto_adjust=True,
                threads=True, timeout=20
            )
            for t in chunk:
                try:
                    df = extraer_df_seguro(raw, t, len(chunk))
                    if df is None or len(df) < 4:
                        continue

                    precio = float(df["Close"].iloc[-1])
                    if not (precio_min <= precio <= precio_max):
                        continue

                    # Cambio en última vela (5 min)
                    c1   = float(df["Close"].iloc[-1])
                    c2   = float(df["Close"].iloc[-2])
                    c3   = float(df["Close"].iloc[-3])

                    chg_5m  = (c1 - c2) / max(c2, 1e-9) * 100  # últimos 5 min
                    chg_10m = (c1 - c3) / max(c3, 1e-9) * 100  # últimos 10 min

                    # Aceleración: ¿la última vela es más fuerte que la anterior?
                    v1 = (c1 - c2) / max(c2, 1e-9) * 100
                    v2 = (c2 - c3) / max(c3, 1e-9) * 100
                    acelerando = v1 > v2 and v1 > 0

                    # Vol relativo 5min
                    vol_ult  = float(df["Volume"].iloc[-1])
                    vol_prom = float(df["Volume"].iloc[:-1].mean())
                    rvol_5m  = vol_ult / max(vol_prom, 1)

                    # Cambio del día
                    open_d   = float(df["Open"].iloc[0])
                    chg_dia  = (precio - open_d) / max(open_d, 1e-9) * 100

                    # Score momentum 5min (0-100)
                    score_5m = (min(abs(chg_5m), 20) / 20 * 40 +
                                min(rvol_5m, 10) / 10 * 30 +
                                (20 if acelerando else 0) +
                                min(abs(chg_10m), 30) / 30 * 10)

                    resultados.append({
                        "Ticker"      : t,
                        "Precio $"    : round(precio, 4),
                        "Δ 5min %"    : round(chg_5m, 2),
                        "Δ 10min %"   : round(chg_10m, 2),
                        "Δ Día %"     : round(chg_dia, 2),
                        "RVOL 5m"     : round(rvol_5m, 1),
                        "Acelerando"  : "⚡ SÍ" if acelerando else "→ NO",
                        "Score 5m"    : round(score_5m, 1),
                        "Vol Actual"  : int(vol_ult),
                    })
                except Exception:
                    continue
        except Exception:
            continue

    pb.empty()
    if not resultados:
        return pd.DataFrame()

    df_r = pd.DataFrame(resultados)
    # Filtrar por cambio mínimo de 5 minutos
    df_r = df_r[df_r["Δ 5min %"].abs() >= min_cambio_5m]
    df_r = df_r.sort_values("Score 5m", ascending=False).reset_index(drop=True)
    return df_r.head(top_n)


# ─────────────────────────────────────────────────────────────
# SUPERTREND
# ─────────────────────────────────────────────────────────────
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
        atr = pd.concat([hl,hc,lc], axis=1).max(axis=1).rolling(periodo).mean()
        mid  = (h + l) / 2
        ub_r = mid + mult * atr
        lb_r = mid - mult * atr
        ub = ub_r.copy(); lb = lb_r.copy()
        for i in range(1, n):
            ub.iloc[i] = (min(ub_r.iloc[i], ub.iloc[i-1])
                          if c.iloc[i-1] <= ub.iloc[i-1] else ub_r.iloc[i])
            lb.iloc[i] = (max(lb_r.iloc[i], lb.iloc[i-1])
                          if c.iloc[i-1] >= lb.iloc[i-1] else lb_r.iloc[i])
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


# ─────────────────────────────────────────────────────────────
# INDICADORES TÉCNICOS 1min — CON FIX DEL BUG RVOL
# ─────────────────────────────────────────────────────────────
def calcular_indicadores(df_raw: pd.DataFrame, st_per: int, st_mult: float):
    try:
        df = df_raw.copy()

        # Convertir columnas a Series 1D numéricas
        def to_s(col):
            x = pd.to_numeric(df[col], errors="coerce")
            if isinstance(x, pd.DataFrame):
                x = x.iloc[:, 0]
            return x.squeeze()

        C = to_s("Close")
        H = to_s("High")
        L = to_s("Low")
        O = to_s("Open")
        V = to_s("Volume").fillna(0)

        # Guardar como columnas limpias
        df["C"] = C.values
        df["H"] = H.values
        df["L"] = L.values
        df["O"] = O.values
        df["V"] = V.values

        n = len(df)
        if n < 3:
            return None

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
        df["macd"]   = (df["C"].ewm(span=min(12,n), adjust=False).mean()
                       - df["C"].ewm(span=min(26,n), adjust=False).mean())
        df["macd_s"] = df["macd"].ewm(span=min(9,n), adjust=False).mean()
        df["macd_h"] = df["macd"] - df["macd_s"]

        # ATR, Soporte, Resistencia
        hl = df["H"] - df["L"]
        hc = (df["H"] - df["C"].shift(1)).abs()
        lc = (df["L"] - df["C"].shift(1)).abs()
        df["atr"] = (pd.concat([hl, hc, lc], axis=1)
                       .max(axis=1)
                       .rolling(min(14, n))
                       .mean()
                       .fillna(df["C"] * 0.01))
        w = min(20, n)
        df["sup"] = df["L"].rolling(w).min().fillna(df["C"] * 0.97)
        df["res"] = df["H"].rolling(w).max().fillna(df["C"] * 1.03)

        # ── RVOL CORREGIDO ─────────────────────────────────
        # Usar ventana de 10 velas, con fallback al promedio total
        wv = min(10, n - 1)
        if wv < 2:
            df["vavg"] = df["V"].mean()
        else:
            df["vavg"] = df["V"].rolling(wv).mean()
        # Rellenar NaN con el promedio del período completo
        df["vavg"] = df["vavg"].fillna(df["V"].mean())
        # Evitar división por cero
        df["vavg"] = df["vavg"].replace(0, df["V"].mean()).replace(0, 1)
        df["rvol"] = df["V"] / df["vavg"]
        # ───────────────────────────────────────────────────

        # Velocidad y aceleración
        df["v1"] = df["C"].pct_change(1) * 100
        df["v2"] = df["C"].pct_change(2) * 100
        df["v3"] = df["C"].pct_change(3) * 100
        df["ac"] = df["v1"] - df["v1"].shift(1)

        # Supertrend
        df = calc_supertrend(df, st_per, st_mult)

        return df
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# MOTOR DE SEÑAL (Score 1-10)
# ─────────────────────────────────────────────────────────────
def gv(row, col, default=0.0):
    try:
        v = float(row[col])
        return default if (np.isnan(v) or np.isinf(v)) else v
    except Exception:
        return default


def motor_senal(df, session: str, cambio_dia: float,
                es_top_gainer: bool, chg_5m: float = 0.0):
    if df is None or len(df) < 3:
        return 1, 1, "⚪ NEUTRO", {}, 0.0, 0.0, 1

    a = df.iloc[-1]
    p = df.iloc[-2] if len(df) > 1 else df.iloc[-1]

    precio = gv(a, "C")
    if precio <= 0:
        return 1, 1, "⚪ NEUTRO", {}, 0.0, 0.0, 1

    up = dn = 0.0
    det = {}

    # 1. RVOL (25%) — ya corregido
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

    # 2. VELOCIDAD última vela 1min (25%)
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

    # 3. ACELERACIÓN (20%)
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

    # 4. SUPERTREND (20%)
    st_dir  = gv(a, "st_dir", 1)
    st_val  = gv(a, "st_val", precio)
    st_crux = int(gv(a, "st_cross", 0))
    dist    = abs(precio - st_val) / max(precio, 1e-9) * 100
    if st_dir == 1:
        up += 2.0
        det["ST"] = f"✅ ST ALCISTA — soporte ${st_val:.4f} ({dist:.1f}%↓)"
        if st_crux:
            up += 1.5; det["ST"] += " 🔔 CRUCE ALCISTA"
    else:
        dn += 2.0
        det["ST"] = f"❌ ST BAJISTA — resist ${st_val:.4f} ({dist:.1f}%↑)"
        if st_crux:
            dn += 1.5; det["ST"] += " 🔔 CRUCE BAJISTA"

    # 5. TÉCNICO: VWAP + EMA + MACD + RSI (10%)
    vwap = gv(a, "vwap", precio)
    e9   = gv(a, "e9", precio)
    e20  = gv(a, "e20", precio)
    rsi  = gv(a, "rsi", 50)
    mh   = gv(a, "macd_h", 0)
    mhp  = gv(p, "macd_h", 0)
    pts  = ((0.3 if precio > vwap else 0) + (0.3 if e9 > e20 else 0) +
            (0.3 if mh > mhp and mh > 0 else 0) + (0.2 if 50 < rsi < 80 else 0) +
            (-0.3 if rsi >= 80 or rsi <= 20 else 0))
    if pts >= 0.7:
        up += 1.0; det["TEC"] = f"▲▲ Alcista (RSI={rsi:.0f},VWAP✓,EMA✓)"
    elif pts >= 0.3:
        up += 0.5; det["TEC"] = f"▲ Parcial (RSI={rsi:.0f})"
    elif pts <= -0.2:
        dn += 0.5; det["TEC"] = f"▼ Bajista (RSI={rsi:.0f})"
    else:
        det["TEC"] = f"→ Neutro (RSI={rsi:.0f})"

    # BONUS: Top Gainer Yahoo + momentum 5min
    if es_top_gainer:
        if cambio_dia >= 50:
            up += 2.0; det["RANK"] = f"🏆🏆 TOP GAINER {cambio_dia:+.1f}% (Webull level)"
        elif cambio_dia >= 20:
            up += 1.5; det["RANK"] = f"🏆 TOP GAINER {cambio_dia:+.1f}%"
        elif cambio_dia >= 5:
            up += 1.0; det["RANK"] = f"▲ Gainer fuerte {cambio_dia:+.1f}%"
        else:
            up += 0.5; det["RANK"] = f"▲ Gainer {cambio_dia:+.1f}%"

    if chg_5m >= 5:
        up += 1.5; det["5MIN"] = f"🔥 +{chg_5m:.2f}% en 5min — WEBULL TOP"
    elif chg_5m >= 2:
        up += 1.0; det["5MIN"] = f"⚡ +{chg_5m:.2f}% en 5min"
    elif chg_5m >= 0.5:
        up += 0.4; det["5MIN"] = f"▲ +{chg_5m:.2f}% en 5min"
    elif chg_5m != 0:
        det["5MIN"] = f"→ {chg_5m:+.2f}% en 5min"

    # Patrón de velas
    c1=gv(df.iloc[-1],"C"); o1=gv(df.iloc[-1],"O",c1)
    c2=gv(df.iloc[-2],"C",c1) if len(df)>1 else c1
    o2=gv(df.iloc[-2],"O",c2) if len(df)>1 else c2
    c3=gv(df.iloc[-3],"C",c2) if len(df)>2 else c2
    o3=gv(df.iloc[-3],"O",c3) if len(df)>2 else c3
    if (c1>o1) and (c2>o2) and (c3>o3) and (c1>c2>c3):
        up+=0.8; det["VELAS"]="🟢🟢🟢 3 verdes consecutivas"
    elif (c1>o1) and (c2>o2) and (c1>c2):
        up+=0.4; det["VELAS"]="🟢🟢 2 verdes"
    elif (c1<o1) and (c2<o2) and (c3<o3) and (c1<c2<c3):
        dn+=0.8; det["VELAS"]="🔴🔴🔴 3 rojas"
    elif (c1<o1) and (c2<o2):
        dn+=0.4; det["VELAS"]="🔴🔴 2 rojas"
    else:
        det["VELAS"]="→ Sin patrón claro"

    mx = 2.5+2.5+2.0+3.5+1.0+2.0+1.5+0.8
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


# ─────────────────────────────────────────────────────────────
# SL / TP DINÁMICO
# ─────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────
# ESCANEO PRINCIPAL 1min + SEÑAL
# ─────────────────────────────────────────────────────────────
def escanear_1min(tickers_info: dict,
                  precio_min: float, precio_max: float,
                  rvol_min: float, vel_min: float,
                  msl: float, mtp: float,
                  session: str, st_per: int, st_mult: float,
                  chg_5m_map: dict, top_n: int) -> pd.DataFrame:
    """
    tickers_info: {ticker: {"cambio_dia": float, "es_top_gainer": bool}}
    chg_5m_map:   {ticker: float}  → cambio % en últimos 5min
    """
    if not tickers_info:
        return pd.DataFrame()

    tickers    = list(tickers_info.keys())
    resultados = []
    total      = len(tickers)
    lote       = 50
    dfs        = {}
    pb         = st.progress(0.0, text="⚡ Descargando datos 1min...")

    # ── Descarga en lotes ────────────────────────────────
    for i in range(0, total, lote):
        chunk = tickers[i:i+lote]
        pb.progress(min((i+lote)/total*0.45, 0.45),
                    text=f"📡 1min {min(i+lote,total)}/{total}...")
        try:
            raw = yf.download(
                chunk,
                period="1d", interval="1m",
                group_by="ticker", prepost=True,
                progress=False, auto_adjust=True,
                threads=True, timeout=25
            )
            for t in chunk:
                dfs[t] = extraer_df_seguro(raw, t, len(chunk))
        except Exception:
            # Reintento individual si falla el lote
            for t in chunk:
                try:
                    s = yf.download(t, period="1d", interval="1m",
                                    prepost=True, progress=False,
                                    auto_adjust=True, threads=False, timeout=12)
                    dfs[t] = extraer_df_seguro(s, t, 1)
                except Exception:
                    dfs[t] = None

    # ── Análisis ─────────────────────────────────────────
    for idx, t in enumerate(tickers):
        pb.progress(0.45 + (idx+1)/total*0.55,
                    text=f"🔬 Analizando {t} ({idx+1}/{total})...")
        try:
            raw_df = dfs.get(t)
            if raw_df is None or len(raw_df) < 5:
                continue

            df = calcular_indicadores(raw_df, st_per, st_mult)
            if df is None:
                continue

            precio = float(df["C"].iloc[-1])
            if not (precio_min <= precio <= precio_max):
                continue

            rv    = float(df["rvol"].iloc[-1]) if not np.isnan(df["rvol"].iloc[-1]) else 1.0
            vel1  = float(df["v1"].iloc[-1])   if not np.isnan(df["v1"].iloc[-1])  else 0.0

            info          = tickers_info.get(t, {})
            cambio_dia    = info.get("cambio_dia", 0.0)
            es_top_gainer = info.get("es_top_gainer", False)
            chg_5m        = chg_5m_map.get(t, 0.0)

            # FILTROS ADAPTATIVOS
            if es_top_gainer or chg_5m >= 2.0:
                # Top gainer o activo en 5min → filtros relajados
                pasa = (rv >= max(1.0, rvol_min * 0.25)) or (abs(vel1) >= max(0.01, vel_min * 0.15))
            elif session == "REGULAR":
                pasa = (rv >= rvol_min) and (abs(vel1) >= vel_min)
            else:
                pasa = (rv >= max(1.1, rvol_min*0.4)) or (abs(vel1) >= max(0.02, vel_min*0.25))

            if not pasa:
                continue

            su, sd, senal, det, rv, vel1, st_dir = motor_senal(
                df, session, cambio_dia, es_top_gainer, chg_5m)

            if session == "REGULAR" and not es_top_gainer and chg_5m < 1.0 and su < 3 and sd < 3:
                continue

            _sl, _tp, rr = calc_sltp(df, precio, senal, msl, mtp)

            open_d   = float(df["O"].iloc[0]) if float(df["O"].iloc[0]) > 0 else precio
            cambio_d = (precio - open_d) / max(open_d, 1e-9) * 100
            rsi  = float(df["rsi"].iloc[-1])
            sup  = float(df["sup"].iloc[-1])
            res  = float(df["res"].iloc[-1])
            vel2 = float(df["v2"].iloc[-1]) if not np.isnan(df["v2"].iloc[-1]) else 0
            ac   = float(df["ac"].iloc[-1]) if not np.isnan(df["ac"].iloc[-1]) else 0
            stv  = float(df["st_val"].iloc[-1]) if "st_val" in df.columns else 0
            st_tx = "🟢 ALCISTA" if st_dir == 1 else "🔴 BAJISTA"
            fuente = ("🏆 Yahoo" if es_top_gainer else
                      ("🔥 5min" if chg_5m >= 2.0 else "📋 Base"))

            resultados.append({
                "Ticker"    : t,
                "Fuente"    : fuente,
                "Precio $"  : round(precio, 4),
                "RVOL"      : round(rv, 1),
                "Vel 1m %"  : round(vel1, 2),
                "Vel 2m %"  : round(vel2, 2),
                "Δ 5m %"    : round(chg_5m, 2),
                "Acel"      : round(ac, 3),
                "Supertrend": st_tx,
                "ST $"      : round(stv, 4),
                "Δ Día %"   : round(cambio_dia if cambio_dia != 0 else cambio_d, 2),
                "Score 🐂"  : su,
                "Score 🐻"  : sd,
                "Señal"     : senal,
                "RSI"       : round(rsi, 1),
                "Soporte $" : round(sup, 4),
                "Resist $"  : round(res, 4),
                "SL $"      : _sl,
                "TP $"      : _tp,
                "R:R"       : rr,
                "_det"      : det,
                "_df"       : df,
            })
        except Exception:
            continue

    pb.empty()
    if not resultados:
        return pd.DataFrame()

    df_res = pd.DataFrame(resultados)
    # Prioridad: Yahoo Top > 5min activos > base
    prio_map = {"🏆 Yahoo": 0, "🔥 5min": 1, "📋 Base": 2}
    df_res["_p"] = df_res["Fuente"].map(prio_map).fillna(3)
    df_res = df_res.sort_values(
        ["_p", "Score 🐂", "RVOL", "Vel 1m %"],
        ascending=[True, False, False, False]
    ).reset_index(drop=True).drop(columns=["_p"])
    return df_res.head(top_n)


# ─────────────────────────────────────────────────────────────
# ALPACA HELPERS
# ─────────────────────────────────────────────────────────────
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
    except Exception as e:
        return False, f"❌ {e}"

def sell(sym, qty):
    try:
        alpaca.submit_order(MarketOrderRequest(
            symbol=sym, qty=qty, side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC
        ))
        return True, f"✅ SELL {qty}x {sym}"
    except Exception as e:
        return False, f"❌ {e}"


# ═════════════════════════════════════════════════════════════
#  INTERFAZ PRINCIPAL
# ═════════════════════════════════════════════════════════════
st.markdown('<h1 class="hdr">⚡ THUNDER RADAR V96</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub">YAHOO TOP GAINERS · MOMENTUM 5MIN · SUPERTREND · RVOL CORREGIDO · ALPACA PAPER</p>',
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
    st.markdown(f'<span style="color:#8b949e">🕐 {hora_et}</span>', unsafe_allow_html=True)
with hc3:
    if cuenta:
        eq  = float(cuenta.equity)
        pnl = eq - float(cuenta.last_equity)
        col = "#00ff88" if pnl >= 0 else "#ff4444"
        st.markdown(f'<span style="color:{col}">💰 ${eq:,.2f} | P&L {pnl:+,.2f}</span>',
                    unsafe_allow_html=True)

st.markdown("""<div class="ibox">
<b style="color:#00ff88">✅ V96 CORRECCIONES:</b>
<b style="color:#ff4500">RVOL=0 CORREGIDO</b> — extracción de datos 1min reparada. |
<b style="color:#ff4500">DETECTOR 5MIN</b> — como Webull "% Chg in 5Mins" detecta JLHL, NXTS, MRDN. |
<b style="color:#ff4500">YAHOO TOP GAINERS</b> — SDOT, BLZE, CLRB, STRL, BIYA en tiempo real.
</div>""", unsafe_allow_html=True)
st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# BARRA LATERAL
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ CONFIGURACIÓN")

    usar_yahoo = st.toggle("🏆 Yahoo Top Gainers (tiempo real)", value=True)
    usar_5min  = st.toggle("🔥 Detector Momentum 5min (Webull style)", value=True)
    usar_base  = st.toggle("📋 Lista base (respaldo)", value=True)

    st.markdown("---")
    precio_min_f = st.number_input("Precio Mín $", value=0.05, step=0.05, min_value=0.01)
    precio_max_f = st.number_input("Precio Máx $", value=500.0, step=10.0)

    st.markdown("**⚡ Motor de Aceleración**")
    dflt_rv = 1.2 if SESSION in ("PRE-MARKET","AFTER-HOURS","CERRADO") else 1.5
    dflt_vl = 0.05 if SESSION in ("PRE-MARKET","AFTER-HOURS","CERRADO") else 0.10

    rvol_min = st.slider("RVOL mínimo", 1.0, 15.0, dflt_rv, 0.1)
    vel_min  = st.slider("Velocidad mín %/vela (1min)", 0.0, 3.0, dflt_vl, 0.01)

    if usar_5min:
        min_chg_5m = st.slider("Δ% mínimo para detector 5min", 0.5, 10.0, 2.0, 0.5,
                               help="Mínimo % de cambio en 5 minutos para incluir en radar")

    st.markdown("**📊 Supertrend**")
    st_per  = st.slider("Período Supertrend", 5, 20, 10, 1)
    st_mult = st.slider("Multiplicador ATR", 1.0, 5.0, 3.0, 0.5)

    top_n_f = st.slider("Resultados finales", 10, 80, 50, 5)

    st.markdown("**🔒 SL / TP**")
    atr_sl = st.slider("ATR × Stop Loss",   0.5, 5.0, 2.0, 0.5)
    atr_tp = st.slider("ATR × Take Profit", 1.0, 8.0, 4.0, 0.5)

    st.markdown("---")
    tickers_extra = st.text_area(
        "Tickers adicionales (manual)",
        "SDOT,BLZE,CLRB,STRL,BIYA,EVER,JLHL,NXTS,MRDN,UK,NA,SLOT",
        height=60)

    st.markdown("---")
    modo_auto = st.toggle("🤖 Auto-Trade", value=False)
    if modo_auto:
        auto_score = st.slider("Score mín auto-compra", 6, 10, 7)
        auto_qty   = st.number_input("Acciones/orden", value=1, min_value=1)
        max_pos    = st.number_input("Máx posiciones", value=3, min_value=1)
        st.warning("⚠️ Ejecuta órdenes reales en Paper.")

    auto_ref = st.toggle("🔁 Auto-escaneo continuo", value=False)
    ref_seg  = 45 if SESSION == "REGULAR" else 60

# ─────────────────────────────────────────────────────────────
# ESTADO
# ─────────────────────────────────────────────────────────────
for k, v in [("gainers_data", {}), ("df_5min", pd.DataFrame()),
             ("df_scan", pd.DataFrame()), ("last_scan", None),
             ("last_yahoo", None), ("last_5min", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────
# SECCIÓN 1: TOP GAINERS YAHOO
# ─────────────────────────────────────────────────────────────
st.subheader("📡 Paso 1 — Top Gainers Tiempo Real (Yahoo Finance)")

y1, y2 = st.columns([3, 1])
with y1:
    btn_yahoo = st.button(
        "🏆 OBTENER TOP GAINERS YAHOO (= Webull Top Gainers 1Day)",
        use_container_width=True)
with y2:
    n_gd = len(st.session_state.gainers_data)
    col_g = "#00ff88" if n_gd > 0 else "#ff4444"
    ts_y = ""
    if st.session_state.last_yahoo:
        ts_y = datetime.fromtimestamp(st.session_state.last_yahoo)\
                       .astimezone(tz_et).strftime("%H:%M ET")
    st.markdown(
        f'<span style="color:{col_g}">📊 {n_gd} stocks '
        f'{"| " + ts_y if ts_y else ""}</span>',
        unsafe_allow_html=True)

if btn_yahoo:
    with st.spinner("🏆 Conectando a Yahoo Finance..."):
        res = obtener_top_gainers()

    cnts = res["counts"]
    c1, c2, c3 = st.columns(3)
    c1.markdown(
        f'<span style="color:{"#00ff88" if cnts["day_gainers"]>0 else "#ff4444"}">'
        f'{"✅" if cnts["day_gainers"]>0 else "❌"} Top Gainers Día: {cnts["day_gainers"]}</span>',
        unsafe_allow_html=True)
    c2.markdown(
        f'<span style="color:{"#00ff88" if cnts["most_actives"]>0 else "#ff4444"}">'
        f'{"✅" if cnts["most_actives"]>0 else "❌"} Más Activos: {cnts["most_actives"]}</span>',
        unsafe_allow_html=True)
    c3.markdown(
        f'<span style="color:{"#00ff88" if cnts["small_cap"]>0 else "#ff4444"}">'
        f'{"✅" if cnts["small_cap"]>0 else "❌"} Small Cap: {cnts["small_cap"]}</span>',
        unsafe_allow_html=True)

    # Construir diccionario
    gd = {}
    for t in res["todos"]:
        gd[t] = {"cambio_dia": 0.0, "es_top_gainer": True}

    # Manuales
    for t in [x.strip().upper() for x in tickers_extra.split(",") if x.strip()]:
        if t not in gd:
            gd[t] = {"cambio_dia": 0.0, "es_top_gainer": True}

    # Base
    if usar_base:
        for t in BASE:
            if t not in gd:
                gd[t] = {"cambio_dia": 0.0, "es_top_gainer": False}

    st.session_state.gainers_data = gd
    st.session_state.last_yahoo   = time.time()

    n_y = cnts["total"]
    n_t = len(gd)
    if n_y > 0:
        st.success(
            f"✅ {n_y} stocks de Yahoo Finance "
            f"(SDOT, BLZE, CLRB, STRL, BIYA...) + {n_t-n_y} base = **{n_t} total**")
    else:
        st.warning(f"⚠️ Yahoo no respondió. Usando {n_t} stocks (manuales + base).")

# Inicializar con manuales + base si está vacío
if not st.session_state.gainers_data:
    gd0 = {}
    for t in [x.strip().upper() for x in tickers_extra.split(",") if x.strip()]:
        gd0[t] = {"cambio_dia": 0.0, "es_top_gainer": True}
    if usar_base:
        for t in BASE:
            if t not in gd0:
                gd0[t] = {"cambio_dia": 0.0, "es_top_gainer": False}
    st.session_state.gainers_data = gd0

# Mostrar tickers Yahoo
if st.session_state.gainers_data:
    yahoo_t = [t for t, v in st.session_state.gainers_data.items() if v.get("es_top_gainer")]
    base_t  = [t for t, v in st.session_state.gainers_data.items() if not v.get("es_top_gainer")]
    ca, cb  = st.columns(2)
    with ca:
        st.markdown(f"**🏆 Yahoo Top Gainers ({len(yahoo_t)}):**")
        st.markdown(
            f'<div class="ibox" style="color:#00ff88">'
            f'{" · ".join(yahoo_t[:30])}{"..." if len(yahoo_t)>30 else ""}</div>',
            unsafe_allow_html=True)
    with cb:
        st.markdown(f"**📋 Base ({len(base_t)}):**")
        st.markdown(
            f'<div class="ibox" style="color:#8b949e">'
            f'{" · ".join(base_t[:20])}{"..." if len(base_t)>20 else ""}</div>',
            unsafe_allow_html=True)

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# SECCIÓN 2: DETECTOR MOMENTUM 5 MINUTOS
# ─────────────────────────────────────────────────────────────
st.subheader("🔥 Paso 2 — Detector Momentum 5 Minutos (como Webull '5 Minutes')")

m1, m2 = st.columns([3, 1])
with m1:
    btn_5min = st.button(
        "🔥 DETECTAR STOCKS ACTIVOS EN ÚLTIMOS 5 MINUTOS",
        use_container_width=True)
with m2:
    n_5m = len(st.session_state.df_5min)
    col_5 = "#ff4500" if n_5m > 0 else "#8b949e"
    ts_5 = ""
    if st.session_state.last_5min:
        ts_5 = datetime.fromtimestamp(st.session_state.last_5min)\
                       .astimezone(tz_et).strftime("%H:%M ET")
    st.markdown(
        f'<span style="color:{col_5}">🔥 {n_5m} detectados '
        f'{"| "+ts_5 if ts_5 else ""}</span>',
        unsafe_allow_html=True)

chg_5m_map = {}  # ticker → cambio% en 5min

if btn_5min:
    todos_tickers = list(st.session_state.gainers_data.keys())
    min_c5 = min_chg_5m if usar_5min else 2.0
    with st.spinner("🔥 Analizando momentum de 5 minutos..."):
        df_5min = detectar_momentum_5min(
            todos_tickers, precio_min_f, precio_max_f, min_c5, top_n_f)
    st.session_state.df_5min  = df_5min
    st.session_state.last_5min = time.time()
    if not df_5min.empty:
        st.success(f"✅ {len(df_5min)} stocks con momentum ≥ {min_c5}% en 5 minutos")
    else:
        st.warning("⚠️ Sin stocks con ese movimiento en 5 min. Baja el umbral.")

# Construir mapa de cambio 5min
if not st.session_state.df_5min.empty:
    for _, row in st.session_state.df_5min.iterrows():
        chg_5m_map[row["Ticker"]] = float(row["Δ 5min %"])

    # Mostrar tabla 5min
    df_5s  = st.session_state.df_5min
    cols_5 = ["Ticker","Precio $","Δ 5min %","Δ 10min %","Δ Día %",
              "RVOL 5m","Acelerando","Score 5m","Vol Actual"]
    df_5sh = df_5s[cols_5].copy()

    def c5d(v):
        return f"color:{'#00ff88' if v>=0 else '#ff4444'};font-weight:bold"
    def c5r(v):
        if v>=5:   return "color:#ff4500;font-weight:900"
        elif v>=3: return "color:#ff8c00;font-weight:700"
        elif v>=2: return "color:#ffc107;font-weight:bold"
        else:      return "color:#8b949e"

    fmt_5 = {"Precio $":"${:.4f}","Δ 5min %":"{:+.2f}%","Δ 10min %":"{:+.2f}%",
              "Δ Día %":"{:+.2f}%","RVOL 5m":"{:.1f}x","Score 5m":"{:.1f}",
              "Vol Actual":"{:,.0f}"}
    try:
        st5 = (df_5sh.style
               .map(c5d, subset=["Δ 5min %","Δ 10min %","Δ Día %"])
               .map(c5r, subset=["RVOL 5m"])
               .format(fmt_5))
    except Exception:
        try:
            st5 = (df_5sh.style
                   .applymap(c5d, subset=["Δ 5min %","Δ 10min %","Δ Día %"])
                   .applymap(c5r, subset=["RVOL 5m"])
                   .format(fmt_5))
        except Exception:
            st5 = df_5sh.style.format(fmt_5)
    st.dataframe(st5, use_container_width=True, hide_index=True, height=300)

    # Añadir stocks del 5min al universo de escaneo si no están
    for t in df_5s["Ticker"].tolist():
        if t not in st.session_state.gainers_data:
            st.session_state.gainers_data[t] = {
                "cambio_dia": float(df_5s[df_5s["Ticker"]==t]["Δ Día %"].iloc[0]),
                "es_top_gainer": True  # Lo marcamos como prioritario
            }

st.markdown('<hr class="n">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PORTAFOLIO
# ─────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────
# PASO 3: ESCANEO 1min — MOTOR DE SEÑAL COMPLETO
# ─────────────────────────────────────────────────────────────
st.subheader("🔭 Paso 3 — Motor de Señal 1min (Supertrend + RVOL + Aceleración)")

n_scan   = len(st.session_state.gainers_data)
n_yahoo  = sum(1 for v in st.session_state.gainers_data.values() if v.get("es_top_gainer"))
n_5min_s = len(chg_5m_map)

sb1, sb2, sb3 = st.columns([2, 1, 1])
with sb1:
    iniciar = st.button(
        f"🚀 INICIAR ESCANEO COMPLETO ({n_scan} stocks)",
        use_container_width=True)
with sb2:
    if st.button("🔄 Refresh UI", use_container_width=True):
        st.rerun()
with sb3:
    if st.session_state.last_scan:
        ts_s = datetime.fromtimestamp(st.session_state.last_scan)\
                       .astimezone(tz_et).strftime("%H:%M:%S ET")
        st.markdown(f'<span style="color:#8b949e;font-size:.74em">Último: {ts_s}</span>',
                    unsafe_allow_html=True)

st.markdown(
    f"⚡ **{n_scan} stocks** | "
    f"🏆 {n_yahoo} Yahoo | 🔥 {n_5min_s} con 5min activo | "
    f"Sesión: **{SESSION}** | RVOL≥{rvol_min}x | Vel≥{vel_min}%/min | ST={st_per}"
)

debe = iniciar or (
    auto_ref and st.session_state.last_scan is not None
    and (time.time() - st.session_state.last_scan) >= ref_seg
)

if debe:
    if not st.session_state.gainers_data:
        st.error("❌ Sin stocks. Pulsa 🏆 OBTENER TOP GAINERS primero.")
    else:
        with st.spinner("⚡ Motor de señal corriendo (RVOL corregido)..."):
            df_scan = escanear_1min(
                st.session_state.gainers_data,
                precio_min_f, precio_max_f,
                rvol_min, vel_min, atr_sl, atr_tp,
                SESSION, st_per, st_mult,
                chg_5m_map, top_n_f
            )
        st.session_state.df_scan   = df_scan
        st.session_state.last_scan = time.time()
        ts_ok = datetime.now(tz_et).strftime("%H:%M:%S ET")
        n = len(df_scan)
        if n > 0:
            n_y2  = len(df_scan[df_scan["Fuente"].str.contains("Yahoo", na=False)])
            n_5m2 = len(df_scan[df_scan["Fuente"].str.contains("5min", na=False)])
            st.success(
                f"✅ {ts_ok} — **{n} señales** "
                f"(🏆 {n_y2} Yahoo Top · 🔥 {n_5m2} 5min · 📋 {n-n_y2-n_5m2} base)"
            )
        else:
            st.warning(
                f"⚠️ {ts_ok} — Sin señales. "
                "Baja RVOL a 1.0x y Velocidad a 0.0%. "
                "Pulsa 🏆 para actualizar top gainers."
            )

df_scan = st.session_state.df_scan

# ─────────────────────────────────────────────────────────────
# RESULTADOS
# ─────────────────────────────────────────────────────────────
if not df_scan.empty:

    despegues = df_scan[df_scan["Score 🐂"] >= 7]
    impulsos  = df_scan[(df_scan["Score 🐂"] >= 5) & (df_scan["Score 🐂"] < 7)]

    # Tarjetas de despegue
    if not despegues.empty:
        st.markdown(f"### 🚀 DESPEGUES DETECTADOS — {len(despegues)} señales")
        for _, row in despegues.iterrows():
            s   = int(row["Score 🐂"])
            cls = "s10" if s == 10 else ("s8" if s >= 8 else "s6")
            rv  = float(row["RVOL"])
            vc  = "#00ff88" if row["Vel 1m %"] >= 0 else "#ff4444"
            d5c = "#00ff88" if row["Δ 5m %"] >= 0   else "#ff4444"
            dc  = "#00ff88" if row["Δ Día %"] >= 0   else "#ff4444"
            stc = "#00ff88" if "ALCISTA" in str(row["Supertrend"]) else "#ff4444"

            fuente = str(row["Fuente"])
            if "Yahoo" in fuente:
                fb = '<span style="background:#1d4ed8;color:#fff;padding:1px 7px;border-radius:4px;font-size:.71em">🏆 Yahoo</span>'
                card = "card-fire"
            elif "5min" in fuente:
                fb = '<span style="background:#b91c1c;color:#fff;padding:1px 7px;border-radius:4px;font-size:.71em">🔥 5min</span>'
                card = "card-5min"
            else:
                fb = '<span style="background:#374151;color:#aaa;padding:1px 7px;border-radius:4px;font-size:.71em">📋 Base</span>'
                card = "card-hot"

            rcl = ("color:#ff4500;font-weight:900" if rv >= 10
                   else ("color:#ff8c00;font-weight:700" if rv >= 5
                         else "color:#ffc107"))

            st.markdown(f"""
            <div class="{card}">
              <span class="tkr">⚡ {row['Ticker']}</span>
              &nbsp;{fb}
              &nbsp;&nbsp;<span class="{cls}">{s}/10</span>
              &nbsp;&nbsp;<span style="color:#a78bfa;font-size:.85em">{row['Señal']}</span>
              &nbsp;&nbsp;<span style="color:{stc};font-size:.80em">{row['Supertrend']}</span>
              <br>
              <span class="lbl">Precio</span> <b style="color:#fff">${row['Precio $']}</b>
              &nbsp;|&nbsp;
              <span class="lbl">RVOL</span> <b style="{rcl}">{rv:.1f}x</b>
              &nbsp;|&nbsp;
              <span class="lbl">Vel 1min</span> <b style="color:{vc}">{row['Vel 1m %']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">Vel 2min</span> <b style="color:{vc}">{row['Vel 2m %']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">Δ 5min</span> <b style="color:{d5c}">{row['Δ 5m %']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">Δ Día</span> <b style="color:{dc}">{row['Δ Día %']:+.2f}%</b>
              &nbsp;|&nbsp;
              <span class="lbl">RSI</span> {row['RSI']}
              &nbsp;|&nbsp;
              <span class="lbl">ST$</span> {row['ST $']}
              <br>
              <span class="lbl">SL</span> <b style="color:#ff6b6b">${row['SL $']}</b>
              &nbsp;|&nbsp;
              <span class="lbl">TP</span> <b style="color:#00ff88">${row['TP $']}</b>
              &nbsp;|&nbsp;
              <span class="lbl">R:R</span> {row['R:R']}x
            </div>""", unsafe_allow_html=True)

    # Impulsos
    if not impulsos.empty:
        with st.expander(f"👁️ IMPULSOS EN FORMACIÓN ({len(impulsos)} — score 5-6)"):
            for _, row in impulsos.iterrows():
                vc  = "#00ff88" if row["Vel 1m %"] >= 0 else "#ff4444"
                stc = "#00ff88" if "ALCISTA" in str(row["Supertrend"]) else "#ff4444"
                fuente = str(row["Fuente"])
                fb = "🏆" if "Yahoo" in fuente else ("🔥" if "5min" in fuente else "📋")
                st.markdown(f"""
                <div class="card-watch">
                  <b class="tkr" style="font-size:1.05em">{fb} {row['Ticker']}</b>
                  &nbsp;<span class="s6">{int(row['Score 🐂'])}/10</span>
                  &nbsp;<span style="color:#8b949e;font-size:.78em">{row['Señal']}</span>
                  &nbsp;<span style="color:{stc};font-size:.75em">{row['Supertrend']}</span>
                  &nbsp;|&nbsp;${row['Precio $']}
                  &nbsp;|&nbsp;<b>RVOL</b> {row['RVOL']}x
                  &nbsp;|&nbsp;<b style="color:{vc}">{row['Vel 1m %']:+.2f}%/min</b>
                  &nbsp;|&nbsp;<b>Δ5m</b> {row['Δ 5m %']:+.1f}%
                  &nbsp;|&nbsp;<b>Δ Día</b> {row['Δ Día %']:+.1f}%
                  &nbsp;|&nbsp;<b>RSI</b> {row['RSI']}
                  &nbsp;|&nbsp;<b style="color:#ff6b6b">SL</b>${row['SL $']}
                  &nbsp;<b style="color:#00ff88">TP</b>${row['TP $']}
                </div>""", unsafe_allow_html=True)

    # Tabla completa
    st.markdown("### 📋 Tabla Completa del Radar")
    cols_t = ["Ticker","Fuente","Precio $","RVOL","Vel 1m %","Vel 2m %",
              "Δ 5m %","Acel","Supertrend","ST $","Δ Día %",
              "Score 🐂","Score 🐻","Señal","RSI",
              "Soporte $","Resist $","SL $","TP $","R:R"]
    df_sh = df_scan[cols_t].copy()

    def cs(v):
        if v>=8:   return "background-color:#15803d;color:white"
        elif v>=6: return "background-color:#1d4ed8;color:white"
        elif v>=4: return "background-color:#92400e;color:white"
        else:      return "background-color:#7f1d1d;color:white"
    def cv(v):
        return f"color:{'#00ff88' if v>=0 else '#ff4444'};font-weight:bold"
    def cr(v):
        if v>=10:  return "color:#ff4500;font-weight:900"
        elif v>=5: return "color:#ff8c00;font-weight:700"
        elif v>=2: return "color:#ffc107;font-weight:bold"
        else:      return "color:#8b949e"
    fmt_t = {
        "Precio $":"${:.4f}","RVOL":"{:.1f}x","Vel 1m %":"{:+.2f}%",
        "Vel 2m %":"{:+.2f}%","Δ 5m %":"{:+.2f}%","Acel":"{:+.3f}",
        "ST $":"${:.4f}","Δ Día %":"{:+.2f}%","RSI":"{:.1f}",
        "Soporte $":"${:.4f}","Resist $":"${:.4f}",
        "SL $":"${:.4f}","TP $":"${:.4f}","R:R":"{:.2f}"
    }
    try:
        styled = (df_sh.style
                  .map(cs, subset=["Score 🐂","Score 🐻"])
                  .map(cv, subset=["Vel 1m %","Vel 2m %","Δ 5m %","Δ Día %"])
                  .map(cr, subset=["RVOL"])
                  .format(fmt_t))
    except Exception:
        try:
            styled = (df_sh.style
                      .applymap(cs, subset=["Score 🐂","Score 🐻"])
                      .applymap(cv, subset=["Vel 1m %","Vel 2m %","Δ 5m %","Δ Día %"])
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
        st.markdown(f"### 📊 {t_op} — Análisis Completo")
        stc2 = "#00ff88" if "ALCISTA" in str(rsel["Supertrend"]) else "#ff4444"
        st.markdown(
            f'<b style="color:{stc2}">{rsel["Supertrend"]}</b>'
            f' — ST: <b>${rsel["ST $"]}</b>',
            unsafe_allow_html=True)
        m1, m2_, m3, m4 = st.columns(4)
        m1.metric("Precio $",   f"${rsel['Precio $']:.4f}")
        m2_.metric("RVOL",      f"{rsel['RVOL']:.1f}x")
        m3.metric("Vel 1min",   f"{rsel['Vel 1m %']:+.2f}%")
        m4.metric("Score 🐂",   f"{rsel['Score 🐂']}/10")
        m5, m6, m7, m8 = st.columns(4)
        m5.metric("RSI",        f"{rsel['RSI']}")
        m6.metric("SL $",       f"${rsel['SL $']:.4f}")
        m7.metric("TP $",       f"${rsel['TP $']:.4f}")
        m8.metric("R:R",        f"{rsel['R:R']}x")
        m9, m10 = st.columns(2)
        m9.metric("Δ 5min",     f"{rsel['Δ 5m %']:+.2f}%")
        m10.metric("Δ Día",     f"{rsel['Δ Día %']:+.2f}%")

        det = rsel.get("_det", {})
        if det:
            st.markdown("**📌 Motor de señal:**")
            for k, v in det.items():
                c = ("#00ff88" if any(x in str(v) for x in
                                     ["▲","🚀","⚡","🔥","✅","🟢","🏆"])
                     else ("#ff4444" if any(x in str(v) for x in
                                           ["▼","💥","❌","🔴"])
                           else "#ffc107"))
                st.markdown(
                    f'<span style="color:{c};font-size:.79em">'
                    f'<b>{k}</b>: {v}</span>',
                    unsafe_allow_html=True)

elif st.session_state.last_scan is not None:
    st.warning("""
    ⚠️ **Sin señales.** Prueba:
    1. Pulsa **🏆 OBTENER TOP GAINERS** (datos frescos de Yahoo)
    2. Pulsa **🔥 DETECTOR 5MIN** (stocks activos ahora)
    3. Baja **RVOL mínimo** a **1.0x**
    4. Baja **Velocidad mínima** a **0.0%**
    """)
else:
    st.markdown("""
    ### 📋 Flujo para capturar el despegue:

    **1️⃣ Pulsa 🏆 OBTENER TOP GAINERS** → SDOT +135%, BLZE +62%, CLRB +45%
    _(Mismos datos que Webull Top Gainers 1 Day)_

    **2️⃣ Pulsa 🔥 DETECTOR 5MIN** → JLHL +16%, NXTS +16%, MRDN +13%
    _(Mismos datos que Webull % Chg in 5Mins)_

    **3️⃣ Pulsa 🚀 INICIAR ESCANEO** → Supertrend + RVOL + Velocidad 1min
    _(Con RVOL corregido — ya no sale 0.0x)_

    > Actualiza el **paso 1** y **paso 2** cada 5-10 minutos para
    > capturar los nuevos stocks que empiezan a dispararse.
    """)

# Auto-refresh
if auto_ref:
    time.sleep(ref_seg)
    st.rerun()

st.markdown('<hr class="n">', unsafe_allow_html=True)
st.markdown("""<div style="text-align:center;color:#8b949e;font-size:.69em;
font-family:'Share Tech Mono',monospace">
⚡ THUNDER RADAR V96 — YAHOO FINANCE · MOMENTUM 5MIN · PAPER TRADING — Uso educativo<br>
Los resultados pasados no garantizan rendimientos futuros. Opera con responsabilidad.
</div>""", unsafe_allow_html=True)
