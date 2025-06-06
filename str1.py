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
    background: linear-gradient(pink,skyblue, skyblue);
    color: black;
}
[data-testid="stSidebar"] {
    background: linear-gradient(skyblue, blue) !important;
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

def compress_image(fig, quality=80):
    png_buf = io.BytesIO()
    fig.savefig(png_buf, format='png', dpi=100)
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

# App header and info
st.write("Developed with ❤️ by **Uka Benjamin Imo**  **[+234............]** **benjaminukaimo@gmail.com**") 
image1 = Image.open("mypiclogo.png")
st.image(image1)
st.markdown(" ")
st.subheader("VAPS 0.2 - Financial Market Modelling")

st.markdown("**A Financial AI System Based on Void Anti-symmetric Pattern Synthesizer for Market Dynamics.**")

# Input controls
col1, col2, col3 = st.columns(3)
with col1:
    symbol = st.selectbox("Symbol", ["TRX", "ADA", "BTC", "BCH", "PEOPLE", "ETH", "IOTX", "SOL", "POL","ATOM", "C98", "AAVE","DOT","MANA","CAKE", "XRP","ALICE", "BNB", "EOS", "ONE","ENJ","NEAR","VTHO","TRUMP","JST","ETC","STX","MBOX","SAND","UNI","DYDX","RUNE","DENT", "SHIB", "DOGE", "HOT", "CELR", "VET", "XLM", "ALGO", "XAU", "EUR", "GBP", "AUD"])
with col2:
    interval = st.selectbox("Interval", ["15min","1min", "5min", "30min", "1h",  "4h", "1day", "1week", "1month"])
with col3:
    market_type = st.selectbox("Market Type", ["Forex", "Crypto", "Stock"], index=0)

# Sidebar controls
st.sidebar.title("Controls")
live_update = st.sidebar.checkbox("Live Update", True)
lookback = st.sidebar.slider("Lookback Period (bars)", 50, 1000, 300)
update_interval = st.sidebar.slider("Update Interval (seconds)", 5, 300, 10)

# Add refresh button
if st.sidebar.button("🔄 Manual Refresh"):
    st.session_state.force_refresh = True
    st.rerun()

# Alert configuration
st.sidebar.title("Alert Settings")
alert_enabled = st.sidebar.checkbox("Enable Alerts", True)
alert_sound = st.sidebar.checkbox("Play Alert Sound", True)
alert_types = st.sidebar.multiselect(
    "Alert Types",
    ["Bullish Divergence", "Bearish Divergence", "RSI Crossover"],
    default=["Bullish Divergence", "Bearish Divergence"]
)

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.previous_signals = {
        "Bullish Divergence": [],
        "Bearish Divergence": [],
        "RSI Crossover": []
    }
    st.session_state.alert_history = []
    st.session_state.sse_client = None
    st.session_state.last_data = None
    st.session_state.force_refresh = False
    st.session_state.loading = True

# Technical indicator functions
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

def compute_ehlers_fisher_transform(data, period=32):
    midpoint = (data['High'] + data['Low']) / 2
    hh = midpoint.rolling(window=period).max()
    ll = midpoint.rolling(window=period).min()
    normalized = 0.66 * ((midpoint - ll) / (hh - ll) - 0.5)
    normalized = normalized.clip(-0.999, 0.999)
    fisher = 1 * np.log((1 + normalized) / (1 - normalized))
    fisher_smoothed = fisher.ewm(span=3, adjust=False).mean()
    return fisher, fisher_smoothed

def compute_smi_ergodic(data, period=20, smooth_long=5, smooth_short=3):
    midpoint = (data['High'] + data['Low']) / 2
    price_change = midpoint.diff(period)
    momentum = midpoint - midpoint.shift(period)
    ergodic_line = momentum.ewm(span=smooth_long, adjust=False).mean()
    trigger_line = ergodic_line.ewm(span=smooth_short, adjust=False).mean()
    return ergodic_line, trigger_line

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

def create_plot(data, price_line_colors, rsi_10_colors, symbol, interval, market_type):
    visible_indicators = ["RSI", "Fisher", "Bias", "Divergence"]
    num_plots = 1 + len(visible_indicators)

    width = 4  # Very wide
    height = 5 * num_plots  # Tall

    fig = Figure(figsize=(width, height), dpi=70)
    gs = fig.add_gridspec(num_plots, 1, height_ratios=[16] + [5]*len(visible_indicators))

    axes = [fig.add_subplot(gs[0])]
    for i in range(1, num_plots):
        axes.append(fig.add_subplot(gs[i], sharex=axes[0]))

    for ax in axes:
        ax.tick_params(axis='both', which='major',
                      labelsize=42, width=4, length=4, pad=6)
        ax.tick_params(axis='both', which='major', labelsize=42)

        for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] +
                     ax.get_xticklabels() + ax.get_yticklabels()):
            item.set_fontweight('bold')
            item.set_fontsize(32)
            item.set_fontstyle('normal')

        ax.grid(True, linestyle='-', linewidth=1.5, alpha=0.7)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_linewidth(2)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")

    current_price = data['Close'].iloc[-1]
    current_time = data.index[-1].strftime('%H:%M UTC')

    for i in range(1, len(data)):
        axes[0].plot(data.index[i-1:i+1], data['Close'].iloc[i-1:i+1],
                    color=price_line_colors[i],
                    linewidth=5.0,
                    alpha=1.0,
                    solid_capstyle='round')

    axes[0].scatter(data.index[data['Confirmed_Divergence'] == 1],
                   data['Close'][data['Confirmed_Divergence'] == 1],
                   color='green', marker='^', s=300,
                   edgecolor='black', linewidth=2,
                   label='Bullish Div')
    axes[0].scatter(data.index[data['Confirmed_Divergence'] == -1],
                   data['Close'][data['Confirmed_Divergence'] == -1],
                   color='red', marker='v', s=300,
                   edgecolor='black', linewidth=2,
                   label='Bearish Div')

    axes[0].axhline(y=current_price, color='blue', linestyle='--', alpha=0.7, linewidth=4.0)
    axes[0].text(0.02, 0.95, f'{current_price:.5f} ({current_time})',
                transform=axes[0].transAxes,
                color='blue',
                fontsize=36,
                fontweight='bold',
                va='top',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='blue', linewidth=2, pad=5))

    axes[0].set_title(f'{market_type}: {symbol} ({interval})',
                     fontsize=32,
                     fontweight='bold',
                     pad=20)
    axes[0].grid(True, linestyle='-', alpha=0.7, linewidth=2.5)

    plot_idx = 1

    for i in range(1, len(data)):
        axes[plot_idx].plot(data.index[i-1:i+1], data['RSI_10'].iloc[i-1:i+1],
                          color=rsi_10_colors[i],
                          linewidth=4.0,
                          alpha=1.0,
                          solid_capstyle='round',
                          label='RSI 10' if i == 1 else "")
    axes[plot_idx].plot(data.index, data['RSI_22'],
                       color='orange',
                       linewidth=4.0,
                       alpha=1.0,
                       label='RSI 22')

    current_rsi = data['RSI_10'].iloc[-1]
    axes[plot_idx].axhline(y=current_rsi, color='blue', linestyle='--', alpha=1.0, linewidth=4.0)
    axes[plot_idx].annotate(f'{current_rsi:.2f}',
                          xy=(0.98, current_rsi),
                          xycoords=('axes fraction', 'data'),
                          xytext=(-10, 0),
                          textcoords='offset points',
                          color='blue',
                          fontsize=30,
                          fontweight='bold',
                          va='center',
                          ha='right',
                          bbox=dict(facecolor='white', alpha=0.8, edgecolor='black', linewidth=1, pad=4))

    axes[plot_idx].axhline(70, color='gray', linestyle='--', alpha=1.0, linewidth=2.5)
    axes[plot_idx].axhline(30, color='gray', linestyle='--', alpha=1.0, linewidth=2.5)
    axes[plot_idx].set_title('STRENGTH INDICATOR',
                           fontsize=26,
                           fontweight='bold',
                           pad=15)
    plot_idx += 1

    axes[plot_idx].plot(data.index, data['Ehlers_Fisher_Smoothed'],
                       color='darkorange',
                       linewidth=4.5,
                       alpha=1.0,
                       solid_capstyle='round',
                       label='Fisher Transform')
    axes[plot_idx].axhline(0.5, color='red', linestyle='--', alpha=1.0, linewidth=1.5)
    axes[plot_idx].axhline(-0.5, color='green', linestyle='--', alpha=1.0, linewidth=1.5)
    axes[plot_idx].axhline(0, color='black', linestyle='-', alpha=1.0, linewidth=1.0)
    axes[plot_idx].set_title('FISHER TRANSFORMATION',
                           fontsize=32,
                           fontweight='bold',
                           pad=15)
    plot_idx += 1

    axes[plot_idx].plot(data.index, data['Bias'],
                       color='gray',
                       linewidth=4.0,
                       alpha=0.7,
                       label='Raw Bias')
    axes[plot_idx].plot(data.index, data['Bias_Smoothed'],
                       color='purple',
                       linewidth=4.5,
                       alpha=1.0,
                       solid_capstyle='round',
                       label='Smoothed Bias')
    axes[plot_idx].axhline(0.3, color='red', linestyle='--', alpha=1.0, linewidth=1.5)
    axes[plot_idx].axhline(-0.3, color='green', linestyle='--', alpha=1.0, linewidth=1.5)
    axes[plot_idx].axhline(0, color='black', linestyle='-', alpha=1.0, linewidth=1.0)

    axes[plot_idx].fill_between(data.index, data['Bias_Smoothed'], 0.2,
                              where=data['Bias_Smoothed'] >= 0.2,
                              facecolor='green', alpha=0.3, interpolate=True)
    axes[plot_idx].fill_between(data.index, data['Bias_Smoothed'], -0.2,
                              where=data['Bias_Smoothed'] <= -0.2,
                              facecolor='red', alpha=0.3, interpolate=True)
    axes[plot_idx].set_title('MARKET BIAS INDICATOR',
                           fontsize=26,
                           fontweight='bold',
                           pad=15)
    plot_idx += 1

    bar_width = 1.2 * (data.index[1] - data.index[0]).total_seconds() / (24 * 3600)
    axes[plot_idx].bar(data.index, data['Divergence_Score'],
                      color=np.where(data['Divergence_Score'] > 0, 'green', 'red'),
                      width=bar_width,
                      alpha=0.7,
                      edgecolor='black',
                      linewidth=1.0)

    axes[plot_idx].axhline(3, color='green', linestyle='--', alpha=1.0, linewidth=1.5)
    axes[plot_idx].axhline(-3, color='red', linestyle='--', alpha=1.0, linewidth=1.5)
    axes[plot_idx].axhline(0, color='black', linestyle='-', alpha=1.0, linewidth=1.0)

    strong_bullish = data['Divergence_Score'] >= 3
    strong_bearish = data['Divergence_Score'] <= -3
    axes[plot_idx].scatter(data.index[strong_bullish], data['Divergence_Score'][strong_bullish],
                         color='lime', marker='o', s=100,
                         edgecolor='black', linewidth=2.5,
                         label='Strong Bullish')
    axes[plot_idx].scatter(data.index[strong_bearish], data['Divergence_Score'][strong_bearish],
                         color='darkred', marker='o', s=100,
                         edgecolor='black', linewidth=2.5,
                         label='Strong Bearish')
    axes[plot_idx].set_title('ANTI-SYMMETRIC BIDIVERGENCE SCORE',
                           fontsize=32,
                           fontweight='bold',
                           pad=15)

    fig.tight_layout(pad=3.0, h_pad=2.0, w_pad=2.0)
    fig.subplots_adjust(top=0.94, right=0.95)

    webp_buf = compress_image(fig)
    plt.close(fig)

    return webp_buf

def swing_3(data):
    if data.empty:
        return plt.figure(), {}

    data = data.copy()

    # Compute indicators
    data['RSI_14'] = compute_rsi(data['Close'])
    data['RSI_10'] = compute_rsi(data['Low'], period=9)
    data['RSI_22'] = compute_rsi(data['Close'], period=22)
    data['MACD'], data['Signal'] = compute_macd(data)
    data['K'], data['D'], data['J'] = compute_kdj(data)
    data['CCI'] = compute_cci(data)
    data['Ehlers_Fisher'], data['Ehlers_Fisher_Smoothed'] = compute_ehlers_fisher_transform(data)
    data['SMI_Ergodic'], data['SMI_Trigger'] = compute_smi_ergodic(data)
    data['Bias'], data['Bias_Smoothed'] = compute_bias_indicator(data)
    data['Inertia'], data['Inertia_Smoothed'] = compute_inertia_indicator(data)

    # Find extrema
    maxima, minima = find_extrema(data['Close'], order=30)

    # Compute divergences
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
                fisher_confirm = data['Ehlers_Fisher_Smoothed'].iloc[i] > 0

                if rsi_confirm and bias_confirm and fisher_confirm:
                    data.at[data.index[divergence_start_idx], 'Confirmed_Divergence'] = 1
                    divergence_active = False

            elif divergence_type == -1:
                rsi_confirm = data['RSI_10'].iloc[i] <= 30
                bias_confirm = data['Bias_Smoothed'].iloc[i] < 0
                fisher_confirm = data['Ehlers_Fisher_Smoothed'].iloc[i] < 0

                if rsi_confirm and bias_confirm and fisher_confirm:
                    data.at[data.index[divergence_start_idx], 'Confirmed_Divergence'] = -1
                    divergence_active = False

        if divergence_active:
            if divergence_type == 1 and data['Close'].iloc[i] < data['Close'].iloc[divergence_start_idx]:
                divergence_active = False
            elif divergence_type == -1 and data['Close'].iloc[i] > data['Close'].iloc[divergence_start_idx]:
                divergence_active = False

    divergence_state = 0
    divergence_price = None
    price_line_colors = []
    for i in range(len(data)):
        if data['Confirmed_Divergence'].iloc[i] == 1:
            divergence_state = 1
            divergence_price = data['Close'].iloc[i]
        elif data['Confirmed_Divergence'].iloc[i] == -1:
            divergence_state = -1
            divergence_price = data['Close'].iloc[i]
        if divergence_state == 1:
            if data['Close'].iloc[i] < divergence_price:
                price_line_colors.append('black')
                divergence_state = 0
                divergence_price = None
            else:
                price_line_colors.append('green')
        elif divergence_state == -1:
            if data['Close'].iloc[i] > divergence_price:
                price_line_colors.append('black')
                divergence_state = 0
                divergence_price = None
            else:
                price_line_colors.append('red')
        else:
            price_line_colors.append('black')

    rsi_crossover_state = 0
    rsi_10_colors = []
    for i in range(len(data)):
        if data['RSI_10'].iloc[i] > data['RSI_22'].iloc[i] and (i == 0 or data['RSI_10'].iloc[i-1] <= data['RSI_22'].iloc[i-1]):
            rsi_crossover_state = 1
        elif data['RSI_10'].iloc[i] < data['RSI_22'].iloc[i] and (i == 0 or data['RSI_10'].iloc[i-1] >= data['RSI_22'].iloc[i-1]):
            rsi_crossover_state = -1
        if rsi_crossover_state == 1:
            if price_line_colors[i] == 'green':
                rsi_10_colors.append('green')
            else:
                rsi_10_colors.append('gray')
        elif rsi_crossover_state == -1:
            if price_line_colors[i] == 'red':
                rsi_10_colors.append('green')
            else:
                rsi_10_colors.append('gray')
        else:
            rsi_10_colors.append('gray')

    fig_buf = create_plot(data, price_line_colors, rsi_10_colors, symbol, interval, market_type)

    current_signals = {
        "Bullish Divergence": data.index[data['Confirmed_Divergence'] == 1].tolist(),
        "Bearish Divergence": data.index[data['Confirmed_Divergence'] == -1].tolist(),
        "RSI Crossover": []
    }

    crossover_up = (data['RSI_10'] > data['RSI_22']) & (data['RSI_10'].shift(1) <= data['RSI_22'].shift(1))
    crossover_down = (data['RSI_10'] < data['RSI_22']) & (data['RSI_10'].shift(1) >= data['RSI_22'].shift(1))
    current_signals["RSI Crossover"] = data.index[crossover_up | crossover_down].tolist()

    return fig_buf, current_signals

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

    st.caption(f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {len(data)} bars loaded")

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