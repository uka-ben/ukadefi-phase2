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

def compress_image(fig, quality=60):
    png_buf = io.BytesIO()
    fig.savefig(png_buf, format='png', dpi=50)
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
st.write("Developed with ❤️ by **Uka Benjamin Imo**  **[+2347067193071]** **benjaminukaimo@gmail.com**") 
image1 = Image.open("mypiclogo.png")
st.image(image1)
st.markdown(" ")
st.subheader("VAPS 0.2 - Financial Market Modelling")

st.markdown("**A Financial AI System Based on Void Anti-symmetric Pattern Synthesizer for Market Dynamics.**")

# Input controls
col1, col2, col3 = st.columns(3)
with col1:
        symbol = st.selectbox("Symbol", ["BTC","SOL", "ETH", "TRX", "ADA",  "BCH", "PEOPLE", "IOTX", "POL","ATOM", "C98", "AAVE","DOT","MANA","CAKE", "XRP","ALICE", "BNB", "EOS", "ONE","ENJ","NEAR","VTHO","TRUMP","JST","ETC","STX","MBOX","SAND","UNI","DYDX","RUNE","DENT", "SHIB", "DOGE", "HOT", "CELR", "VET", "XLM", "ALGO", "GBP", "AUD","XAU", "EUR",])
with col2:
    interval = st.selectbox("Interval", ["1h", "15min", "5min", "30min",  "4h", "1day", "1week", "1month"])
with col3:
    market_type = st.selectbox("Market Type", ["Forex", "Crypto", "Stock"], index=0)

# Sidebar controls
st.sidebar.title("Controls")
live_update = st.sidebar.checkbox("Live Update", True)
lookback = st.slider("Lookback Period (bars)", 50, 1000, 250)
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
    st.session_state.description_shown = False

# [Rest of your technical indicator functions...]
# [Keep all your existing technical functions exactly as they were...]

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

    # Use a dedicated container for the chart
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

    # Description section - only shown once
    if not st.session_state.description_shown:
        with st.expander("About VAPS 0.2", expanded=True):
            st.markdown("""
            **Professional Version Features:**
            - Real-time multi-asset monitoring
            - Advanced pattern recognition
            - Customizable alert systems
            - Institutional-grade analytics
            
            **Applications Beyond Finance:**
            - Fraud detection systems
            - Predictive maintenance
            - AI-driven diagnostics
            
            **Contact for full version:**  
            📧 benjaminukaimo@gmail.com  
            📞 +2347067193071 (WhatsApp)
            """)
        st.session_state.description_shown = True

    # Alert history in sidebar
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

    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    **Disclaimer:**  
    Trial version - contact for commercial licensing.
    """)

# Run the app
if __name__ == "__main__":
    placeholder = st.empty()
    
    while True:
        with placeholder.container():
            main_display()
            
            if st.session_state.get('force_refresh', False):
                st.session_state.force_refresh = False
                st.session_state.loading = True
                st.rerun()

        if not live_update:
            break

        time.sleep(max(update_interval, 30))