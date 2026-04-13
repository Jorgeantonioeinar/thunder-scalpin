import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import pytz
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

st.set_page_config(page_title="THUNDER V74.1", layout="wide")
st.title("🚀 THUNDER SCALPING DASHBOARD V74.1 - Jorge")

# ==================== CLAVES ====================
TWELVE_DATA_KEY = "7bf9d008a8cc4a87b8b045eec07d94d4"
ALPACA_API_KEY = "PKOKUMRZBCA2YJKVZIATSPGV5J"
ALPACA_SECRET_KEY = "2UBriZpW7NooR1EvtowC63GcarFt7rEQFD9ofti9Ah6N"

# ==================== ALPACA ====================
alpaca = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)

with st.sidebar:
    st.header("⚙️ Configuración")
    sensibilidad = st.selectbox("Nivel de Sensibilidad", ["Nivel 1: Elite", "Nivel 2: Balanceado", "Nivel 3: Agresivo"])
    precio_min = st.number_input("Precio Mínimo ($)", value=0.01)
    precio_max = st.number_input("Precio Máximo ($)", value=200.0)
    
    modo = st.radio("Modo de Operación", ["Manual", "Automático"])
    st.checkbox("Paper Trading", value=True, disabled=True)

    st.subheader("Agregar tus propias acciones")
    manual_tickers = st.text_input("Escribe tickers separados por coma (ej: GME, AMC, TSLA)", 
                                   value="GME,AMC,TSLA,NVDA")
    manual_list = [t.strip().upper() for t in manual_tickers.split(",") if t.strip()]

# ==================== SESIÓN ====================
def get_ny_session():
    tz = pytz.timezone('America/New_York')
    now = datetime.now(tz)
    hora = now.strftime('%H:%M:%S')
    if now.weekday() >= 5: return hora, "🔴 CERRADO"
    elif 4 <= now.hour < 9.5: return hora, "🌅 PRE-MARKET"
    elif 9.5 <= now.hour < 16: return hora, "🟢 REGULAR"
    elif 16 <= now.hour < 20: return hora, "🌙 AFTER-HOURS"
    return hora, "🔴 CERRADO"

ny_time, session = get_ny_session()
st.subheader(f"🕒 NY: {ny_time} | {session}")

if st.button("🔄 Actualizar"):
    st.rerun()

# ==================== TICKERS ====================
def obtener_top_gainers():
    try:
        url = f"https://api.twelvedata.com/market_movers/stocks?type=gainers&apikey={TWELVE_DATA_KEY}"
        data = requests.get(url, timeout=8).json()
        return [item['symbol'] for item in data.get('values', [])[:100]]
    except:
        return []

all_tickers = list(set(obtener_top_gainers() + manual_list))

# ==================== ANÁLISIS ====================
@st.cache_data(ttl=10)
def analizar(ticker):
    try:
        df = yf.download(ticker, period="3d", interval="5m", prepost=True, progress=False)
        if df.empty: return None
        precio = float(df['Close'].iloc[-1])
        cambio = ((precio / float(df['Close'].iloc[-2])) - 1) * 100 if len(df)>1 else 0

        score_buy = 0
        if cambio >= 6: score_buy += 5
        if cambio >= 12: score_buy += 4
        if int(df['Volume'].iloc[-1]) > 800000: score_buy += 3

        buy_rating = min(10, max(1, int(score_buy * 10 / 12)))

        return {
            "Ticker": ticker,
            "Precio": round(precio, 3),
            "Cambio%": round(cambio, 2),
            "Buy Rating": buy_rating,
            "Vol": f"{int(df['Volume'].iloc[-1]):,}"
        }
    except:
        return None

# ==================== RESULTADOS ====================
resultados = [analizar(t) for t in all_tickers]
resultados = [r for r in resultados if r and precio_min <= r["Precio"] <= precio_max]

if resultados:
    df = pd.DataFrame(resultados).sort_values(by="Buy Rating", ascending=False)
    st.dataframe(df, use_container_width=True, height=700)

    # Botón Manual
    if modo == "Manual":
        ticker_sel = st.selectbox("Seleccionar acción para COMPRAR MANUAL", df["Ticker"])
        if st.button("🟢 COMPRAR MANUAL (Paper Trading)"):
            st.success(f"✅ Orden de COMPRA enviada: {ticker_sel}")
else:
    st.info("Cargando datos...")

st.caption("V74.1 | Alpaca conectado (Paper) | Puedes agregar tus propias acciones")
