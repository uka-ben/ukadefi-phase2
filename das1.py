# trading_strategy_v5e.py
# Version 5e – bias‑adaptive ATR + SSE live streaming + image compression + auto‑refresh.

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from scipy.signal import argrelextrema
import time
import threading
import queue
import json
import io
from PIL import Image
import warnings
warnings.filterwarnings('ignore')

# ========== Streamlit UI config ==========
st.set_page_config(page_title="Trading Strategy v5e", layout="wide")
st.title("📈 Swing 3 Strategy – Bias‑Adaptive ATR (Live)")

# ========== Compression ==========
def compress_image(fig, quality=75, dpi=80):
    png_buf = io.BytesIO()
    fig.savefig(png_buf, format='png', dpi=dpi, bbox_inches='tight')
    png_buf.seek(0)
    img = Image.open(png_buf)
    webp_buf = io.BytesIO()
    img.save(webp_buf, format='webp', quality=quality)
    webp_buf.seek(0)
    return webp_buf

# ========== SSE Client ==========
class SSEClient:
    def __init__(self, api_key, symbol, interval):
        self.api_key = api_key
        self.symbol = symbol
        self.interval = interval
        self.event_queue = queue.Queue()
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)

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
                                self.event_queue.put(event_data)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            st.error(f"SSE Error: {str(e)}")

    def get_update(self):
        try:
            return self.event_queue.get_nowait()
        except queue.Empty:
            return None

# ========== Technical Indicators ==========
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

def compute_atr(data, period=14):
    high = data['High']; low = data['Low']; close = data['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def compute_tsi(data, long=25, short=13):
    diff = data['Close'].diff()
    ema_short = diff.ewm(span=short, adjust=False).mean()
    ema_short_abs = diff.abs().ewm(span=short, adjust=False).mean()
    ema_long = ema_short.ewm(span=long, adjust=False).mean()
    ema_long_abs = ema_short_abs.ewm(span=long, adjust=False).mean()
    return 100 * (ema_long / ema_long_abs)

def compute_aroon(data, period=25):
    high = data['High']; low = data['Low']
    def aroon_calc(series, period):
        return 100 * (period - series.rolling(window=period).apply(
            lambda x: period - x.argmax() - 1 if not x.isnull().all() else 0)) / period
    aroon_up = aroon_calc(high, period)
    aroon_down = aroon_calc(low, period)
    return aroon_up - aroon_down

def find_extrema(series, order=30):
    maxima = argrelextrema(series.values, np.greater, order=order)[0]
    minima = argrelextrema(series.values, np.less, order=order)[0]
    return maxima, minima

# ========== Data Loading ==========
@st.cache_data(ttl=60)
def load_market_data(symbol, interval, lookback, api_key):
    try:
        url = f"https://api.twelvedata.com/time_series?apikey={api_key}&interval={interval}&symbol={symbol}/USD&type=etf&timezone=Africa/Lagos&outputsize={lookback}"
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return pd.DataFrame()
        data = response.json()
        if 'values' not in data:
            return pd.DataFrame()
        df = pd.DataFrame(data['values'])
        df = df.rename(columns={'datetime':'Date','open':'Open','close':'Close','high':'High','low':'Low','volume':'Volume'})
        df['Date'] = pd.to_datetime(df['Date'])
        numeric_cols = df.columns.drop('Date')
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        df = df.sort_values('Date').reset_index(drop=True)
        df = df.iloc[-lookback:]
        df.index = df['Date']
        return df
    except Exception:
        return pd.DataFrame()

def update_data_with_sse(prev_df, new_point):
    if prev_df is None or prev_df.empty:
        return prev_df
    new_row = {
        'Date': pd.to_datetime(new_point['timestamp']),
        'Open': float(new_point['open']),
        'High': float(new_point['high']),
        'Low': float(new_point['low']),
        'Close': float(new_point['close']),
    }
    if 'volume' in new_point:
        new_row['Volume'] = float(new_point['volume'])
    elif 'Volume' in prev_df.columns:
        new_row['Volume'] = 0
    new_df = pd.DataFrame([new_row])
    updated = pd.concat([prev_df, new_df]).drop_duplicates(subset=['Date'], keep='last')
    return updated

# ========== Strategy ==========
def swing_3_strategy(data, extrema_order=30):
    if data.empty:
        return pd.DataFrame()
    df = data.copy()
    df['MACD'], df['Signal'] = compute_macd(df)
    df['K'], df['D'], df['J'] = compute_kdj(df)
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    sma = tp.rolling(window=30).mean()
    mad = tp.rolling(window=30).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
    df['CCI'] = (tp - sma) / (0.015 * mad)
    df['TSI'] = compute_tsi(df, long=25, short=13)
    df['Aroon_Osc'] = compute_aroon(df, period=25)
    macd_norm = df['MACD'] / (2 * df['MACD'].std())
    cci_norm = df['CCI'] / 200
    tsi_norm = df['TSI'] / 100
    aroon_norm = df['Aroon_Osc'] / 100
    df['Bias'] = 0.25 * macd_norm + 0.25 * cci_norm + 0.25 * tsi_norm + 0.25 * aroon_norm
    df['Bias_Smoothed'] = df['Bias'].ewm(span=5, adjust=False).mean()
    bias_strength = np.clip(abs(df['Bias_Smoothed']) / 0.5, 0, 1)
    base_mult = [1.0, 2.0, 3.0]
    max_mult  = [1.5, 3.0, 5.0]
    df['TP_Mult_1'] = base_mult[0] + (max_mult[0] - base_mult[0]) * bias_strength
    df['TP_Mult_2'] = base_mult[1] + (max_mult[1] - base_mult[1]) * bias_strength
    df['TP_Mult_3'] = base_mult[2] + (max_mult[2] - base_mult[2]) * bias_strength
    maxima, minima = find_extrema(df['Close'], order=extrema_order)
    df['DIV_MACD'] = np.where(
        (df.index.isin(df.index[minima])) & (df['MACD'].diff() < 0.1) & (df['MACD'] < 0), 2,
        np.where((df.index.isin(df.index[maxima])) & (df['MACD'].diff() > -0.1) & (df['MACD'] > 0), -2, 0))
    df['DIV_KDJ'] = np.where(
        (df.index.isin(df.index[minima])) & (df['J'].diff() < 30) & (df['J'] < 50), 2,
        np.where((df.index.isin(df.index[maxima])) & (df['J'].diff() > -30) & (df['J'] > 50), -2, 0))
    df['DIV_CCI'] = np.where(
        (df.index.isin(df.index[minima])) & (df['CCI'].diff() < 10) & (df['CCI'] < -100), 1,
        np.where((df.index.isin(df.index[maxima])) & (df['CCI'].diff() > -10) & (df['CCI'] > 100), -1, 0))
    df['Divergence_Score'] = df['DIV_MACD'] + df['DIV_KDJ'] + df['DIV_CCI']
    df["Potential_Divergence"] = (
        (df['DIV_MACD'] + df['DIV_KDJ']) >= 2).astype(int) - (
        (df['DIV_MACD'] + df['DIV_KDJ']) <= -2).astype(int)
    df['Extrema_Index'] = np.nan
    df['SL_Level'] = np.nan
    df['TP1'] = np.nan; df['TP2'] = np.nan; df['TP3'] = np.nan
    df['Confirmed_Divergence'] = 0
    divergence_active = False; divergence_type = 0; divergence_start_idx = 0
    for i in range(len(df)):
        if not divergence_active and df['Potential_Divergence'].iloc[i] != 0:
            divergence_active = True
            divergence_type = df['Potential_Divergence'].iloc[i]
            divergence_start_idx = i
        if divergence_active:
            if divergence_type == 1 and df['Bias_Smoothed'].iloc[i] > 0:
                df.at[df.index[i], 'Confirmed_Divergence'] = 1
                df.at[df.index[i], 'Extrema_Index'] = divergence_start_idx
                divergence_active = False
            elif divergence_type == -1 and df['Bias_Smoothed'].iloc[i] < 0:
                df.at[df.index[i], 'Confirmed_Divergence'] = -1
                df.at[df.index[i], 'Extrema_Index'] = divergence_start_idx
                divergence_active = False
        if divergence_active:
            if divergence_type == 1 and df['Close'].iloc[i] < df['Close'].iloc[divergence_start_idx]:
                divergence_active = False
            elif divergence_type == -1 and df['Close'].iloc[i] > df['Close'].iloc[divergence_start_idx]:
                divergence_active = False
    df['Signal'] = 0
    df['Signal'] = np.where(df['Confirmed_Divergence'] == 1, 1, df['Signal'])
    df['Signal'] = np.where(df['Confirmed_Divergence'] == -1, -1, df['Signal'])
    return df

def compute_sl_tp(df, atr_period=14, sl_window=5, stop_loss_type='swing', atr_stop_multiplier=1.5):
    df = df.copy()
    if df.empty:
        return df
    if 'ATR' not in df.columns:
        df['ATR'] = compute_atr(df, period=atr_period)
    signals = df[df['Confirmed_Divergence'] != 0]
    if signals.empty:
        return df
    for idx in signals.index:
        signal_type = df.loc[idx, 'Confirmed_Divergence']
        ext_idx = int(df.loc[idx, 'Extrema_Index']) if not np.isnan(df.loc[idx, 'Extrema_Index']) else None
        entry = df.loc[idx, 'Close']
        atr_val = df.loc[idx, 'ATR']
        if np.isnan(atr_val):
            atr_val = df['ATR'].mean()
        if stop_loss_type == 'swing':
            if ext_idx is not None and 0 <= ext_idx < len(df):
                start = max(0, ext_idx - sl_window)
                end = min(len(df)-1, ext_idx + sl_window)
                high_window = df['High'].iloc[start:end+1]
                low_window = df['Low'].iloc[start:end+1]
                sl = low_window.min() if signal_type == 1 else high_window.max()
            else:
                sl = entry - atr_val * atr_stop_multiplier if signal_type == 1 else entry + atr_val * atr_stop_multiplier
        else:
            sl = entry - atr_val * atr_stop_multiplier if signal_type == 1 else entry + atr_val * atr_stop_multiplier
        mult1 = df.loc[idx, 'TP_Mult_1']; mult2 = df.loc[idx, 'TP_Mult_2']; mult3 = df.loc[idx, 'TP_Mult_3']
        if signal_type == 1:
            tp1 = entry + atr_val * mult1; tp2 = entry + atr_val * mult2; tp3 = entry + atr_val * mult3
        else:
            tp1 = entry - atr_val * mult1; tp2 = entry - atr_val * mult2; tp3 = entry - atr_val * mult3
        df.loc[idx, 'SL_Level'] = sl
        df.loc[idx, 'TP1'] = tp1; df.loc[idx, 'TP2'] = tp2; df.loc[idx, 'TP3'] = tp3
    return df

# ========== Plotting ==========
def plot_multi_timeframe(results_dict, symbol="TRX", sl_tp_display_window=20):
    intervals = list(results_dict.keys())
    n = len(intervals)
    if n == 0:
        fig, ax = plt.subplots(figsize=(10,6))
        ax.text(0.5, 0.5, "No data to plot.", ha='center', va='center')
        return compress_image(fig)

    fig, axes = plt.subplots(n, 1, figsize=(14, 8 * n), sharex=False)
    if n == 1:
        axes = [axes]

    for row, interval in enumerate(intervals):
        df = results_dict[interval]
        if df.empty:
            axes[row].text(0.5, 0.5, f"No data for {interval}", ha='center', va='center')
            axes[row].set_title(f'{symbol}/USD  {interval}')
            continue

        ax_div = axes[row]
        ax_div.set_xlabel('Date', fontweight='bold', fontsize=10, color='black')
        ax_div.set_ylabel('Divergence Score (inverted)', fontweight='bold', fontsize=9, color='black')
        inverted_score = -df['Divergence_Score']
        bar_width = 0.8 * (df.index[1] - df.index[0]).total_seconds() / (24 * 3600)
        colors = ['green' if x > 0 else 'red' if x < 0 else 'gray' for x in df['Divergence_Score']]
        ax_div.bar(df.index, inverted_score, color=colors, width=bar_width, alpha=0.85, zorder=0)
        ax_div.axhline(0, color='black', linewidth=0.5, alpha=0.4)
        ax_div.axhline(-3, color='green', linestyle='--', alpha=0.6, linewidth=1.0, label='Strong Bull')
        ax_div.axhline(3, color='red', linestyle='--', alpha=0.6, linewidth=1.0, label='Strong Bear')
        ax_div.tick_params(axis='y', labelsize=8)
        ax_div.grid(True, alpha=0.2, axis='x')
        max_score = max(abs(df['Divergence_Score'].max()), abs(df['Divergence_Score'].min()), 1)
        ax_div.set_ylim(-max_score * 1.2, max_score * 1.2)

        ax_price = ax_div.twinx()
        ax_price.plot(df.index, df['Close'], 'k-', label='Close', linewidth=1.2, alpha=0.9, zorder=1)
        ax_price.set_ylabel('Price', fontweight='bold', fontsize=9, color='blue')
        ax_price.tick_params(axis='y', labelsize=8)

        current_price = df['Close'].iloc[-1]
        ax_price.axhline(y=current_price, color='black', linestyle='-', linewidth=3.0, alpha=0.8, zorder=2)
        ax_price.axhline(y=current_price, color='red', linestyle='--', linewidth=1.8, alpha=1.0, label='Current Price', zorder=3)
        ax_price.text(1.02, current_price, f'{current_price:.4f}', color='red', fontsize=9, fontweight='bold',
                      va='center', ha='left', transform=ax_price.get_yaxis_transform(), zorder=10,
                      bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='black', alpha=0.9))

        price_range = df['Close'].max() - df['Close'].min()
        label_offset = price_range * 0.005

        signals = df[df['Confirmed_Divergence'] != 0]
        for idx in signals.index:
            pos = df.index.get_loc(idx)
            sig = df.loc[idx, 'Confirmed_Divergence']
            entry = df.loc[idx, 'Close']
            sl = df.loc[idx, 'SL_Level']
            tp1 = df.loc[idx, 'TP1']; tp2 = df.loc[idx, 'TP2']; tp3 = df.loc[idx, 'TP3']
            marker = '^' if sig == 1 else 'v'
            color = 'green' if sig == 1 else 'red'
            ax_price.scatter(idx, entry, color=color, marker=marker, s=120, zorder=15,
                             alpha=0.8, edgecolors='black', linewidth=0.5)
            start_pos = max(0, pos - sl_tp_display_window)
            end_pos = min(len(df)-1, pos + sl_tp_display_window)
            start_date = df.index[start_pos]; end_date = df.index[end_pos]
            if not np.isnan(sl):
                ax_price.plot([start_date, end_date], [sl, sl], color='darkred', linestyle='--', linewidth=1.0, alpha=0.9, zorder=2)
                ax_price.text(end_date, sl + label_offset, f'SL {sl:.4f}', color='darkred', fontsize=7, fontweight='bold',
                              va='bottom', ha='left', zorder=10,
                              bbox=dict(boxstyle='round,pad=0.1', facecolor='white', edgecolor='darkred', alpha=0.3))
            if not np.isnan(tp1):
                ax_price.plot([start_date, end_date], [tp1, tp1], color='darkblue', linestyle='--', linewidth=1.2, alpha=0.9, zorder=2)
                ax_price.text(end_date, tp1 + label_offset, f'TP1 {tp1:.4f}', color='darkblue', fontsize=7, fontweight='bold',
                              va='bottom', ha='left', zorder=10,
                              bbox=dict(boxstyle='round,pad=0.1', facecolor='white', edgecolor='darkblue', alpha=0.3))
            if not np.isnan(tp2):
                ax_price.plot([start_date, end_date], [tp2, tp2], color='darkblue', linestyle='--', linewidth=1.2, alpha=0.7, zorder=2)
                ax_price.text(end_date, tp2 + label_offset, f'TP2 {tp2:.4f}', color='darkblue', fontsize=7, fontweight='bold',
                              va='bottom', ha='left', zorder=10,
                              bbox=dict(boxstyle='round,pad=0.1', facecolor='white', edgecolor='darkblue', alpha=0.3))
            if not np.isnan(tp3):
                ax_price.plot([start_date, end_date], [tp3, tp3], color='darkblue', linestyle='--', linewidth=1.2, alpha=0.7, zorder=2)
                ax_price.text(end_date, tp3 + label_offset, f'TP3 {tp3:.4f}', color='darkblue', fontsize=7, fontweight='bold',
                              va='bottom', ha='left', zorder=10,
                              bbox=dict(boxstyle='round,pad=0.1', facecolor='white', edgecolor='darkblue', alpha=0.3))

        ax_price.set_title(f'{symbol}/USD  {interval}', fontsize=12, fontweight='bold', pad=10)
        lines1, labels1 = ax_price.get_legend_handles_labels()
        lines2, labels2 = ax_div.get_legend_handles_labels()
        unique = dict(zip(labels1 + labels2, lines1 + lines2))
        if unique:
            leg = ax_price.legend(unique.values(), unique.keys(), loc='upper left', fontsize=8)
            for text in leg.get_texts():
                text.set_fontweight('bold')
                text.set_color('black')
            leg.get_frame().set_facecolor('white')
            leg.get_frame().set_edgecolor('black')

        ax_div.tick_params(axis='x', rotation=30, labelsize=8)

    plt.tight_layout()
    return compress_image(fig, quality=75, dpi=80)

# ========== Main Execution ==========
def run_strategy(symbol, api_key, lookback, extrema_order, atr_period, sl_window,
                 stop_loss_type, atr_stop_multiplier, intervals):
    results = {}
    for interval in intervals:
        df = load_market_data(symbol, interval, lookback, api_key)
        if df.empty:
            results[interval] = pd.DataFrame()
            continue
        df_signals = swing_3_strategy(df, extrema_order=extrema_order)
        if df_signals.empty:
            results[interval] = pd.DataFrame()
            continue
        df_signals = compute_sl_tp(df_signals, atr_period=atr_period, sl_window=sl_window,
                                   stop_loss_type=stop_loss_type, atr_stop_multiplier=atr_stop_multiplier)
        results[interval] = df_signals
    return results

# ========== Streamlit UI ==========
with st.sidebar:
    st.header("Parameters")
    symbol = st.text_input("Symbol", value="TRX").upper()
    api_key = st.text_input("Twelve Data API Key", type="password", value="cef197ce3e054ee69d6c795401b229cd")
    lookback = st.number_input("Lookback (bars)", value=1000, min_value=100, step=100)
    extrema_order = st.number_input("Extrema Order", value=45, min_value=10, max_value=100, step=5)
    atr_period = st.number_input("ATR Period", value=14, min_value=5, max_value=50, step=1)
    sl_window = st.number_input("SL Window (for swing method)", value=5, min_value=1, max_value=20, step=1)
    stop_loss_type = st.selectbox("Stop Loss Type", options=['swing', 'atr'], index=0)
    atr_stop_multiplier = st.number_input("ATR Stop Multiplier", value=1.5, min_value=0.5, max_value=5.0, step=0.1)
    intervals = st.multiselect("Timeframes", options=['5min','15min','30min','1h'], default=['5min','15min','30min','1h'])
    
    st.divider()
    st.subheader("Live Streaming")
    live_update = st.checkbox("Enable Live Update", value=False)
    if live_update:
        stream_interval = st.selectbox("Stream Interval", intervals, index=0 if intervals else 0)
        update_interval = st.slider("Update Interval (seconds)", 5, 300, 30)
        st.caption(f"Streaming {symbol} {stream_interval}")
        # Autorefresh component – triggers a page refresh every update_interval seconds
        st_autorefresh(interval=update_interval * 1000, key="live_refresh")
    else:
        stream_interval = None
        update_interval = 30

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = {}
if 'sse_client' not in st.session_state:
    st.session_state.sse_client = None
if 'live_data' not in st.session_state:
    st.session_state.live_data = {}
if 'last_update_time' not in st.session_state:
    st.session_state.last_update_time = 0
if 'first_run' not in st.session_state:
    st.session_state.first_run = True

# Handle SSE client
if live_update and st.session_state.sse_client is None:
    st.session_state.sse_client = SSEClient(api_key, symbol, stream_interval)
    st.session_state.sse_client.start()
elif not live_update and st.session_state.sse_client is not None:
    st.session_state.sse_client.stop()
    st.session_state.sse_client = None

# Load data on first run or when parameters change
if st.session_state.first_run:
    st.session_state.first_run = False
    with st.spinner("Loading data..."):
        results = run_strategy(symbol, api_key, lookback, extrema_order, atr_period, sl_window,
                               stop_loss_type, atr_stop_multiplier, intervals)
        st.session_state.results = results
        st.session_state.live_data = {}
        for interval, df in results.items():
            if not df.empty:
                cols = ['Open','High','Low','Close']
                if 'Volume' in df.columns:
                    cols.append('Volume')
                st.session_state.live_data[interval] = df[cols].copy()
        st.session_state.last_update_time = time.time()

# ---- Live update: fetch new tick if available ----
if live_update and st.session_state.sse_client is not None and stream_interval is not None:
    new_tick = st.session_state.sse_client.get_update()
    if new_tick and stream_interval in st.session_state.live_data:
        raw = st.session_state.live_data[stream_interval]
        updated_raw = update_data_with_sse(raw, new_tick)
        if len(updated_raw) > lookback:
            updated_raw = updated_raw.iloc[-lookback:]
        st.session_state.live_data[stream_interval] = updated_raw
        # Recompute signals for this interval
        df_signals = swing_3_strategy(updated_raw, extrema_order=extrema_order)
        if not df_signals.empty:
            df_signals = compute_sl_tp(df_signals, atr_period=atr_period, sl_window=sl_window,
                                       stop_loss_type=stop_loss_type, atr_stop_multiplier=atr_stop_multiplier)
            st.session_state.results[stream_interval] = df_signals
            st.session_state.last_update_time = time.time()

# ---- Display: Current Signals Table ----
st.subheader("📋 Current Signals (most recent per timeframe)")
current_signals = []
for interval, df in st.session_state.results.items():
    if df.empty:
        continue
    signals = df[df['Confirmed_Divergence'] != 0]
    if signals.empty:
        continue
    last_signal = signals.iloc[-1]
    row = {
        'Datetime': last_signal.name,
        'Interval': interval,
        'Price': last_signal['Close'],
        'Action': 'buy' if last_signal['Confirmed_Divergence'] == 1 else 'sell',
        'SL': last_signal['SL_Level'],
        'TP1': last_signal['TP1'],
        'TP2': last_signal['TP2'],
        'TP3': last_signal['TP3'],
        'Bias_Smoothed': last_signal['Bias_Smoothed']
    }
    current_signals.append(row)

if current_signals:
    current_df = pd.DataFrame(current_signals)
    current_df = current_df.sort_values('Datetime', ascending=False)
    float_cols = ['Price', 'SL', 'TP1', 'TP2', 'TP3', 'Bias_Smoothed']
    for col in float_cols:
        current_df[col] = current_df[col].map(lambda x: f"{x:.6f}" if pd.notna(x) else "")
    st.dataframe(current_df, use_container_width=True, height=300)
else:
    st.info("No signals detected.")

# ---- Display: Chart ----
chart_placeholder = st.empty()
if any(not df.empty for df in st.session_state.results.values()):
    fig_buf = plot_multi_timeframe(st.session_state.results, symbol=symbol, sl_tp_display_window=20)
    chart_placeholder.image(fig_buf, use_container_width=True)
else:
    chart_placeholder.warning("No data to display.")
