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

# Apply custom CSS for enhanced background and lighter sidebar color
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background: linear-gradient(white,blue, blue);
    color: white;
}
[data-testid="stSidebar"] {
    background: linear-gradient(skyblue, blue) !important;
    color: white;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: white;
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

def compress_image(fig, quality=85):
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
st.title("Phase 2-financial modelling")

st.markdown("**UKADEFI** is a powerful system with several phases. ukadefi can offer solution to problems involving **time series, fraud detection,robotics,decisioning, robotics**, etc.")
st.markdown("**Here UKADEFI** system applied to financial trading.")

# Input controls
symbol = st.text_input("Symbol.. EUR,BTC,ETH,AAPL,etc", "EUR").upper()
interval = st.selectbox("Interval", ["1min", "5min", "30min", "1h", "4h", "1day", "1week", "1month"])

# Sidebar controls
st.sidebar.title("Controls")
page = st.radio(
    "Select Strategy", 
    ["Wide Swing 1", "Wide Swing 2", "Short Swing 1", "Short Swing 2"],
    index=0, horizontal=True
)

# API Configuration
api_key = "cef197ce3e054ee69d6c795401b229cd"

# Live update controls
live_update = st.sidebar.checkbox("Live Chat Update", True)
lookback = st.sidebar.slider("Chat Lookback Period (bars)", 50, 1000, 300)
update_interval = st.sidebar.slider("Live Update Interval (seconds)", 15, 300, 30)

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

# Strategy 1: Wide Swing 1
def wide_swing_1(data):
    if data.empty:
        return plt.figure(), {}
    
    data = data.copy()
    data['RSI_14'] = compute_rsi(data['Close'])
    data['RSI_10'] = compute_rsi(data['Close'], period=10)
    data['RSI_22'] = compute_rsi(data['Close'], period=22)
    data['MACD'], data['Signal'] = compute_macd(data)
    data['K'], data['D'], data['J'] = compute_kdj(data)

    maxima, minima = find_extrema(data['Close'], order=60)

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
    crossover_up = (data['RSI_10'] > data['RSI_22']) & (data['RSI_10'].shift(1) <= data['RSI_22'].shift(1))
    crossover_down = (data['RSI_10'] < data['RSI_22']) & (data['RSI_10'].shift(1) >= data['RSI_22'].shift(1))
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

    # Mark current price with dashed line
    ax1.axhline(y=current_price, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    ax1.annotate(f'{current_price:.4f}\n{current_time.strftime("%H:%M:%S")}', 
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
    
    ax1.set_title(f'{symbol} Price with Reversal Traps ({interval})', fontsize=12)
    ax1.legend(loc='upper left')
    ax1.grid(True, linestyle='--', alpha=0.7)
    
    # RSI plot with dynamic coloring
    rsi_crossover_state = 0
    rsi_colors = []
    
    for i in range(len(data)):
        if data['RSI_10'].iloc[i] > data['RSI_22'].iloc[i] and (i == 0 or data['RSI_10'].iloc[i-1] <= data['RSI_22'].iloc[i-1]):
            rsi_crossover_state = 1
        elif data['RSI_10'].iloc[i] < data['RSI_22'].iloc[i] and (i == 0 or data['RSI_10'].iloc[i-1] >= data['RSI_22'].iloc[i-1]):
            rsi_crossover_state = -1
        
        if rsi_crossover_state == 1:
            if price_colors[i] == 'green':
                rsi_colors.append('green')
            else:
                rsi_colors.append('gray')
        elif rsi_crossover_state == -1:
            if price_colors[i] == 'red':
                rsi_colors.append('green')
            else:
                rsi_colors.append('gray')
        else:
            rsi_colors.append('gray')
    
    for i in range(1, len(data)):
        ax2.plot(data.index[i-1:i+1], data['RSI_10'].iloc[i-1:i+1], color=rsi_colors[i])
    
    ax2.plot(data.index, data['RSI_22'], color='red', label='RSI 22')
    
    # Mark current RSI value
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
    
    ax2.scatter(rsi_up.index, rsi_up['RSI_10'], color='blue', marker='^', s=80)
    ax2.scatter(rsi_down.index, rsi_down['RSI_10'], color='orange', marker='v', s=80)
    
    ax2.axhline(70, color='gray', linestyle='--', alpha=0.5)
    ax2.axhline(30, color='gray', linestyle='--', alpha=0.5)
    ax2.set_title('Market Twist', fontsize=12)
    ax2.legend(loc='upper left')
    ax2.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    return fig, current_signals

# Strategy 2: Wide Swing 2
def wide_swing_2(data):
    if data.empty:
        return plt.figure(), {}
    
    data = data.copy()
    data['RSI_14'] = compute_rsi(data['Close'])
    data['RSI_7'] = compute_rsi(data['Close'], period=7)
    data['RSI_21'] = compute_rsi(data['Close'], period=21)
    data['MACD'], data['Signal'] = compute_macd(data)
    data['K'], data['D'], data['J'] = compute_kdj(data)

    maxima, minima = find_extrema(data['Close'], order=60)
    
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
    
    # Track signals
    current_signals = {
        "Bullish Divergence": data.index[data['Final_Divergence'] == 1].tolist(),
        "Bearish Divergence": data.index[data['Final_Divergence'] == -1].tolist(),
        "RSI Crossover": []
    }
    
    # Check RSI crossovers
    crossover_up = (data['RSI_7'] > data['RSI_21']) & (data['RSI_7'].shift(1) <= data['RSI_21'].shift(1))
    crossover_down = (data['RSI_7'] < data['RSI_21']) & (data['RSI_7'].shift(1) >= data['RSI_21'].shift(1))
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
    
    ax1.set_title(f'{symbol} Price with Divergences ({interval})', fontsize=12)
    ax1.legend(loc='upper left')
    ax1.grid(True, linestyle='--', alpha=0.7)
    
    # RSI plot
    ax2.plot(data.index, data['RSI_7'], color='blue', label='RSI 7')
    ax2.plot(data.index, data['RSI_21'], color='orange', label='RSI 21')
    
    # Mark current RSI value with dashed line
    current_rsi = data['RSI_7'].iloc[-1]
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
    
    ax2.scatter(rsi_up.index, rsi_up['RSI_7'], color='green', marker='^', s=80, label='Bullish Crossover')
    ax2.scatter(rsi_down.index, rsi_down['RSI_7'], color='red', marker='v', s=80, label='Bearish Crossover')
    
    ax2.axhline(70, color='gray', linestyle='--', alpha=0.5)
    ax2.axhline(30, color='gray', linestyle='--', alpha=0.5)
    ax2.set_title('RSI 7 vs RSI 21', fontsize=12)
    ax2.legend(loc='upper left')
    ax2.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    return fig, current_signals

# Main app display
def main_display():

    #st.markdown('<div class="background">', unsafe_allow_html=True)


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
    if page == "Wide Swing 1":
        fig, current_signals = wide_swing_1(data)
    elif page == "Wide Swing 2":
        fig, current_signals = wide_swing_2(data)
    elif page == "Short Swing 1":
        fig, current_signals = short_swing_1(data)
