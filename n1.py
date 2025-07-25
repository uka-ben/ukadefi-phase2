import streamlit as st
import numpy as np 
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import requests
from scipy.signal import argrelextrema
import time  
from datetime import datetime
import brotli
import threading
import queue
import json
from PIL import Image
import io
import base64

# Configure page layout and style
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background: linear-gradient(pink,skyblue, white);
    color: black;
}
[data-testid="stSidebar"] {
    background: linear-gradient(skyblue, white) !important;
    color: black;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: black;
}
footer {
    visibility: hidden;
}
header {
    visibility: hidden;
}
body {
    font-family: "Source Sans Pro", sans-serif;
}
.stButton>button {
    background-color: blue;
    color: white;
    font-size: 16px;
    border-radius: 8px;
    padding: 10px 24px;
    border: none;
    cursor: pointer;
    transition: background-color 0.3s ease;
}
.stButton>button:hover {
    background-color: #45a804;
}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    color: #2c3e50;
}
.stDataFrame {
    border-radius: 8px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}
.stProgress > div > div > div {
    background-color: #4CAF50;
}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

# API Configuration
api_key = "cef197ce3e054ee69d6c795401b229cd"

# Compression helper functions
def compress_data(data):
    if isinstance(data, (pd.DataFrame, pd.Series)):
        data = data.to_json(orient='split')
    return brotli.compress(json.dumps(data).encode('utf-8'))

def decompress_data(compressed_data):
    return json.loads(brotli.decompress(compressed_data).decode('utf-8'))

def compress_image(fig, quality=30):
    png_buf = io.BytesIO()
    fig.savefig(png_buf, format='png', dpi=25)
    png_buf.seek(0)
    img = Image.open(png_buf)
    webp_buf = io.BytesIO()
    img.save(webp_buf, format='webp', quality=quality)
    webp_buf.seek(0)
    return webp_buf

# Sound alert function
def play_alert_sound(alert_type="neutral"):
    sound_url = {
        "bullish": "https://github.com/uka-ben/Sounder/raw/c2b3f81a8b704924eeb69efa668f805576740e34/alert1.wav",
        "bearish": "https://github.com/uka-ben/Sounder/raw/c2b3f81a8b704924eeb69efa668f805576740e34/alert1.wav",
        "neutral": "https://github.com/uka-ben/Sounder/raw/c2b3f81a8b704924eeb69efa668f805576740e34/alert1.wav"
    }.get(alert_type.lower(), "https://github.com/uka-ben/Sounder/raw/c2b3f81a8b704924eeb69efa668f805576740e34/alert1.wav")

    audio_html = f"""
    <audio autoplay>
        <source src="{sound_url}?v={time.time()}" type="audio/wav">
    </audio>
    """
    st.components.v1.html(audio_html, height=0)

# ======== NEW INDICATOR FUNCTIONS ========
def td_sequential(close, lookback=9):
    """DeMark Sequential (TD Setup)"""
    td_setup = np.zeros(len(close))
    for i in range(lookback, len(close)):
        if all(close[i] > close[i-j-4] for j in range(lookback)):
            td_setup[i] = 1  # Bullish Setup
        elif all(close[i] < close[i-j-4] for j in range(lookback)):
            td_setup[i] = -1  # Bearish Setup
    return pd.Series(td_setup, index=close.index)

def ehlers_cyber_cycle(price, alpha=0.07):
    """Ehlers Adaptive Cyber Cycle (Smoothed)"""
    smooth = (price + 2*price.shift(1) + 2*price.shift(2) + price.shift(3)) / 6
    cycle = np.zeros(len(price))
    for i in range(2, len(price)):
        cycle[i] = (1 - 0.5*alpha)**2 * (smooth[i] - 2*smooth[i-1] + smooth[i-2]) + 2*(1-alpha)*cycle[i-1] - (1-alpha)**2 * cycle[i-2]
    return pd.Series(cycle, index=price.index)

def supertrend(df, period=10, multiplier=3):
    """SuperTrend (Trend-Following)"""
    hl2 = (df['High'] + df['Low']) / 2
    atr = df['High'].rolling(period).max() - df['Low'].rolling(period).min()
    upper = hl2 + (multiplier * atr)
    lower = hl2 - (multiplier * atr)
    return pd.DataFrame({'Upper': upper, 'Lower': lower}, index=df.index)

def williams_r(high, low, close, lookback=14):
    """Williams %R (Momentum Oscillator)"""
    highest_high = high.rolling(lookback).max()
    lowest_low = low.rolling(lookback).min()
    return pd.Series(-100 * (highest_high - close) / (highest_high - lowest_low), index=close.index)

# Original indicator functions
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def compute_macd(data, short=12, long=26, signal=9):
    macd_line = data['Close'].ewm(span=short, adjust=False).mean() - data['Close'].ewm(span=long, adjust=False).mean()
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def compute_kdj(data, window=14, smooth=3):
    low_min = data['Low'].rolling(window=window).min()
    high_max = data['High'].rolling(window=window).max()
    k = 100 * ((data['Close'] - low_min) / (high_max - low_min))
    d = k.rolling(window=smooth).mean()
    j = 3 * k - 2 * d
    return k, d, j

def compute_cci(data, window=30):
    tp = (data['High'] + data['Low'] + data['Close']) / 3
    sma = tp.rolling(window=window).mean()
    mad = tp.rolling(window=window).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
    cci = (tp - sma) / (0.015 * mad)
    return cci

def compute_bias_indicator(data):
    rsi_bias = (data['RSI_14'] - 50) / 50
    macd_bias = data['MACD'] / (2 * data['MACD'].std())
    cci_bias = data['CCI'] / 200
    bias = 0.4 * rsi_bias + 0.3 * macd_bias + 0.3 * cci_bias
    bias_smoothed = bias.ewm(span=5, adjust=False).mean()
    return bias, bias_smoothed

def compute_inertia_indicator(data, period=30, smooth=10):
    numerator = (data['Close'] - data['Open']).rolling(window=period).mean()
    denominator = (data['High'] - data['Low']).rolling(window=period).mean()
    rvi = numerator / denominator
    price_changes = data['Close'].diff()
    std_dev = price_changes.rolling(window=period).std()
    inertia = rvi * std_dev
    inertia_smoothed = inertia.ewm(span=smooth, adjust=False).mean()
    return inertia, inertia_smoothed

def find_extrema(series, order=70):
    maxima = argrelextrema(series.values, np.greater, order=order)[0]
    minima = argrelextrema(series.values, np.less, order=order)[0]
    return maxima, minima

# Data loading functions
@st.cache_data(ttl=60, show_spinner="Fetching market data...")
def load_initial_data(symbol, interval, lookback, api_key):
    try:
        url = f"https://api.twelvedata.com/time_series?apikey={api_key}&interval={interval}&symbol={symbol}/USD&type=etf&timezone=Africa/Lagos&outputsize={lookback}"
        headers = {'Accept-Encoding': 'br'}
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            st.error(f"API Error: {response.status_code}")
            return pd.DataFrame()

        data = response.json()

        if 'values' not in data:
            st.error(f"API Error: {data.get('message', 'Unknown error')}")
            return pd.DataFrame()

        df = pd.DataFrame(data['values'])
        df = df.rename(columns={
            'datetime': 'Date', 
            'open': 'Open', 
            'close': 'Close',
            'high': 'High', 
            'low': 'Low',
            'volume': 'Volume'
        })

        df['Date'] = pd.to_datetime(df['Date'])
        numeric_cols = df.columns.drop('Date')
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        df = df.sort_values('Date').reset_index(drop=True)
        df = df.iloc[-lookback:]
        df.index = df['Date']
        return df

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

def update_data_with_sse(prev_data, new_data_point):
    if prev_data is None or prev_data.empty:
        return pd.DataFrame()

    new_row = pd.DataFrame([{
        'Date': pd.to_datetime(new_data_point['timestamp']),
        'Open': float(new_data_point['open']),
        'High': float(new_data_point['high']),
        'Low': float(new_data_point['low']),
        'Close': float(new_data_point['close']),
        'Volume': float(new_data_point.get('volume', 0))
    }])

    updated = pd.concat([prev_data, new_row]).drop_duplicates(subset=['Date'], keep='last')

    if len(updated) > lookback:
        updated = updated.iloc[-lookback:]

    updated.index = updated['Date']
    return updated

def check_for_new_signals(current_signals):
    new_signals = {}
    for signal_type in current_signals:
        previous = st.session_state.previous_signals.get(signal_type, [])
        current = current_signals.get(signal_type, [])

        new = [s for s in current if s not in previous]
        if new:
            new_signals[signal_type] = new

    return new_signals

def trigger_alert(alert_type, price, timestamp):
    if alert_type == "Bullish Divergence":
        st.toast(f"🚨 BULLISH at {price:.4f}", icon="📈")
        st.sidebar.success(f"Bullish at {price:.4f}")
    elif alert_type == "Bearish Divergence":
        st.toast(f"🚨 BEARISH at {price:.4f}", icon="📉")
        st.sidebar.error(f"Bearish at {price:.4f}")
    elif alert_type == "RSI Crossover":
        st.toast(f"⚠️ New strength at {price:.4f}", icon="🔔")
        st.sidebar.warning(f"RSI crossover at {price:.4f}")

    if alert_sound:
        sound_type = "bullish" if "Bullish" in alert_type else "bearish" if "Bearish" in alert_type else "neutral"
        play_alert_sound(sound_type)

    st.session_state.alert_history.append({
        "timestamp": timestamp,
        "type": alert_type,
        "price": price,
        "symbol": symbol
    })

    st.session_state.alert_history = st.session_state.alert_history[-50:]

def create_plot(data, symbol, interval, market_type):
    # Create figure with 5 subplots
    fig = Figure(figsize=(35, 25), dpi=40)
    gs = fig.add_gridspec(5, 1, height_ratios=[12, 5, 5, 5, 5])

    axes = [fig.add_subplot(gs[0])]  # Price chart
    axes.append(fig.add_subplot(gs[1], sharex=axes[0]))  # Williams %R
    axes.append(fig.add_subplot(gs[2], sharex=axes[0]))  # Cyber Cycle
    axes.append(fig.add_subplot(gs[3], sharex=axes[0]))  # SuperTrend
    axes.append(fig.add_subplot(gs[4], sharex=axes[0]))  # TD Sequential

    # === 1. PRICE CHART ===
    current_price = data['Close'].iloc[-1]
    axes[0].plot(data.index, data['Close'], color='blue', linewidth=3, alpha=0.8)
    axes[0].plot(data.index, data['Upper'], color='red', linestyle='--', alpha=0.7, label='SuperTrend Upper')
    axes[0].plot(data.index, data['Lower'], color='green', linestyle='--', alpha=0.7, label='SuperTrend Lower')
    axes[0].axhline(y=current_price, color='black', linestyle=':', alpha=0.7)
    axes[0].set_title(f'{market_type}: {symbol} ({interval})', fontsize=20)
    axes[0].legend()

    # === 2. WILLIAMS %R ===
    axes[1].plot(data.index, data['Williams_%R'], color='purple', linewidth=2)
    axes[1].axhline(-80, color='green', linestyle='--', alpha=0.7, label='Oversold')
    axes[1].axhline(-20, color='red', linestyle='--', alpha=0.7, label='Overbought')
    axes[1].set_title('Williams %R (Overbought/Oversold)', fontsize=16)
    axes[1].legend()

    # === 3. CYBER CYCLE ===
    axes[2].plot(data.index, data['Cyber_Cycle'], color='orange', linewidth=2)
    axes[2].axhline(0, color='black', linestyle='-', alpha=0.5)
    axes[2].set_title('Ehlers Cyber Cycle', fontsize=16)

    # === 4. SUPER TREND ===
    axes[3].plot(data.index, data['Upper'], color='red', label='Resistance')
    axes[3].plot(data.index, data['Lower'], color='green', label='Support')
    axes[3].set_title('SuperTrend Zones', fontsize=16)
    axes[3].legend()

    # === 5. TD SEQUENTIAL ===
    axes[4].scatter(data.index[data['TD_Sequential'] == 1], 
                   data['Close'][data['TD_Sequential'] == 1], 
                   color='green', marker='^', s=100, label='Bullish Setup')
    axes[4].scatter(data.index[data['TD_Sequential'] == -1], 
                   data['Close'][data['TD_Sequential'] == -1], 
                   color='red', marker='v', s=100, label='Bearish Setup')
    axes[4].set_title('DeMark Sequential (Reversals)', fontsize=16)
    axes[4].legend()

    # Format all axes
    for ax in axes:
        ax.grid(True, linestyle='--', alpha=0.6)

    return compress_image(fig)

def swing_3(data):
    if data.empty:
        return plt.figure(), {}

    data = data.copy()

    # === CORE INDICATORS ===
    data['RSI_14'] = compute_rsi(data['Close'])
    data['RSI_10'] = compute_rsi(data['Low'], period=9)
    data['RSI_22'] = compute_rsi(data['Close'], period=22)
    data['MACD'], data['Signal'] = compute_macd(data)
    data['K'], data['D'], data['J'] = compute_kdj(data)
    data['CCI'] = compute_cci(data)
    data['Bias'], data['Bias_Smoothed'] = compute_bias_indicator(data)
    data['Inertia'], data['Inertia_Smoothed'] = compute_inertia_indicator(data)

    # === NEW INDICATORS ===
    data['TD_Sequential'] = td_sequential(data['Close'])
    data['Cyber_Cycle'] = ehlers_cyber_cycle(data['Close'])
    data = pd.concat([data, supertrend(data)], axis=1)
    data['Williams_%R'] = williams_r(data['High'], data['Low'], data['Close'])

    # === DIVERGENCE LOGIC ===
    maxima, minima = find_extrema(data['Close'], order=30)
    data['DIV_RSI'] = np.where(
        (data.index.isin(data.index[maxima])) & (data['RSI_14'].diff() > -1) & (data['RSI_14'] > 50), -50,
        np.where((data.index.isin(data.index[minima])) & (data['RSI_14'].diff() < 1) & (data['RSI_14'] < 50), 2, 0))
    
    data['DIV_MACD'] = np.where(
        (data.index.isin(data.index[maxima])) & (data['MACD'].diff() > -0.1) & (data['MACD'] > 0), -50,
        np.where((data.index.isin(data.index[minima])) & (data['MACD'].diff() < 0.1) & (data['MACD'] < 0), 2, 0))
    
    data['DIV_KDJ'] = np.where(
        (data.index.isin(data.index[maxima])) & (data['J'].diff() > -30) & (data['J'] > 50), -50,
        np.where((data.index.isin(data.index[minima])) & (data['J'].diff() < 30) & (data['J'] < 50), 2, 0))
    
    data['DIV_CCI'] = np.where(
        (data.index.isin(data.index[maxima])) & (data['CCI'].diff() > -10) & (data['CCI'] > 100), -1,
        np.where((data.index.isin(data.index[minima])) & (data['CCI'].diff() < 10) & (data['CCI'] < -100), 1, 0))

    data['Divergence_Score'] = (
        data['DIV_RSI'].clip(-1, 1) +
        data['DIV_MACD'].clip(-1, 1) +
        data['DIV_KDJ'].clip(-1, 1) +
        data['DIV_CCI'])

    data["Potential_Divergence"] = (
        (data['DIV_RSI'] + data['DIV_MACD'] + data['DIV_KDJ']) >= 2).astype(int) - (
        (data['DIV_RSI'] + data['DIV_MACD'] + data['DIV_KDJ']) <= -2).astype(int)

    data['Confirmed_Divergence'] = 0
    divergence_active = False
    divergence_type = 0
    divergence_start_idx = 0

    for i in range(len(data)):
        if not divergence_active and data['Potential_Divergence'].iloc[i] != 0:
            divergence_active = True
            divergence_type = data['Potential_Divergence'].iloc[i]
            divergence_start_idx = i

        if divergence_active:
            if divergence_type == 1:
                rsi_confirm = data['RSI_10'].iloc[i] >= 70
                bias_confirm = data['Bias_Smoothed'].iloc[i] > 0
                williams_confirm = data['Williams_%R'].iloc[i] < -80

                if rsi_confirm and bias_confirm and williams_confirm:
                    data.at[data.index[divergence_start_idx], 'Confirmed_Divergence'] = 1
                    divergence_active = False

            elif divergence_type == -1:
                rsi_confirm = data['RSI_10'].iloc[i] <= 30
                bias_confirm = data['Bias_Smoothed'].iloc[i] < 0
                williams_confirm = data['Williams_%R'].iloc[i] > -20

                if rsi_confirm and bias_confirm and williams_confirm:
                    data.at[data.index[divergence_start_idx], 'Confirmed_Divergence'] = -1
                    divergence_active = False

        if divergence_active:
            if divergence_type == 1 and data['Close'].iloc[i] < data['Close'].iloc[divergence_start_idx]:
                divergence_active = False
            elif divergence_type == -1 and data['Close'].iloc[i] > data['Close'].iloc[divergence_start_idx]:
                divergence_active = False

    # Create plot with new indicators
    fig_buf = create_plot(data, symbol, interval, market_type)

    current_signals = {
        "Bullish Divergence": data.index[data['Confirmed_Divergence'] == 1].tolist(),
        "Bearish Divergence": data.index[data['Confirmed_Divergence'] == -1].tolist(),
        "RSI Crossover": [],
        "TD Sequential": data.index[abs(data['TD_Sequential']) == 1].tolist()
    }

    crossover_up = (data['RSI_10'] > data['RSI_22']) & (data['RSI_10'].shift(1) <= data['RSI_22'].shift(1))
    crossover_down = (data['RSI_10'] < data['RSI_22']) & (data['RSI_10'].shift(1) >= data['RSI_22'].shift(1))
    current_signals["RSI Crossover"] = data.index[crossover_up | crossover_down].tolist()

    return fig_buf, current_signals

# App header and info
st.write("Developed with ❤️ by **Uka Benjamin Imo**  **+2347067193071** **benjaminukaimo@gmail.com**") 
st.subheader("VAPS 0.2 - Financial Market Modelling")
st.markdown("**A Financial AI System Based on Void Anti-symmetric Pattern Synthesizer for Market Dynamics.**")

# Input controls
col1, col2, col3 = st.columns(3)
with col1:
    symbol = st.selectbox("Symbol", ["SOL", "ETH","BTC","TRX", "ADA", "BCH", "PEOPLE", "IOTX", "POL","ATOM", "C98", "AAVE","DOT","MANA","CAKE", "XRP","ALICE", "BNB", "EOS", "ONE","ENJ","NEAR","VTHO","TRUMP","CRO","TLM","LUNC","ETC","STX","MBOX","SAND","UNI","DYDX","RUNE","DENT", "SHIB", "DOGE", "HOT", "CELR", "VET", "XLM", "ALGO", "GBP", "AUD","XAU", "EUR"])
with col2:
    interval = st.selectbox("Interval", ["1h", "15min", "5min", "30min", "4h", "1day", "1week", "1month", "1min"])
with col3:
    market_type = st.selectbox("Market Type", ["Forex", "Crypto", "Stock"], index=0)

# Sidebar controls
st.sidebar.title("Controls")
live_update = st.sidebar.checkbox("Live Update", True)
lookback = st.slider("Lookback Period (bars)", 100, 1000, 240)
update_interval = st.sidebar.slider("Update Interval (seconds)", 5, 300, 30)

# Add refresh button
if st.button("🔄 Manual Refresh"):
    st.session_state.force_refresh = True
    st.rerun()

# Alert configuration
st.sidebar.title("Alert Settings")
alert_enabled = st.sidebar.checkbox("Enable Alerts", True)
alert_sound = st.sidebar.checkbox("Play Alert Sound", True)
alert_types = st.sidebar.multiselect(
    "Alert Types",
    ["Bullish Divergence", "Bearish Divergence", "RSI Crossover", "TD Sequential"],
    default=["Bullish Divergence", "Bearish Divergence"]
)

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.previous_signals = {
        "Bullish Divergence": [],
        "Bearish Divergence": [],
        "RSI Crossover": [],
        "TD Sequential": []
    }
    st.session_state.alert_history = []
    st.session_state.sse_client = None
    st.session_state.last_data = None
    st.session_state.force_refresh = False
    st.session_state.loading = True

# SSE Client implementation
class SSEClient:
    def __init__(self, api_key, symbol, interval, lookback):
        self.api_key = api_key
        self.symbol = symbol
        self.interval = interval
        self.lookback = lookback
        self.event_queue = queue.Queue()
        self.running = False
        self.thread = None
        self.last_data = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _run(self):
        url = f"https://api.twelvedata.com/timeseries?apikey={self.api_key}&symbol={self.symbol}/USD&type=etf&timezone=Africa/Lagos&interval={self.interval}"
        headers = {'Accept-Encoding': 'br'}

        try:
            with requests.get(url, stream=True, headers=headers) as response:
                for line in response.iter_lines():
                    if not self.running:
                        break

                    if line:
                        try:
                            event_data = json.loads(line.decode('utf-8'))
                            if 'event' in event_data and event_data['event'] == 'price':
                                compressed = compress_data(event_data)
                                self.event_queue.put(compressed)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            st.error(f"SSE Error: {str(e)}")

    def get_update(self):
        try:
            compressed = self.event_queue.get_nowait()
            return decompress_data(compressed)
        except queue.Empty:
            return None

def main_display():
    st.header(f"{symbol} ({interval}) Analysis")

    if live_update and st.session_state.sse_client is None:
        st.session_state.sse_client = SSEClient(api_key, symbol, interval, lookback)
        st.session_state.sse_client.start()

    if live_update:
        update = st.session_state.sse_client.get_update()
        if update:
            st.session_state.last_data = update_data_with_sse(
                st.session_state.last_data,
                update
            )
        data = st.session_state.last_data if st.session_state.last_data is not None else load_initial_data(symbol, interval, lookback, api_key)
    else:
        if st.session_state.sse_client is not None:
            st.session_state.sse_client.stop()
            st.session_state.sse_client = None

        data = load_initial_data(symbol, interval, lookback, api_key)
        st.session_state.last_data = data

    if data.empty:
        st.warning("No data available - check your API key and symbol")
        return

    # Show loading message while processing
    if st.session_state.loading:
        with st.spinner("Please wait, the anti-symmetric synthesizer is working..."):
            fig_buf, current_signals = swing_3(data)
            st.session_state.loading = False
    else:
        fig_buf, current_signals = swing_3(data)

    # Use a container to prevent flickering
    chart_container = st.empty()
    with chart_container.container():
        st.image(fig_buf, use_container_width=True)

    if alert_enabled and live_update:
        new_signals = check_for_new_signals(current_signals)
        for signal_type, timestamps in new_signals.items():
            if signal_type in alert_types:
                for ts in timestamps:
                    trigger_alert(signal_type, data.loc[ts, 'Close'], ts)

    st.session_state.previous_signals = current_signals

    st.caption(f"Last update (0:0 UTC- Same as time on chart: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {len(data)} bars loaded")

    with st.sidebar.expander("Recent Alerts", expanded=True):
        for alert in reversed(st.session_state.alert_history[-10:]):
            cols = st.columns([1, 2, 1])
            cols[0].write(alert['timestamp'].strftime('%H:%M:%S'))

            if alert['type'] == "Bullish Divergence":
                cols[1].success(alert['type'])
            elif alert['type'] == "Bearish Divergence":
                cols[1].error(alert['type'])
            else:
                cols[1].warning(alert['type'])

            cols[2].write(f"{alert['price']:.4f}")

# Run the app
if __name__ == "__main__":
    placeholder = st.empty()
    
    while True:
        with placeholder.container():
            main_display()
            
            # Reset force refresh flag after processing
            if st.session_state.get('force_refresh', False):
                st.session_state.force_refresh = False
                st.session_state.loading = True
                st.rerun()

        if not live_update:
            break

        time.sleep(max(update_interval, 30))