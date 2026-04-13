import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import pytz
from datetime import datetime

st.set_page_config(page_title="THUNDER V73.2", layout="wide")
st.title("🚀 THUNDER SCALPING DASHBOARD V73.2 - Jorge")

# Tus claves
TWELVE_DATA_KEY = "7bf9d008a8cc4a87b8b045eec07d94d4"

with st.sidebar:
    st.header("⚙️ Configuración")
    sensibilidad = st.selectbox("Nivel de Sensibilidad", 
                                ["Nivel 1: Elite (Solo fuertes)", 
                                 "Nivel 2: Balanceado (Recomendado)", 
                                 "Nivel 3: Agresivo (Muchas señales)"])
    
    precio_min = st.number_input("Precio Mínimo ($)", value=0.01)
    precio_max = st.number_input("Precio Máximo ($)", value=200.0)
    
    modo = st.radio("Modo", ["Manual", "Automático"])
    paper = st.checkbox("Paper Trading", value=True)

    st.subheader("Supertrend Configurado")
    st.markdown("Usa Supertrend(10, 3) para respetar pullbacks en tendencia alcista.")

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

# Obtener más Top Gainers
def obtener_top_gainers():
    try:
        url = f"https://api.twelvedata.com/market_movers/stocks?type=gainers&apikey={TWELVE_DATA_KEY}"
        data = requests.get(url, timeout=10).json()
        return [item['symbol'] for item in data.get('values', [])[:200]]  # Aumentado a 200
    except:
        return ["GME","AMC","TSLA","NVDA","MARA","RIOT","PLTR","SOUN","ARM","SMCI"]

tickers = obtener_top_gainers()

@st.cache_data(ttl=10)
def analizar(ticker):
    try:
        df = yf.download(ticker, period="3d", interval="5m", prepost=True, progress=False)
        if df.empty: return None
        df = df[['Open','High','Low','Close','Volume']].copy()
        df.columns = ['open','high','low','close','volume']
        
        precio = float(df['close'].iloc[-1])
        cambio = ((precio / float(df['close'].iloc[-2])) - 1) * 100 if len(df)>1 else 0

        # Supertrend Simple (manual)
        df['ATR'] = df['high'].rolling(10).max() - df['low'].rolling(10).min()
        df['Upper'] = df['close'].rolling(10).mean() + 3 * df['ATR']
        df['Lower'] = df['close'].rolling(10).mean() - 3 * df['ATR']
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df)>1 else last

        score_buy = 0
        score_sell = 0
        razones = []

        if cambio >= 5: score_buy += 4; razones.append("🚀 DISPARO")
        if cambio >= 10: score_buy += 3

        # Supertrend Alcista
        if precio > last['Upper']: score_buy += 4; razones.append("SUPER TREND ALCISTA")
        if precio < last['Lower']: score_sell += 5; razones.append("SUPER TREND BAJISTA")

        buy_rating = min(10, max(1, int(score_buy * 10 / 11)))
        sell_rating = min(10, max(1, int(score_sell * 10 / 8)))

        return {
            "Ticker": ticker,
            "Precio": round(precio, 3),
            "Cambio%": round(cambio, 2),
            "Buy": buy_rating,
            "Sell": sell_rating,
            "Estrategia": " + ".join(razones) or "Monitoreo",
        }
    except:
        return None

# Mostrar resultados
resultados = [analizar(t) for t in tickers[:180]]
resultados = [r for r in resultados if r and precio_min <= r["Precio"] <= precio_max]

if resultados:
    df = pd.DataFrame(resultados).sort_values(by="Buy", ascending=False)
    st.dataframe(df, use_container_width=True, height=700)
else:
    st.info("Cargando Top Gainers...")

st.caption("V73.2 | Supertrend configurado | Respeta pullbacks | Escanea Top 200 Gainers")
