import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import pytz
from datetime import datetime
import requests
import os

st.set_page_config(page_title="THUNDER V71", layout="wide")
st.title("🚀 THUNDER SCALPING DASHBOARD V71.0 - Jorge")

# TUS CLAVES (ya están puestas)
TWELVE_DATA_KEY = "7bf9d008a8cc4a87b8b045eec07d94d4"
ALPACA_API_KEY = "PKOKUMRZBCA2YJKVZIATSPGV5J"
ALPACA_SECRET_KEY = "2UBriZpW7NooR1EvtowC63GcarFt7rEQFD9ofti9Ah6N"

with st.sidebar:
    st.header("⚙️ Configuración")
    max_activos = st.slider("Máximo de acciones a escanear", 50, 300, 150)
    modo = st.radio("Modo de Operación", ["Manual", "Automático"])
    paper_trading = st.checkbox("Paper Trading (Recomendado)", value=True)

    st.subheader("📘 Estrategias Explicadas")
    st.markdown("""
    **🔥 GAP & GO** → Abre con gap fuerte + volumen alto (ideal pre-market).  
    **📈 EMA Crossover** → EMA9 cruza por encima de EMA20.  
    **🚀 SUPERFLIP** → Supertrend cambia a alcista.  
    **VWAP Anchor** → Precio por encima del VWAP.
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

@st.cache_data(ttl=10)
def analizar(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="5m", prepost=True, progress=False)
        if df.empty: return None
        df = df[['Open','High','Low','Close','Volume']]
        df.columns = ['open','high','low','close','volume']
        
        precio = float(df['close'].iloc[-1])
        vol = int(df['volume'].iloc[-1])
        cambio = ((precio / float(df['close'].iloc[-2])) - 1) * 100 if len(df)>1 else 0

        df['EMA9'] = ta.ema(df['close'],9)
        df['EMA20'] = ta.ema(df['close'],20)
        df['RSI'] = ta.rsi(df['close'],14)
        df['VWAP'] = ta.vwap(df['high'],df['low'],df['close'],df['volume'])
        super_df = ta.supertrend(df['high'],df['low'],df['close'],10,3)
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df)>1 else last

        score = 0
        strat = []

        if len(df) > 30:
            gap = (precio - float(df['close'].iloc[-30])) / float(df['close'].iloc[-30]) * 100
            if gap > 3 and vol > df['volume'].tail(20).mean() * 1.7:
                score += 5
                strat.append("🔥 GAP & GO")

        if last['EMA9'] > last['EMA20'] and prev['EMA9'] <= prev['EMA20']:
            score += 4
            strat.append("📈 EMA CROSS")

        if last.get('SUPERTd_10_3.0', 0) == 1 and prev.get('SUPERTd_10_3.0', 0) == -1:
            score += 5
            strat.append("🚀 SUPERFLIP")

        buy_rating = min(10, max(1, int(score * 10 / 18)))

        return {
            "Ticker": ticker,
            "Precio": round(precio,2),
            "Cambio%": round(cambio,2),
            "Buy Rating": buy_rating,
            "Estrategia": " + ".join(strat) or "Base",
            "RSI": round(last['RSI'],1)
        }
    except:
        return None

ny_time, session = get_ny_session()
st.subheader(f"🕒 Nueva York: {ny_time} | Sesión: {session}")

if st.button("🔄 Actualizar Datos"):
    st.rerun()

tickers = ["MNDR","NVVE","FFIE","GME","AMC","MARA","RIOT","TSLA","PLTR","SOUN","SERV","HOLO","KTRA","PEGY",
           "SAVA","NVAX","CRSP","HOOD","COIN","RIVN","LCID","ARM","SMCI","AMD","NVDA"]

resultados = [analizar(t) for t in tickers[:max_activos]]
resultados = [r for r in resultados if r]

if resultados:
    df = pd.DataFrame(resultados).sort_values(by="Buy Rating", ascending=False)
    st.dataframe(df, use_container_width=True, height=600)
else:
    st.info("Esperando señales...")

st.caption("✅ Programa listo. Usa primero Paper Trading.")
