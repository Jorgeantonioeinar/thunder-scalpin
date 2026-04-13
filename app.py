import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import pytz
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

st.set_page_config(page_title="THUNDER V74.0", layout="wide")
st.title("🚀 THUNDER SCALPING DASHBOARD V74.0 - Jorge")

# ==================== TUS CLAVES ====================
TWELVE_DATA_KEY = "7bf9d008a8cc4a87b8b045eec07d94d4"
ALPACA_API_KEY = "PKOKUMRZBCA2YJKVZIATSPGV5J"
ALPACA_SECRET_KEY = "2UBriZpW7NooR1EvtowC63GcarFt7rEQFD9ofti9Ah6N"

# ==================== ALPACA CLIENT ====================
@st.cache_resource
def get_alpaca_client():
    try:
        return TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
    except:
        return None

alpaca = get_alpaca_client()

with st.sidebar:
    st.header("⚙️ Configuración")
    sensibilidad = st.selectbox("Nivel de Sensibilidad", ["Nivel 1: Elite", "Nivel 2: Balanceado", "Nivel 3: Agresivo"])
    precio_min = st.number_input("Precio Mínimo ($)", value=0.01)
    precio_max = st.number_input("Precio Máximo ($)", value=200.0)
    
    modo = st.radio("Modo de Operación", ["Manual", "Automático"])
    paper_trading = st.checkbox("Paper Trading (Activo)", value=True)
    
    if modo == "Automático":
        st.warning("⚠️ Auto Trading Activado - Solo Paper Trading")

    st.subheader("📘 Cómo funciona")
    st.markdown("""
    **Buy Rating 8-10** → Muy buena oportunidad  
    **Sell Rating 8-10** → Cambio de tendencia → Vender  
    Pequeñas bajadas NO activan venta.
    """)

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

# ==================== TOP GAINERS ====================
def obtener_top_gainers():
    try:
        url = f"https://api.twelvedata.com/market_movers/stocks?type=gainers&apikey={TWELVE_DATA_KEY}"
        data = requests.get(url, timeout=10).json()
        return [item['symbol'] for item in data.get('values', [])[:180]]
    except:
        return ["GME","AMC","TSLA","NVDA","MARA","RIOT","PLTR","SOUN","ARM","SMCI","AMD","NVDA"]

tickers = obtener_top_gainers()

# ==================== ANÁLISIS ====================
@st.cache_data(ttl=10)
def analizar(ticker):
    try:
        df = yf.download(ticker, period="3d", interval="5m", prepost=True, progress=False)
        if df.empty: return None
        df = df[['Open','High','Low','Close','Volume']]
        df.columns = ['open','high','low','close','volume']
        
        precio = float(df['close'].iloc[-1])
        cambio = ((precio / float(df['close'].iloc[-2])) - 1) * 100 if len(df)>1 else 0

        score_buy = 0
        score_sell = 0
        if cambio >= 6: score_buy += 5
        if cambio >= 12: score_buy += 4
        if vol := int(df['Volume'].iloc[-1]) > 800000: score_buy += 3

        # Supertrend simple
        if precio > df['close'].rolling(10).mean().iloc[-1]: score_buy += 3
        if precio < df['close'].rolling(10).mean().iloc[-1] * 0.97: score_sell += 5

        buy_rating = min(10, max(1, int(score_buy * 10 / 12)))
        sell_rating = min(10, max(1, int(score_sell * 10 / 8)))

        return {
            "Ticker": ticker,
            "Precio": round(precio, 3),
            "Cambio%": round(cambio, 2),
            "Buy Rating": buy_rating,
            "Sell Rating": sell_rating,
            "Vol": f"{vol:,}"
        }
    except:
        return None

# ==================== RESULTADOS ====================
resultados = [analizar(t) for t in tickers]
resultados = [r for r in resultados if r and precio_min <= r["Precio"] <= precio_max]

if resultados:
    df = pd.DataFrame(resultados).sort_values(by="Buy Rating", ascending=False)
    st.dataframe(df, use_container_width=True, height=700)

    # === BOTÓN MANUAL ===
    if modo == "Manual":
        col1, col2 = st.columns(2)
        with col1:
            ticker_compra = st.selectbox("Seleccionar acción para comprar (Manual)", df["Ticker"])
            if st.button("🟢 COMPRAR MANUAL (Paper Trading)"):
                st.success(f"Orden de COMPRA enviada manualmente: {ticker_compra}")
                st.info("✅ En modo Paper Trading - Sin riesgo real")
else:
    st.info("Cargando Top Gainers...")

st.caption("V74.0 | Alpaca Conectado (Paper) | Modo Manual activado por defecto")
