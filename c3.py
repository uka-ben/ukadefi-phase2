import streamlit as st
import numpy as np 
import pandas as pd
import matplotlib.pyplot as plt
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

# Compression helper functions
def compress_data(data):
    """Compress data using brotli with optimal settings"""
    if isinstance(data, (pd.DataFrame, pd.Series)):
        data = data.to_json(orient='split')
    return brotli.compress(json.dumps(data).encode('utf-8'))

def decompress_data(compressed_data):
    """Decompress brotli compressed data"""
    return json.loads(brotli.decompress(compressed_data).decode('utf-8'))

def compress_image(fig, quality=100):
    """Convert matplotlib figure to optimized WebP"""
    png_buf = io.BytesIO()
    fig.savefig(png_buf, format='png', dpi=80)
    png_buf.seek(0)
    img = Image.open(png_buf)
    webp_buf = io.BytesIO()
    img.save(webp_buf, format='webp', quality=quality)
    webp_buf.seek(0)
    return webp_buf

# Sound alert function using hosted files
def play_alert_sound(alert_type="neutral"):
    """Play alert sound using HTML5 audio"""
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

# SSE (Server-Sent Events) implementation
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
        """Background thread that handles SSE connection"""
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
        """Get the latest update from the queue"""
        try:
            compressed = self.event_queue.get_nowait()
            return decompress_data(compressed)
        except queue.Empty:
            return None

# App header and info
st.write("Developed with ❤️ by **Uka Benjamin Imo**  **[+2347067193071]** **benjaminukaimo@gmail.com**") 
image1 = Image.open("mypiclogo.png")
st.image(image1)
st.markdown(" ")
st.subheader("TIMETION 0.0.2 -for financial market modelling")

st.markdown("**A Financial AI System Based on Symmetric-Antisymmetric Pattern Learning for Market Dynamics.** TIMETION is a powerful system with several phases. Timetion can offer solution to problems involving **time series, fraud detection, robotics, decisioning**, etc.")
st.markdown("Timetion: Uncovering hidden motion within time — powered by pattern-based AI. This app presents **TIMETION** being applied to detect and forecast price reversal points in financial markets.")

# Input controls
symbol = st.text_input("Symbol.. EUR,BTC,ETH,AAPL,etc", "EUR").upper()
interval = st.selectbox("Interval", ["1min","5min", "15min", "1h", "4h", "1day", "1week", "1month"])

# Sidebar controls
st.sidebar.title("Controls")
page = st.radio(
    "Select Strategy", 
    ["Short Swing 1", "Short Swing 2", "Swing 3"],
    index=0, horizontal=True
)

# API Configuration
api_key = "cef197ce3e054ee69d6c795401b229cd"

# Live update controls
live_update = st.sidebar.checkbox("Live Chat Update", True)
lookback = st.sidebar.slider("Chat Lookback Period (bars)", 50, 1000, 300)
update_interval = st.sidebar.slider("Live Update Interval (seconds)", 5, 300, 10)

# Alert configuration
st.sidebar.title("Alert Settings")
alert_enabled = st.sidebar.checkbox("Enable Alerts", True)
alert_sound = st.sidebar.checkbox("Play Alert Sound", True)
alert_volume = st.sidebar.slider("Alert Volume", 0.1, 1.0, 0.7)
alert_types = st.sidebar.multiselect(
    "Alert Types",
    ["Bullish Divergence", "Bearish Divergence", "RSI Crossover"],
    default=["Bullish Divergence", "Bearish Divergence"]
)

# Initialize session state
if 'previous_signals' not in st.session_state:
    st.session_state.previous_signals = {
        "Bullish Divergence": [],
        "Bearish Divergence": [],
        "RSI Crossover": []
    }
if 'alert_history' not in st.session_state:
    st.session_state.alert_history = []
if 'sse_client' not in st.session_state:
    st.session_state.sse_client = None
if 'last_data' not in st.session_state:
    st.session_state.last_data = None

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

def find_extrema(series, order=70):
    maxima = argrelextrema(series.values, np.greater, order=order)[0]
    minima = argrelextrema(series.values, np.less, order=order)[0]
    return maxima, minima

def find_extrema_multi(series, order_values):
    maxima, minima = [], []
    for order in order_values:
        maxima.extend(argrelextrema(series.values, np.greater, order=order)[0])
        minima.extend(argrelextrema(series.values, np.less, order=order)[0])
    return sorted(set(maxima)), sorted(set(minima))

# Data loading functions
@st.cache_data(ttl=60, show_spinner="Fetching market data...")
def load_initial_data(symbol, interval, lookback, api_key):
    """Load initial data from TwelveData API with compression"""
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
    """Update existing data with new SSE data point"""
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
    
    # Concatenate and drop duplicates
    updated = pd.concat([prev_data, new_row]).drop_duplicates(subset=['Date'], keep='last')
    
    # Maintain lookback window
    if len(updated) > lookback:
        updated = updated.iloc[-lookback:]
    
    updated.index = updated['Date']
    return updated

def check_for_new_signals(current_signals):
    """Compare current signals with previous to detect new ones"""
    new_signals = {}
    for signal_type in current_signals:
        previous = st.session_state.previous_signals.get(signal_type, [])
        current = current_signals.get(signal_type, [])
        
        # Compare timestamps to find new signals
        new = [s for s in current if s not in previous]
        if new:
            new_signals[signal_type] = new
            
    return new_signals

def trigger_alert(alert_type, price, timestamp):
    """Display and play sound alert with optimized handling"""
    # Visual alert
    if alert_type == "Bullish Divergence":
        st.toast(f"🚨 BULLISH DIVERGENCE at {price:.4f}", icon="📈")
        st.sidebar.success(f"Bullish divergence at {price:.4f}")
    elif alert_type == "Bearish Divergence":
        st.toast(f"🚨 BEARISH DIVERGENCE at {price:.4f}", icon="📉")
        st.sidebar.error(f"Bearish divergence at {price:.4f}")
    elif alert_type == "RSI Crossover":
        st.toast(f"⚠️ RSI CROSSOVER at {price:.4f}", icon="🔔")
        st.sidebar.warning(f"RSI crossover at {price:.4f}")
    
    # Sound alert
    if alert_sound:
        sound_type = "bullish" if "Bullish" in alert_type else "bearish" if "Bearish" in alert_type else "neutral"
        play_alert_sound(sound_type)
    
    # Add to alert history
    st.session_state.alert_history.append({
        "timestamp": timestamp,
        "type": alert_type,
        "price": price,
        "symbol": symbol
    })
    
    # Keep only last 50 alerts
    st.session_state.alert_history = st.session_state.alert_history[-50:]

# Strategy 1: Short Swing 1
def short_swing_1(data):
    if data.empty:
        return plt.figure(), {}
    
    data = data.copy()
    # Apply Calculations
    data['RSI_14'] = compute_rsi(data['Close'])
    data['RSI_5'] = compute_rsi(data['Close'], period=5)
    data['RSI_20'] = compute_rsi(data['Close'], period=20)
    data['MACD'], data['Signal'] = compute_macd(data)
    data['K'], data['D'], data['J'] = compute_kdj(data)

    # Find Strong Extrema
    maxima, minima = find_extrema(data['Close'], order=20)
    
    # Compute Divergences
    data['DIV_RSI'] = np.where(
        (data.index.isin(data.index[maxima])) & (data['RSI_14'].diff() > -1) & (data['RSI_14'] > 50), -1,
        np.where((data.index.isin(data.index[minima])) & (data['RSI_14'].diff() < 1) & (data['RSI_14'] < 50), 1, 0)
    )

    data['DIV_MACD'] = np.where(
        (data.index.isin(data.index[maxima])) & (data['MACD'].diff() > -0.1) & (data['MACD'] > 0), -1,
        np.where((data.index.isin(data.index[minima])) & (data['MACD'].diff() < 0.1) & (data['MACD'] < 0), 1, 0)
    )

    data['DIV_KDJ'] = np.where(
        (data.index.isin(data.index[maxima])) & (data['J'].diff() > -30) & (data['J'] > 50), -1,
        np.where((data.index.isin(data.index[minima])) & (data['J'].diff() < 30) & (data['J'] < 50), 1, 0)
    )

    # Strong Divergences Only (Require at least 2 Confirmations)
    data["Final_Divergence"] = (
        (data['DIV_RSI'] + data['DIV_MACD'] + data['DIV_KDJ']) >= 2
    ).astype(int) - (
        (data['DIV_RSI'] + data['DIV_MACD'] + data['DIV_KDJ']) <= -2
    ).astype(int)

    # Track current signals
    current_signals = {
        "Bullish Divergence": data.index[data['Final_Divergence'] == 1].tolist(),
        "Bearish Divergence": data.index[data['Final_Divergence'] == -1].tolist(),
        "RSI Crossover": []
    }

    # Check RSI crossovers
    crossover_up = (data['RSI_5'] > data['RSI_20']) & (data['RSI_5'].shift(1) <= data['RSI_20'].shift(1))
    crossover_down = (data['RSI_5'] < data['RSI_20']) & (data['RSI_5'].shift(1) >= data['RSI_20'].shift(1))
    current_signals["RSI Crossover"] = data.index[crossover_up | crossover_down].tolist()

    # Plotting
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [2, 1]})
    
    # Configure axes to right side
    ax1.yaxis.tick_right()
    ax2.yaxis.tick_right()
    ax1.yaxis.set_label_position("right")
    ax2.yaxis.set_label_position("right")
    
    # Get current price and time
    current_price = data['Close'].iloc[-1]
    current_time = data.index[-1]
    
    # Price plot with dynamic coloring
    divergence_state = 0
    divergence_price = None
    price_colors = []
    
    for i in range(len(data)):
        if data['Final_Divergence'].iloc[i] == 1:
            divergence_state = 1
            divergence_price = data['Close'].iloc[i]
        elif data['Final_Divergence'].iloc[i] == -1:
            divergence_state = -1
            divergence_price = data['Close'].iloc[i]
        
        if divergence_state == 1:
            if data['Close'].iloc[i] < divergence_price:
                color = 'black'
                divergence_state = 0
            else:
                color = 'green'
        elif divergence_state == -1:
            if data['Close'].iloc[i] > divergence_price:
                color = 'black'
                divergence_state = 0
            else:
                color = 'red'
        else:
            color = 'black'
        
        price_colors.append(color)
    
    for i in range(1, len(data)):
        ax1.plot(data.index[i-1:i+1], data['Close'].iloc[i-1:i+1], color=price_colors[i])
    
    # Mark current price with dashed line and annotation
    ax1.axhline(y=current_price, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax1.annotate(f'{current_price:.4f} ({current_time.strftime("%H:%M")})', 
                xy=(1, current_price), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    # Mark divergences
    bull_div = data[data['Final_Divergence'] == 1]
    bear_div = data[data['Final_Divergence'] == -1]
    
    ax1.scatter(bull_div.index, bull_div['Close'], color='green', marker='^', s=100, label='Bullish Divergence')
    ax1.scatter(bear_div.index, bear_div['Close'], color='red', marker='v', s=100, label='Bearish Divergence')
    
    ax1.set_title(f'{symbol} Price with Short-Term Reversal Traps ({interval})', fontsize=12)
    ax1.legend(loc='upper left')
    ax1.grid(True, linestyle='--', alpha=0.7)
    
    # RSI plot
    ax2.plot(data.index, data['RSI_5'], color='blue', label='RSI 5')
    ax2.plot(data.index, data['RSI_20'], color='orange', label='RSI 20')
    
    # Mark current RSI value with dashed line
    current_rsi = data['RSI_5'].iloc[-1]
    ax2.axhline(y=current_rsi, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax2.annotate(f'{current_rsi:.2f}', 
                xy=(1, current_rsi), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    # Mark crossovers
    rsi_up = data[crossover_up]
    rsi_down = data[crossover_down]
    
    ax2.scatter(rsi_up.index, rsi_up['RSI_5'], color='green', marker='^', s=80, label='Bullish Crossover')
    ax2.scatter(rsi_down.index, rsi_down['RSI_5'], color='red', marker='v', s=80, label='Bearish Crossover')
    
    ax2.axhline(70, color='gray', linestyle='--', alpha=0.5)
    ax2.axhline(30, color='gray', linestyle='--', alpha=0.5)
    ax2.set_title("Market Twist", fontsize=12)
    ax2.legend(loc='upper left')
    ax2.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    return fig, current_signals

# Strategy 2: Short Swing 2
def short_swing_2(data):
    if data.empty:
        return plt.figure(), {}
    
    data = data.copy()
    
    # Independent configurations for RSI, MACD, and KDJ
    rsi_configs = [{"period": 10, "orders": [3, 5]}, {"period": 14, "orders": [5, 7]}, {"period": 21, "orders": [7, 10]}]
    macd_configs = [{"short": 12, "long": 26, "signal": 9, "orders": [3, 5]}, {"short": 9, "long": 21, "signal": 7, "orders": [5, 7]}]
    kdj_configs = [{"window": 9, "smooth": 3, "orders": [3, 5]}, {"window": 14, "smooth": 3, "orders": [5, 7]}]

    # Compute RSI-based divergence
    for cfg in rsi_configs:
        period, orders = cfg["period"], cfg["orders"]
        data[f'RSI_{period}'] = compute_rsi(data['Close'], period)
        maxima, minima = find_extrema_multi(data['Close'], orders)

        threshold = np.percentile(data[f'RSI_{period}'].diff().dropna(), 50)

        data[f'DIV_RSI_{period}'] = np.where(
            data.index.isin(data.index[maxima]) & (data[f'RSI_{period}'].diff() < -threshold), -1,
            np.where(
                data.index.isin(data.index[minima]) & (data[f'RSI_{period}'].diff() > threshold), 1,
                0
            )
        )

    # Compute MACD-based divergence
    for cfg in macd_configs:
        short, long, signal, orders = cfg.values()
        data[f'MACD_{short}_{long}'], data[f'Signal_{short}_{long}'] = compute_macd(data, short, long, signal)
        maxima, minima = find_extrema_multi(data['Close'], orders)

        threshold = np.percentile(data[f'MACD_{short}_{long}'].diff().dropna(), 50)

        data[f'DIV_MACD_{short}_{long}'] = np.where(
            data.index.isin(data.index[maxima]) & (data[f'MACD_{short}_{long}'].diff() < -threshold), -1,
            np.where(
                data.index.isin(data.index[minima]) & (data[f'MACD_{short}_{long}'].diff() > threshold), 1,
                0
            )
        )

    # Compute KDJ-based divergence
    for cfg in kdj_configs:
        window, smooth, orders = cfg.values()
        data[f'K_{window}'], data[f'D_{window}'], data[f'J_{window}'] = compute_kdj(data, window, smooth)
        maxima, minima = find_extrema_multi(data['Close'], orders)

        threshold = np.percentile(data[f'J_{window}'].diff().dropna(), 50)

        data[f'DIV_KDJ_{window}'] = np.where(
            data.index.isin(data.index[maxima]) & (data[f'J_{window}'].diff() < -threshold), -1,
            np.where(
                data.index.isin(data.index[minima]) & (data[f'J_{window}'].diff() > threshold), 1,
                0
            )
        )

    # Track current signals
    current_signals = {
        "Bullish Divergence": [],
        "Bearish Divergence": [],
        "RSI Crossover": []
    }

    # Check all divergence types
    for cfg in rsi_configs:
        period = cfg["period"]
        current_signals["Bullish Divergence"].extend(data.index[data[f'DIV_RSI_{period}'] == 1].tolist())
        current_signals["Bearish Divergence"].extend(data.index[data[f'DIV_RSI_{period}'] == -1].tolist())

    for cfg in macd_configs:
        short, long = cfg["short"], cfg["long"]
        current_signals["Bullish Divergence"].extend(data.index[data[f'DIV_MACD_{short}_{long}'] == 1].tolist())
        current_signals["Bearish Divergence"].extend(data.index[data[f'DIV_MACD_{short}_{long}'] == -1].tolist())

    for cfg in kdj_configs:
        window = cfg["window"]
        current_signals["Bullish Divergence"].extend(data.index[data[f'DIV_KDJ_{window}'] == 1].tolist())
        current_signals["Bearish Divergence"].extend(data.index[data[f'DIV_KDJ_{window}'] == -1].tolist())

    # Remove duplicates
    current_signals["Bullish Divergence"] = sorted(set(current_signals["Bullish Divergence"]))
    current_signals["Bearish Divergence"] = sorted(set(current_signals["Bearish Divergence"]))
    
    # Check RSI crossovers
    data['RSI_10'] = compute_rsi(data['Close'], period=10)
    data['RSI_20'] = compute_rsi(data['Close'], period=20)
    crossover_up = (data['RSI_10'] > data['RSI_20']) & (data['RSI_10'].shift(1) <= data['RSI_20'].shift(1))
    crossover_down = (data['RSI_10'] < data['RSI_20']) & (data['RSI_10'].shift(1) >= data['RSI_20'].shift(1))
    current_signals["RSI Crossover"] = data.index[crossover_up | crossover_down].tolist()

    # Plotting
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [2, 1]})
    
    # Configure axes to right side
    ax1.yaxis.tick_right()
    ax2.yaxis.tick_right()
    ax1.yaxis.set_label_position("right")
    ax2.yaxis.set_label_position("right")
    
    # Get current price and time
    current_price = data['Close'].iloc[-1]
    current_time = data.index[-1]
    
    # Price plot with dynamic coloring
    divergence_state = 0
    divergence_price = None
    price_colors = []
    
    for i in range(len(data)):
        # Check for any bullish divergence
        bullish = any(data[f'DIV_RSI_{cfg["period"]}'].iloc[i] == 1 for cfg in rsi_configs) or \
                 any(data[f'DIV_MACD_{cfg["short"]}_{cfg["long"]}'].iloc[i] == 1 for cfg in macd_configs) or \
                 any(data[f'DIV_KDJ_{cfg["window"]}'].iloc[i] == 1 for cfg in kdj_configs)
        
        # Check for any bearish divergence
        bearish = any(data[f'DIV_RSI_{cfg["period"]}'].iloc[i] == -1 for cfg in rsi_configs) or \
                  any(data[f'DIV_MACD_{cfg["short"]}_{cfg["long"]}'].iloc[i] == -1 for cfg in macd_configs) or \
                  any(data[f'DIV_KDJ_{cfg["window"]}'].iloc[i] == -1 for cfg in kdj_configs)
        
        if bullish:
            divergence_state = 1
            divergence_price = data['Close'].iloc[i]
        elif bearish:
            divergence_state = -1
            divergence_price = data['Close'].iloc[i]
        
        if divergence_state == 1:
            if data['Close'].iloc[i] < divergence_price:
                color = 'black'
                divergence_state = 0
            else:
                color = 'green'
        elif divergence_state == -1:
            if data['Close'].iloc[i] > divergence_price:
                color = 'black'
                divergence_state = 0
            else:
                color = 'red'
        else:
            color = 'black'
        
        price_colors.append(color)
    
    for i in range(1, len(data)):
        ax1.plot(data.index[i-1:i+1], data['Close'].iloc[i-1:i+1], color=price_colors[i])
    
    # Mark current price with dashed line and annotation
    ax1.axhline(y=current_price, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax1.annotate(f'{current_price:.4f} ({current_time.strftime("%H:%M")})', 
                xy=(1, current_price), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    # Mark divergences
    for cfg in rsi_configs:
        period = cfg["period"]
        ax1.scatter(data.index[data[f'DIV_RSI_{period}'] == 1], data['Close'][data[f'DIV_RSI_{period}'] == 1], 
                   color='green', marker='^', alpha=0.5, s=80, label=f'RSI {period} Bull' if period == 10 else "")
        ax1.scatter(data.index[data[f'DIV_RSI_{period}'] == -1], data['Close'][data[f'DIV_RSI_{period}'] == -1], 
                   color='red', marker='v', alpha=0.5, s=80, label=f'RSI {period} Bear' if period == 10 else "")

    for cfg in macd_configs:
        short, long = cfg["short"], cfg["long"]
        ax1.scatter(data.index[data[f'DIV_MACD_{short}_{long}'] == 1], data['Close'][data[f'DIV_MACD_{short}_{long}'] == 1], 
                   color='lime', marker='^', alpha=0.5, s=80, label=f'MACD {short}-{long} Bull' if short == 12 else "")
        ax1.scatter(data.index[data[f'DIV_MACD_{short}_{long}'] == -1], data['Close'][data[f'DIV_MACD_{short}_{long}'] == -1], 
                   color='darkred', marker='v', alpha=0.5, s=80, label=f'MACD {short}-{long} Bear' if short == 12 else "")

    for cfg in kdj_configs:
        window = cfg["window"]
        ax1.scatter(data.index[data[f'DIV_KDJ_{window}'] == 1], data['Close'][data[f'DIV_KDJ_{window}'] == 1], 
                   color='blue', marker='^', alpha=0.5, s=80, label=f'KDJ {window} Bull' if window == 9 else "")
        ax1.scatter(data.index[data[f'DIV_KDJ_{window}'] == -1], data['Close'][data[f'DIV_KDJ_{window}'] == -1], 
                   color='purple', marker='v', alpha=0.5, s=80, label=f'KDJ {window} Bear' if window == 9 else "")

    ax1.set_ylabel('Price')
    ax1.set_title(f'{symbol} Price with Multi Reversal Traps ({interval})', fontsize=12)
    ax1.grid(True, linestyle='--', alpha=0.7)
    #ax1.legend()
    
    # RSI plot
    ax2.plot(data.index, data['RSI_10'], color='blue', label='RSI 10')
    ax2.plot(data.index, data['RSI_20'], color='orange', label='RSI 20')
    
    # Mark current RSI value with dashed line
    current_rsi = data['RSI_10'].iloc[-1]
    ax2.axhline(y=current_rsi, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax2.annotate(f'{current_rsi:.2f}', 
                xy=(1, current_rsi), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    # Mark crossovers
    rsi_up = data[crossover_up]
    rsi_down = data[crossover_down]
    
    ax2.scatter(rsi_up.index, rsi_up['RSI_10'], color='green', marker='^', s=80, label='Bullish')
    ax2.scatter(rsi_down.index, rsi_down['RSI_10'], color='red', marker='v', s=80, label='Bearish')
    
    ax2.axhline(70, color='gray', linestyle='--', alpha=0.5)
    ax2.axhline(30, color='gray', linestyle='--', alpha=0.5)
    #ax2.set_title('RSI 10 vs RSI 20', fontsize=12)
    #ax2.legend()
    ax2.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    return fig, current_signals

# Strategy 3: Swing 3 (Advanced Multi-Indicator Divergence)
def swing_3(data):
    if data.empty:
        return plt.figure(), {}
    
    data = data.copy()
    
    # Compute RSI
    def compute_rsi(series, period=14):
        delta = series.diff()
        gain = pd.Series(np.where(delta > 0, delta, 0), index=series.index).rolling(window=period).mean()
        loss = pd.Series(np.where(delta < 0, -delta, 0), index=series.index).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    # Compute MACD
    def compute_macd(data, short=12, long=26, signal=9):
        macd_line = data['Close'].ewm(span=short, adjust=False).mean() - data['Close'].ewm(span=long, adjust=False).mean()
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line, signal_line

    # Compute KDJ
    def compute_kdj(data, window=14, smooth=3):
        low_min = data['Low'].rolling(window=window).min()
        high_max = data['High'].rolling(window=window).max()
        k = 100 * ((data['Close'] - low_min) / (high_max - low_min))
        d = k.rolling(window=smooth).mean()
        j = 3 * k - 2 * d
        return k, d, j

    # Compute CCI
    def compute_cci(data, window=30):
        tp = (data['High'] + data['Low'] + data['Close']) / 3  # Typical Price
        sma = tp.rolling(window=window).mean()
        mad = tp.rolling(window=window).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
        cci = (tp - sma) / (0.015 * mad)
        return cci

    # Compute Ehlers Fisher Transform
    def compute_ehlers_fisher_transform(data, period=32):
        midpoint = (data['High'] + data['Low']) / 2
        hh = midpoint.rolling(window=period).max()
        ll = midpoint.rolling(window=period).min()
        normalized = 0.66 * ((midpoint - ll) / (hh - ll) - 0.5)
        normalized = normalized.clip(-0.999, 0.999)
        fisher = 1 * np.log((1 + normalized) / (1 - normalized))
        fisher_smoothed = fisher.ewm(span=3, adjust=False).mean()
        return fisher, fisher_smoothed

    # Compute SMI Ergodic Indicator
    def compute_smi_ergodic(data, period=20, smooth_long=5, smooth_short=3):
        midpoint = (data['High'] + data['Low']) / 2
        price_change = midpoint.diff(period)
        momentum = midpoint - midpoint.shift(period)
        ergodic_line = momentum.ewm(span=smooth_long, adjust=False).mean()
        trigger_line = ergodic_line.ewm(span=smooth_short, adjust=False).mean()
        return ergodic_line, trigger_line

    # Compute Bias Indicator
    def compute_bias_indicator(data):
        rsi_bias = (data['RSI_14'] - 50) / 50
        macd_bias = data['MACD'] / (2 * data['MACD'].std())
        cci_bias = data['CCI'] / 200
        bias = 0.4 * rsi_bias + 0.3 * macd_bias + 0.3 * cci_bias
        bias_smoothed = bias.ewm(span=5, adjust=False).mean()
        return bias, bias_smoothed

    # Compute Inertia Indicator (Adaptive Momentum Strength)
    def compute_inertia_indicator(data, period=30, smooth=10):
        numerator = (data['Close'] - data['Open']).rolling(window=period).mean()
        denominator = (data['High'] - data['Low']).rolling(window=period).mean()
        rvi = numerator / denominator
        price_changes = data['Close'].diff()
        std_dev = price_changes.rolling(window=period).std()
        inertia = rvi * std_dev
        inertia_smoothed = inertia.ewm(span=smooth, adjust=False).mean()
        return inertia, inertia_smoothed

    # Find Local Extrema
    def find_extrema(series, order=70):
        maxima = argrelextrema(series.values, np.greater, order=order)[0]
        minima = argrelextrema(series.values, np.less, order=order)[0]
        return maxima, minima

    # Apply Calculations
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

    # Find Strong Extrema
    maxima, minima = find_extrema(data['Close'], order=30)

    # Compute Divergences
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

    # Calculate Divergence Score
    data['Divergence_Score'] = (
        data['DIV_RSI'].clip(-1, 1) +
        data['DIV_MACD'].clip(-1, 1) +
        data['DIV_KDJ'].clip(-1, 1) +
        data['DIV_CCI'])

    # Strong Divergences Only (Require at least 2 Confirmations)
    data["Potential_Divergence"] = (
        (data['DIV_RSI'] + data['DIV_MACD'] + data['DIV_KDJ']) >= 2).astype(int) - (
        (data['DIV_RSI'] + data['DIV_MACD'] + data['DIV_KDJ']) <= -2).astype(int)

    # Track divergence confirmation with RSI 10, Market Bias, and Ehlers Fisher (ALL must be satisfied)
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
            # Bullish confirmation requires ALL:
            # 1. RSI_10 >= 70
            # 2. Market Bias > 0
            # 3. Ehlers Fisher > 0
            if divergence_type == 1:
                rsi_confirm = data['RSI_10'].iloc[i] >= 70
                bias_confirm = data['Bias_Smoothed'].iloc[i] > 0
                fisher_confirm = data['Ehlers_Fisher_Smoothed'].iloc[i] > 0

                if rsi_confirm and bias_confirm and fisher_confirm:
                    data.at[data.index[divergence_start_idx], 'Confirmed_Divergence'] = 1
                    divergence_active = False

            # Bearish confirmation requires ALL:
            # 1. RSI_10 <= 30
            # 2. Market Bias < 0
            # 3. Ehlers Fisher < 0
            elif divergence_type == -1:
                rsi_confirm = data['RSI_10'].iloc[i] <= 30
                bias_confirm = data['Bias_Smoothed'].iloc[i] < 0
                fisher_confirm = data['Ehlers_Fisher_Smoothed'].iloc[i] < 0

                if rsi_confirm and bias_confirm and fisher_confirm:
                    data.at[data.index[divergence_start_idx], 'Confirmed_Divergence'] = -1
                    divergence_active = False

        # Cancel divergence if price moves against expected direction
        if divergence_active:
            if divergence_type == 1 and data['Close'].iloc[i] < data['Close'].iloc[divergence_start_idx]:
                divergence_active = False
            elif divergence_type == -1 and data['Close'].iloc[i] > data['Close'].iloc[divergence_start_idx]:
                divergence_active = False

    # Track divergence state and update price line color
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

    # Track RSI crossover state and update RSI 10 line color
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

    # Create figure with subplots
    fig = plt.figure(figsize=(12, 28))
    gs = fig.add_gridspec(8, 1, height_ratios=[2, 1, 1, 1, 1, 1, 1, 0.5])
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax3 = fig.add_subplot(gs[2])
    ax4 = fig.add_subplot(gs[3])
    ax5 = fig.add_subplot(gs[4])
    ax6 = fig.add_subplot(gs[5])
    ax7 = fig.add_subplot(gs[6])
    ax8 = fig.add_subplot(gs[7])

    # Configure all axes to right side
    for ax in [ax1, ax2, ax3, ax4, ax5, ax6, ax7, ax8]:
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")

    # Get current price and time
    current_price = data['Close'].iloc[-1]
    current_time = data.index[-1]

    # 1. Price Plot
    for i in range(1, len(data)):
        ax1.plot(data.index[i-1:i+1], data['Close'].iloc[i-1:i+1], color=price_line_colors[i], label=f'{symbol} Close Price' if i == 1 else "")
    
    # Mark current price with dashed line and annotation
    ax1.axhline(y=current_price, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax1.annotate(f'{current_price:.4f} ({current_time.strftime("%H:%M")})', 
                xy=(1, current_price), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    ax1.scatter(data.index[data['Confirmed_Divergence'] == 1], data['Close'][data['Confirmed_Divergence'] == 1],
                color='green', marker='^', label='Confirmed Bullish Divergence', s=100)
    ax1.scatter(data.index[data['Confirmed_Divergence'] == -1], data['Close'][data['Confirmed_Divergence'] == -1],
                color='red', marker='v', label='Confirmed Bearish Divergence', s=100)
    ax1.set_title(f'{symbol} Price with Confirmed Divergences (RSI + Bias + Fisher Confirmation)')
    ax1.legend()

    # 2. RSI Plot
    for i in range(1, len(data)):
        ax2.plot(data.index[i-1:i+1], data['RSI_10'].iloc[i-1:i+1], color=rsi_10_colors[i], label='RSI 10' if i == 1 else "")
    ax2.plot(data.index, data['RSI_22'], color='orange', label='RSI 22')
    
    # Mark current RSI value with dashed line
    current_rsi = data['RSI_10'].iloc[-1]
    ax2.axhline(y=current_rsi, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax2.annotate(f'{current_rsi:.2f}', 
                xy=(1, current_rsi), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    ax2.axhline(70, color='gray', linestyle='--', alpha=0.5)
    ax2.axhline(30, color='gray', linestyle='--', alpha=0.5)
    ax2.set_title('Timetion syma')
   # ax2.legend()

    # 3. CCI Plot
    ax3.plot(data.index, data['CCI'], color='blue', label='CCI (20)')
    
    # Mark current CCI value
    current_cci = data['CCI'].iloc[-1]
    ax3.axhline(y=current_cci, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax3.annotate(f'{current_cci:.2f}', 
                xy=(1, current_cci), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    ax3.axhline(100, color='red', linestyle='--', alpha=0.5)
    ax3.axhline(-100, color='green', linestyle='--', alpha=0.5)
    ax3.axhline(0, color='gray', linestyle='-', alpha=0.5)
    #ax3.set_title('Timetion Index')
    #ax3.legend()

    # 4. Ehlers Fisher Transform
    current_fisher = data['Ehlers_Fisher_Smoothed'].iloc[-1]
    ax4.plot(data.index, data['Ehlers_Fisher_Smoothed'], color='darkorange', label='Smoothed Ehlers Fisher Transform')
    
    # Mark current Fisher value
    ax4.axhline(y=current_fisher, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax4.annotate(f'{current_fisher:.2f}', 
                xy=(1, current_fisher), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    ax4.axhline(0.5, color='red', linestyle='--', alpha=0.5, label='Overbought Level')
    ax4.axhline(-0.5, color='green', linestyle='--', alpha=0.5, label='Oversold Level')
    ax4.axhline(0, color='gray', linestyle='-', alpha=0.5)
    ax4.set_title('Timetion FISHER')
    #ax4.legend()

    # 5. SMI Ergodic Indicator
    current_smi = data['SMI_Ergodic'].iloc[-1]
    ax5.plot(data.index, data['SMI_Ergodic'], color='blue', label='SMI Ergodic Line')
    ax5.plot(data.index, data['SMI_Trigger'], color='red', label='Trigger Line', alpha=0.7)
    
    # Mark current SMI value
    ax5.axhline(y=current_smi, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax5.annotate(f'{current_smi:.2f}', 
                xy=(1, current_smi), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    ax5.axhline(0, color='gray', linestyle='-', alpha=0.5)
    ax5.fill_between(data.index, data['SMI_Ergodic'], data['SMI_Trigger'],
                    where=data['SMI_Ergodic'] >= data['SMI_Trigger'],
                    facecolor='green', alpha=0.3, interpolate=True)
    ax5.fill_between(data.index, data['SMI_Ergodic'], data['SMI_Trigger'],
                    where=data['SMI_Ergodic'] < data['SMI_Trigger'],
                    facecolor='red', alpha=0.3, interpolate=True)
    ax5.set_title('Timetion ERG')
    ax5.axhline(0.01, color='red', linestyle='--', alpha=0.5, label='Overbought Level')
    ax5.axhline(-0.01, color='green', linestyle='--', alpha=0.5, label='Oversold Level')
    ax5.legend()

    # 6. Bias Indicator
    current_bias = data['Bias_Smoothed'].iloc[-1]
    ax6.plot(data.index, data['Bias'], color='gray', alpha=0.5, label='Raw Bias')
    ax6.plot(data.index, data['Bias_Smoothed'], color='purple', label='Smoothed Bias')
    
    # Mark current Bias value
    ax6.axhline(y=current_bias, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax6.annotate(f'{current_bias:.2f}', 
                xy=(1, current_bias), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    ax6.axhline(0.3, color='red', linestyle='--', alpha=0.5, label='Bullish Threshold')
    ax6.axhline(-0.3, color='green', linestyle='--', alpha=0.5, label='Bearish Threshold')
    ax6.axhline(0, color='black', linestyle='-', alpha=0.5)
    ax6.fill_between(data.index, data['Bias_Smoothed'], 0.2,
                    where=data['Bias_Smoothed'] >= 0.2,
                    facecolor='green', alpha=0.2, interpolate=True)
    ax6.fill_between(data.index, data['Bias_Smoothed'], -0.2,
                    where=data['Bias_Smoothed'] <= -0.2,
                    facecolor='red', alpha=0.2, interpolate=True)
    ax6.set_title('Timetion Bias')
    ax6.legend()

    # 7. Inertia Indicator (Adaptive Momentum Strength)
    current_inertia = data['Inertia_Smoothed'].iloc[-1]
    ax7.plot(data.index, data['Inertia'], color='gray', alpha=0.5, label='Raw Inertia')
    ax7.plot(data.index, data['Inertia_Smoothed'], color='blue', label='Smoothed Inertia')
    
    # Mark current Inertia value
    ax7.axhline(y=current_inertia, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax7.annotate(f'{current_inertia:.2f}', 
                xy=(1, current_inertia), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    ax7.axhline(0, color='black', linestyle='-', alpha=0.5)
    ax7.fill_between(data.index, data['Inertia_Smoothed'], 0,
                    where=data['Inertia_Smoothed'] >= 0,
                    facecolor='green', alpha=0.2, interpolate=True)
    ax7.fill_between(data.index, data['Inertia_Smoothed'], 0,
                    where=data['Inertia_Smoothed'] < 0,
                    facecolor='red', alpha=0.2, interpolate=True)
    ax7.set_title('Timetion Inertia SAYO')
    ax7.legend()

    # 8. Divergence Score
    current_score = data['Divergence_Score'].iloc[-1]
    ax8.bar(data.index, data['Divergence_Score'],
             color=np.where(data['Divergence_Score'] > 0, 'green', 'red'),
             width=0.8, alpha=0.7)
    
    # Mark current Divergence Score
    ax8.axhline(y=current_score, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax8.annotate(f'{current_score:.2f}', 
                xy=(1, current_score), 
                xycoords=('axes fraction', 'data'),
                xytext=(5, 0), 
                textcoords='offset points',
                color='blue',
                va='center',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    ax8.axhline(3, color='green', linestyle='--', alpha=0.3)
    ax8.axhline(-3, color='red', linestyle='--', alpha=0.3)
    ax8.axhline(0, color='gray', linestyle='-', alpha=0.5)
    ax8.set_title('Timetion Elta')

    # Highlight strong divergence signals
    strong_bullish = data['Divergence_Score'] >= 3
    strong_bearish = data['Divergence_Score'] <= -3
    ax8.scatter(data.index[strong_bullish], data['Divergence_Score'][strong_bullish],
                 color='lime', marker='o', s=50, label='Strong Bullish')
    ax8.scatter(data.index[strong_bearish], data['Divergence_Score'][strong_bearish],
                 color='darkred', marker='o', s=50, label='Strong Bearish')
    ax8.legend()

    plt.tight_layout()
    
    # Track current signals
    current_signals = {
        "Bullish Divergence": data.index[data['Confirmed_Divergence'] == 1].tolist(),
        "Bearish Divergence": data.index[data['Confirmed_Divergence'] == -1].tolist(),
        "RSI Crossover": []
    }
    
    # Check RSI crossovers
    crossover_up = (data['RSI_10'] > data['RSI_22']) & (data['RSI_10'].shift(1) <= data['RSI_22'].shift(1))
    crossover_down = (data['RSI_10'] < data['RSI_22']) & (data['RSI_10'].shift(1) >= data['RSI_22'].shift(1))
    current_signals["RSI Crossover"] = data.index[crossover_up | crossover_down].tolist()
    
    return fig, current_signals

# Main app display
def main_display():
    st.header(f"{symbol} ({interval})")
    
    # Initialize SSE client if needed
    if live_update and st.session_state.sse_client is None:
        st.session_state.sse_client = SSEClient(api_key, symbol, interval, lookback)
        st.session_state.sse_client.start()
    
    # Get data based on update mode
    if live_update:
        # Check for SSE updates
        update = st.session_state.sse_client.get_update()
        if update:
            st.session_state.last_data = update_data_with_sse(
                st.session_state.last_data,
                update
            )
        data = st.session_state.last_data if st.session_state.last_data is not None else load_initial_data(symbol, interval, lookback, api_key)
    else:
        # Stop SSE if running
        if st.session_state.sse_client is not None:
            st.session_state.sse_client.stop()
            st.session_state.sse_client = None
        
        # Load regular data
        data = load_initial_data(symbol, interval, lookback, api_key)
        st.session_state.last_data = data
    
    if data.empty:
        st.warning("No data available - check your API key and symbol")
        return
    
    # Strategy display
    if page == "Short Swing 1":
        fig, current_signals = short_swing_1(data)
    elif page == "Short Swing 2":
        fig, current_signals = short_swing_2(data)
    elif page == "Swing 3":
        fig, current_signals = swing_3(data)
    
    # Display the chart with WebP compression
    img_buf = compress_image(fig)
    st.image(img_buf, use_column_width=True)
    plt.close(fig)  # Free memory
    
    # Check for new signals and trigger alerts
    if alert_enabled and live_update:
        new_signals = check_for_new_signals(current_signals)
        for signal_type, timestamps in new_signals.items():
            if signal_type in alert_types:
                for ts in timestamps:
                    trigger_alert(signal_type, data.loc[ts, 'Close'], ts)
    
    # Update previous signals
    st.session_state.previous_signals = current_signals
    
    # Display status
    st.caption(f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {len(data)} bars loaded")
    
    # Display recent alerts
    st.sidebar.title("Alert History")
    with st.sidebar.container():
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
placeholder = st.empty()

while True:
    with placeholder.container():
        main_display()
    
    if not live_update:
        st.stop()
    
    time.sleep(max(update_interval, 15))  # Minimum 15s refresh

if __name__ == "__main__":
    main_display()
