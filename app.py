import streamlit as st
import pandas as pd
import yfinance as yf
import pytz
from datetime import datetime

st.set_page_config(page_title="THUNDER V72", layout="wide")
st.title("🚀 THUNDER SCALPING DASHBOARD V72.0 - Jorge")

with st.sidebar:
    st.header("⚙️ Configuración")
    max_activos = st.slider("Máximo de acciones", 50, 300, 150)
    modo = st.radio("Modo", ["Manual", "Automático"])
    paper = st.checkbox("Paper Trading", value=True)

    st.subheader("📘 Estrategias")
    st.markdown("""
    🔥 **GAP & GO** → Gap alcista + volumen  
    📈 **EMA Crossover** → EMA9 cruza EMA20  
    🚀 **Momentum fuerte** → Cambio rápido de precio
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

tickers = ["MNDR","NVVE","FFIE","GME","AMC","MARA","RIOT","TSLA","PLTR","SOUN","SERV","HOLO","KTRA","PEGY",
           "SAVA","NVAX","CRSP","HOOD","COIN","RIVN","LCID","ARM","SMCI","AMD","NVDA"]

data = []
for ticker in tickers[:max_activos]:
    try:
        df = yf.download(ticker, period="5d", interval="5m", prepost=True, progress=False)
        if df.empty: continue
        precio = float(df['Close'].iloc[-1])
        cambio = ((precio / float(df['Close'].iloc[-2])) - 1) * 100 if len(df)>1 else 0
        
        data.append({
            "Ticker": ticker,
            "Precio": round(precio, 2),
            "Cambio%": round(cambio, 2),
            "Buy Rating": "7/10" if cambio > 2 else "5/10"
        })
    except:
        pass

if data:
    df_final = pd.DataFrame(data).sort_values(by="Cambio%", ascending=False)
    st.dataframe(df_final, use_container_width=True, height=600)
else:
    st.info("Cargando datos...")

st.caption("✅ Versión estable sin pandas_ta | Usa Paper Trading primero")
