import streamlit as st
import numpy as np 
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import requests
from scipy.signal import argrelextrema
import time  
from datetime import datetime, timezone
import brotli
import threading
import queue
import json
from PIL import Image
import io
import base64

# Configure page layout and style with larger fonts
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
    font-size: 1.5rem !important;
}
footer {
    visibility: hidden;
}
header {
    visibility: hidden;
}
body {
    font-family: "Source Sans Pro", sans-serif;
    font-size: 1.2rem !important;
}
.stButton>button {
    background-color: blue;
    color: white;
    font-size: 1.3rem !important;
    border-radius: 8px;
    padding: 12px 28px;
    border: none;
    cursor: pointer;
    transition: background-color 0.3s ease;
}
.stButton>button:hover {
    background-color: #45a804;
}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    color: #2c3e50;
    font-size: 2rem !important;
}
.stDataFrame {
    border-radius: 8px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}
.stProgress > div > div > div {
    background-color: #4CAF50;
}
.loading-spinner {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 300px;
    font-size: 2.5rem !important;
    font-weight: bold;
    color: #2c3e50;
}
.stAlert {
    font-size: 1.3rem !important;
}
.stToast {
    font-size: 1.5rem !important;
}
.stCaption {
    font-size: 1.3rem !important;
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

def compress_image(fig, quality=100):
    png_buf = io.BytesIO()
    fig.savefig(png_buf, format='png', dpi=150)  # Increased DPI for better quality
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
        url = f"https://api.twelvedata.com/timeseries?apikey={self.api_key}&symbol={self.symbol}/USD&type=etf&timezone=UTC&interval={self.interval}"
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

# App header and info with larger fonts
st.write("Developed with ❤️ by **Uka Benjamin Imo**  **[+234............]** **benjaminukaimo@gmail.com**") 
image1 = Image.open("mypiclogo.png")
st.image(image1)
st.markdown(" ")
st.subheader("VAPS 0.2 - Financial Market Modelling")

st.markdown("**A Financial AI System Based on Void Anti-symmetric Pattern Synthesizer for Market Dynamics.**")

# Input controls with larger fonts
col1, col2, col3 = st.columns(3)
with col1:
    symbol = st.selectbox("Symbol", ["TRX", "ADA", "BTC", "BCH", "PEOPLE", "ETH", "IOTX", "SOL", "POL","ATOM", "C98", "AAVE","DOT","MANA","CAKE", "XRP","ALICE", "BNB", "EOS", "ONE", "SHIB", "DOGE", "HOT", "CELR", "VET", "XLM", "ALGO", "XAU", "EUR", "GBP", "AUD"])
with col2:
    interval = st.selectbox("Interval", ["15min","1min", "5min", "30min", "1h",  "4h", "1day", "1week", "1month"])
with col3:
    market_type = st.selectbox("Market Type", ["Forex", "Crypto", "Stock"], index=0)

# Sidebar controls with larger fonts
st.sidebar.title("Controls")
live_update = st.sidebar.checkbox("Live Update", True)
lookback = st.sidebar.slider("Lookback Period (bars)", 50, 1000, 300)
update_interval = st.sidebar.slider("Update Interval (seconds)", 5, 300, 10)

# Alert configuration with larger fonts
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
    st.session_state.last_update_time = None
    st.session_state.chart_placeholder = None
    st.session_state.loading = True

# Technical indicator functions (unchanged)
# ... [keep all your technical indicator functions the same] ...

def create_plot(data, price_line_colors, rsi_10_colors, symbol, interval, market_type):
    visible_indicators = ["RSI", "Fisher", "Bias", "Divergence"]
    num_plots = 1 + len(visible_indicators)

    # Increased dimensions for better visibility
    width = 36  # Very wide
    height_per_plot = 14  # Taller individual plots
    height = height_per_plot * num_plots  # Total height

    fig = Figure(figsize=(width, height), dpi=100)
    gs = fig.add_gridspec(num_plots, 1, height_ratios=[15] + [6]*len(visible_indicators))

    axes = [fig.add_subplot(gs[0])]
    for i in range(1, num_plots):
        axes.append(fig.add_subplot(gs[i], sharex=axes[0]))

    # Configure all axes with larger fonts and thicker lines
    for ax in axes:
        ax.tick_params(axis='both', which='major',
                      labelsize=38, width=4, length=10, pad=12)  # Increased sizes
        ax.tick_params(axis='both', which='minor',
                      labelsize=36, width=3, length=6, pad=10)

        for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] +
                     ax.get_xticklabels() + ax.get_yticklabels()):
            item.set_fontweight('bold')
            item.set_fontsize(38)  # Larger font size
            item.set_fontstyle('normal')

        ax.grid(True, linestyle='-', linewidth=2.5, alpha=0.7)  # Thicker grid lines
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_linewidth(3)  # Thicker bottom spine
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")

    current_price = data['Close'].iloc[-1]
    current_time = data.index[-1].strftime('%H:%M UTC')

    # Plot price with thicker lines
    for i in range(1, len(data)):
        axes[0].plot(data.index[i-1:i+1], data['Close'].iloc[i-1:i+1],
                    color=price_line_colors[i],
                    linewidth=6.0,  # Thicker price line
                    alpha=1.0,
                    solid_capstyle='round')

    # Larger markers for divergences
    axes[0].scatter(data.index[data['Confirmed_Divergence'] == 1],
                   data['Close'][data['Confirmed_Divergence'] == 1],
                   color='green', marker='^', s=300,  # Larger markers
                   edgecolor='black', linewidth=3,  # Thicker borders
                   label='Bullish Div')
    axes[0].scatter(data.index[data['Confirmed_Divergence'] == -1],
                   data['Close'][data['Confirmed_Divergence'] == -1],
                   color='red', marker='v', s=300,  # Larger markers
                   edgecolor='black', linewidth=3,  # Thicker borders
                   label='Bearish Div')

    # Current price line with larger text
    axes[0].axhline(y=current_price, color='blue', linestyle='--', alpha=0.7, linewidth=5.0)
    axes[0].text(0.02, 0.95, f'{current_price:.5f} ({current_time})',
                transform=axes[0].transAxes,
                color='blue',
                fontsize=42,  # Larger font
                fontweight='bold',
                va='top',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='blue', linewidth=3, pad=8))

    axes[0].set_title(f'{market_type}: {symbol} ({interval})',
                     fontsize=44,  # Larger title
                     fontweight='bold',
                     pad=25)
    axes[0].grid(True, linestyle='-', alpha=0.7, linewidth=3.0)

    plot_idx = 1

    # RSI Plot with thicker lines
    for i in range(1, len(data)):
        axes[plot_idx].plot(data.index[i-1:i+1], data['RSI_10'].iloc[i-1:i+1],
                          color=rsi_10_colors[i],
                          linewidth=5.0,  # Thicker line
                          alpha=1.0,
                          solid_capstyle='round',
                          label='RSI 10' if i == 1 else "")
    axes[plot_idx].plot(data.index, data['RSI_22'],
                       color='orange',
                       linewidth=5.0,  # Thicker line
                       alpha=1.0,
                       label='RSI 22')

    current_rsi = data['RSI_10'].iloc[-1]
    axes[plot_idx].axhline(y=current_rsi, color='blue', linestyle='--', alpha=1.0, linewidth=5.0)
    axes[plot_idx].annotate(f'{current_rsi:.2f}',
                          xy=(0.98, current_rsi),
                          xycoords=('axes fraction', 'data'),
                          xytext=(-15, 0),  # More offset
                          textcoords='offset points',
                          color='blue',
                          fontsize=38,  # Larger font
                          fontweight='bold',
                          va='center',
                          ha='right',
                          bbox=dict(facecolor='white', alpha=0.8, edgecolor='black', linewidth=2, pad=6))

    axes[plot_idx].axhline(70, color='gray', linestyle='--', alpha=1.0, linewidth=3.5)
    axes[plot_idx].axhline(30, color='gray', linestyle='--', alpha=1.0, linewidth=3.5)
    axes[plot_idx].set_title('STRENGTH INDICATOR',
                           fontsize=40,  # Larger title
                           fontweight='bold',
                           pad=20)
    plot_idx += 1

    # Fisher Transform with thicker lines
    axes[plot_idx].plot(data.index, data['Ehlers_Fisher_Smoothed'],
                       color='darkorange',
                       linewidth=6.0,  # Thicker line
                       alpha=1.0,
                       solid_capstyle='round',
                       label='Fisher Transform')
    axes[plot_idx].axhline(0.5, color='red', linestyle='--', alpha=1.0, linewidth=2.5)
    axes[plot_idx].axhline(-0.5, color='green', linestyle='--', alpha=1.0, linewidth=2.5)
    axes[plot_idx].axhline(0, color='black', linestyle='-', alpha=1.0, linewidth=2.0)
    axes[plot_idx].set_title('FISHER TRANSFORMATION',
                           fontsize=40,  # Larger title
                           fontweight='bold',
                           pad=20)
    plot_idx += 1

    # Bias Indicator with thicker lines
    axes[plot_idx].plot(data.index, data['Bias'],
                       color='gray',
                       linewidth=5.0,  # Thicker line
                       alpha=0.7,
                       label='Raw Bias')
    axes[plot_idx].plot(data.index, data['Bias_Smoothed'],
                       color='purple',
                       linewidth=6.0,  # Thicker line
                       alpha=1.0,
                       solid_capstyle='round',
                       label='Smoothed Bias')
    axes[plot_idx].axhline(0.3, color='red', linestyle='--', alpha=1.0, linewidth=2.5)
    axes[plot_idx].axhline(-0.3, color='green', linestyle='--', alpha=1.0, linewidth=2.5)
    axes[plot_idx].axhline(0, color='black', linestyle='-', alpha=1.0, linewidth=2.0)

    axes[plot_idx].fill_between(data.index, data['Bias_Smoothed'], 0.2,
                              where=data['Bias_Smoothed'] >= 0.2,
                              facecolor='green', alpha=0.3, interpolate=True)
    axes[plot_idx].fill_between(data.index, data['Bias_Smoothed'], -0.2,
                              where=data['Bias_Smoothed'] <= -0.2,
                              facecolor='red', alpha=0.3, interpolate=True)
    axes[plot_idx].set_title('MARKET BIAS INDICATOR',
                           fontsize=40,  # Larger title
                           fontweight='bold',
                           pad=20)
    plot_idx += 1

    # Divergence Score with thicker bars
    bar_width = 1.5 * (data.index[1] - data.index[0]).total_seconds() / (24 * 3600)  # Wider bars
    axes[plot_idx].bar(data.index, data['Divergence_Score'],
                      color=np.where(data['Divergence_Score'] > 0, 'green', 'red'),
                      width=bar_width,
                      alpha=0.7,
                      edgecolor='black',
                      linewidth=2.0)  # Thicker bar borders

    axes[plot_idx].axhline(3, color='green', linestyle='--', alpha=1.0, linewidth=2.5)
    axes[plot_idx].axhline(-3, color='red', linestyle='--', alpha=1.0, linewidth=2.5)
    axes[plot_idx].axhline(0, color='black', linestyle='-', alpha=1.0, linewidth=2.0)

    strong_bullish = data['Divergence_Score'] >= 3
    strong_bearish = data['Divergence_Score'] <= -3
    axes[plot_idx].scatter(data.index[strong_bullish], data['Divergence_Score'][strong_bullish],
                         color='lime', marker='o', s=150,  # Larger markers
                         edgecolor='black', linewidth=3.0,  # Thicker borders
                         label='Strong Bullish')
    axes[plot_idx].scatter(data.index[strong_bearish], data['Divergence_Score'][strong_bearish],
                         color='darkred', marker='o', s=150,  # Larger markers
                         edgecolor='black', linewidth=3.0,  # Thicker borders
                         label='Strong Bearish')
    axes[plot_idx].set_title('ANTI-SYMMETRIC BIDIVERGENCE SCORE',
                           fontsize=40,  # Larger title
                           fontweight='bold',
                           pad=20)

    fig.tight_layout(pad=4.0, h_pad=3.0, w_pad=3.0)  # More padding
    fig.subplots_adjust(top=0.94, right=0.95)

    webp_buf = compress_image(fig)
    plt.close(fig)

    return webp_buf

# ... [keep the rest of your functions the same] ...

def main_display():
    st.header(f"{symbol} ({interval}) Analysis")
    
    # Add larger refresh button
    if st.button("🔄 Refresh Chart", key="refresh_button"):
        st.session_state.last_data = None
        st.session_state.loading = True
        st.rerun()

    if st.session_state.loading:
        with st.spinner("Please wait, the anti-symmetric synthesizer is working..."):
            time.sleep(2)
        st.session_state.loading = False

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

    # Create a placeholder for the chart
    if 'chart_placeholder' not in st.session_state:
        st.session_state.chart_placeholder = st.empty()

    fig_buf, current_signals = swing_3(data)
    
    # Update the chart in the placeholder
    with st.session_state.chart_placeholder.container():
        st.image(fig_buf, use_column_width=True)

    if alert_enabled and live_update:
        new_signals = check_for_new_signals(current_signals)
        for signal_type, timestamps in new_signals.items():
            if signal_type in alert_types:
                for ts in timestamps:
                    trigger_alert(signal_type, data.loc[ts, 'Close'], ts)

    st.session_state.previous_signals = current_signals

    # Use UTC time consistently with larger font
    current_utc_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    st.markdown(f"<p style='font-size: 1.4rem;'>Last update: {current_utc_time} | {len(data)} bars loaded</p>", unsafe_allow_html=True)

    with st.sidebar.expander("Recent Alerts", expanded=True):
        for alert in reversed(st.session_state.alert_history[-10:]):
            cols = st.columns([1, 2, 1])
            cols[0].markdown(f"<p style='font-size: 1.2rem;'>{alert['timestamp'].strftime('%H:%M:%S')}</p>", unsafe_allow_html=True)

            if alert['type'] == "Bullish Divergence":
                cols[1].success(f"<p style='font-size: 1.2rem;'>{alert['type']}</p>", unsafe_allow_html=True)
            elif alert['type'] == "Bearish Divergence":
                cols[1].error(f"<p style='font-size: 1.2rem;'>{alert['type']}</p>", unsafe_allow_html=True)
            else:
                cols[1].warning(f"<p style='font-size: 1.2rem;'>{alert['type']}</p>", unsafe_allow_html=True)

            cols[2].markdown(f"<p style='font-size: 1.2rem;'>{alert['price']:.4f}</p>", unsafe_allow_html=True)

# Run the app
if __name__ == "__main__":
    while True:
        main_display()
        
        if not live_update:
            st.stop()
            
        time.sleep(max(update_interval, 5))