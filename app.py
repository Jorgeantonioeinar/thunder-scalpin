import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import pytz
from datetime import datetime

st.set_page_config(page_title="THUNDER V73.1", layout="wide")
st.title("🚀 THUNDER SCALPING DASHBOARD V73.1 - Jorge")

# ==================== TUS CLAVES ====================
TWELVE_DATA_KEY = "7bf9d008a8cc4a87b8b045eec07d94d4"
ALPACA_API_KEY = "PKOKUMRZBCA2YJKVZIATSPGV5J"
ALPACA_SECRET_KEY = "2UBriZpW7NooR1EvtowC63GcarFt7rEQFD9ofti9Ah6N"

# ==================== CONFIGURACIÓN ====================
with st.sidebar:
    st.header("⚙️ Configuración")
    sensibilidad = st.selectbox("Nivel de Sensibilidad", 
                                ["Nivel 1: Elite (Solo disparos fuertes)", 
                                 "Nivel 2: Balanceado (Recomendado)", 
                                 "Nivel 3: Agresivo (Más señales)"])
    
    precio_min = st.number_input("Precio Mínimo ($)", value=0.01, step=0.01)
    precio_max = st.number_input("Precio Máximo ($)", value=200.0, step=1.0)
    
    modo = st.radio("Modo de Operación", ["Manual", "Automático"])
    paper_trading = st.checkbox("Paper Trading (Recomendado)", value=True)

    st.subheader("📘 Cómo funciona")
    st.markdown("""
    - **Buy Rating 8-10** → Disparo fuerte → Buen momento para comprar  
    - **Sell Rating 8-10** → Cambio real de tendencia → Vender  
    - Pequeñas bajadas **NO** activan venta mientras siga alcista
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
st.subheader(f"🕒 NY: **{ny_time}** | Sesión: **{session}**")

if st.button("🔄 Actualizar Datos"):
    st.rerun()

# Obtener Top Gainers
def obtener_top_gainers():
    try:
        url = f"https://api.twelvedata.com/market_movers/stocks?type=gainers&apikey={TWELVE_DATA_KEY}"
        data = requests.get(url, timeout=10).json()
        return [item['symbol'] for item in data.get('values', [])[:100]]
    except:
        return ["MNDR","NVVE","FFIE","GME","AMC","MARA","RIOT","TSLA","PLTR","SOUN","SERV","HOLO","KTRA","PEGY",
                "SAVA","NVAX","CRSP","HOOD","COIN","RIVN","LCID","ARM","SMCI","AMD","NVDA"]

tickers = obtener_top_gainers()

# Análisis principal
@st.cache_data(ttl=10)
def analizar(ticker):
    try:
        df = yf.download(ticker, period="3d", interval="5m", prepost=True, progress=False)
        if df.empty: return None
        df = df[['Open','High','Low','Close','Volume']].copy()
        df.columns = ['open','high','low','close','volume']
        
        precio = float(df['close'].iloc[-1])
        vol = int(df['volume'].iloc[-1])
        cambio = ((precio / float(df['close'].iloc[-2])) - 1) * 100 if len(df)>1 else 0

        # EMA simples
        df['EMA9'] = df['close'].ewm(span=9).mean()
        df['EMA20'] = df['close'].ewm(span=20).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df)>1 else last

        score_buy = 0
        score_sell = 0
        razones = []

        # Momentum fuerte
        if cambio >= 8: score_buy += 5; razones.append("🚀 MOMENTUM FUERTE")
        elif cambio >= 5: score_buy += 3; razones.append("🔥 MOMENTUM")

        # Gap & Go
        if len(df) > 25:
            gap = (precio - float(df['close'].iloc[-25])) / float(df['close'].iloc[-25]) * 100
            if gap > 4: score_buy += 4; razones.append("GAP & GO")

        # Tendencia Alcista
        if last['close'] > last['EMA9'] > last['EMA20']: score_buy += 4

        # Volumen
        avg_vol = df['volume'].tail(20).mean()
        if vol > avg_vol * 1.8: score_buy += 3; razones.append("VOLUME SURGE")

        # Para venta (cambio de tendencia)
        if last['close'] < last['EMA9'] and prev['close'] > prev['EMA9']:
            score_sell += 6

        buy_rating = min(10, max(1, int(score_buy * 10 / 16)))
        sell_rating = min(10, max(1, int(score_sell * 10 / 8)))

        return {
            "Ticker": ticker,
            "Precio": round(precio, 3),
            "Cambio%": round(cambio, 2),
            "Buy Rating": buy_rating,
            "Sell Rating": sell_rating,
            "Estrategia": " + ".join(razones) or "Monitoreo",
            "Vol": f"{vol:,}"
        }
    except:
        return None

# ==================== MOSTRAR RESULTADOS ====================
resultados = []
for t in tickers[:150]:
    res = analizar(t)
    if res and precio_min <= res["Precio"] <= precio_max:
        resultados.append(res)

if resultados:
    df = pd.DataFrame(resultados).sort_values(by="Buy Rating", ascending=False)
    st.dataframe(df, use_container_width=True, height=700)
else:
    st.info("Cargando Top Gainers y buscando disparos...")

st.caption("V73.1 | Detecta subidas fuertes (5%+) | Respeta pullbacks en tendencia alcista | Paper Trading recomendado")
