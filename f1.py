import flet as ft
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
import matplotlib
matplotlib.use("Agg")  # Use Agg backend for matplotlib

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
    fig.savefig(png_buf, format='png', dpi=150)
    png_buf.seek(0)
    img = Image.open(png_buf)
    webp_buf = io.BytesIO()
    img.save(webp_buf, format='webp', quality=quality, method=6, bbox_inches='tight', pad_inches=0.1)
    webp_buf.seek(0)
    return webp_buf

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
            print(f"SSE Error: {str(e)}")
            
    def get_update(self):
        """Get the latest update from the queue"""
        try:
            compressed = self.event_queue.get_nowait()
            return decompress_data(compressed)
        except queue.Empty:
            return None

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

# Compute Schaff Trend Cycle
def compute_stc(data, fast_period=23, slow_period=50, cycle_period=10):
    # Calculate MACD line
    macd = data['Close'].ewm(span=fast_period, adjust=False).mean() - data['Close'].ewm(span=slow_period, adjust=False).mean()

    # Calculate Stochastic of MACD
    lowest_macd = macd.rolling(window=cycle_period).min()
    highest_macd = macd.rolling(window=cycle_period).max()
    stoch_macd = 100 * (macd - lowest_macd) / (highest_macd - lowest_macd)

    # Initialize STC
    stc = pd.Series(np.nan, index=data.index)
    k = 1  # Smoothing factor

    # Calculate STC with double smoothing
    for i in range(1, len(stoch_macd)):
        if np.isnan(stc.iloc[i-1]):
            stc.iloc[i] = stoch_macd.iloc[i]
        else:
            stc.iloc[i] = k * (stoch_macd.iloc[i] - stc.iloc[i-1]) + stc.iloc[i-1]

    # Second smoothing pass
    stc_final = pd.Series(np.nan, index=data.index)
    for i in range(1, len(stc)):
        if np.isnan(stc_final.iloc[i-1]):
            stc_final.iloc[i] = stc.iloc[i]
        else:
            stc_final.iloc[i] = k * (stc.iloc[i] - stc_final.iloc[i-1]) + stc_final.iloc[i-1]

    return stc_final

# Data loading functions
def load_initial_data(symbol, interval, lookback, api_key):
    """Load initial data from TwelveData API with compression"""
    try:
        url = f"https://api.twelvedata.com/time_series?apikey={api_key}&interval={interval}&symbol={symbol}/USD&type=etf&timezone=Africa/Lagos&outputsize={lookback}"
        headers = {'Accept-Encoding': 'br'}
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return pd.DataFrame(), f"API Error: {response.status_code}"
            
        data = response.json()
        
        if 'values' not in data:
            return pd.DataFrame(), f"API Error: {data.get('message', 'Unknown error')}"
            
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
        return df, None
        
    except Exception as e:
        return pd.DataFrame(), f"Error loading data: {str(e)}"

def update_data_with_sse(prev_data, new_data_point, lookback):
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

def check_for_new_signals(current_signals, previous_signals):
    """Compare current signals with previous to detect new ones"""
    new_signals = {}
    for signal_type in current_signals:
        previous = previous_signals.get(signal_type, [])
        current = current_signals.get(signal_type, [])
        
        # Compare timestamps to find new signals
        new = [s for s in current if s not in previous]
        if new:
            new_signals[signal_type] = new
            
    return new_signals


# Strategy 2: Swing 3 (Advanced Multi-Indicator Divergence)
def swing_3(data, visible_indicators):
    if data.empty:
        return plt.figure(), {}
    
    data = data.copy()
    
    # Compute RSI
    data['RSI_14'] = compute_rsi(data['Close'])
    data['RSI_10'] = compute_rsi(data['Low'], period=9)
    data['RSI_22'] = compute_rsi(data['Close'], period=22)
    data['MACD'], data['Signal'] = compute_macd(data)
    data['K'], data['D'], data['J'] = compute_kdj(data)
    
    # Compute CCI
    tp = (data['High'] + data['Low'] + data['Close']) / 3  # Typical Price
    sma = tp.rolling(window=30).mean()
    mad = tp.rolling(window=30).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
    data['CCI'] = (tp - sma) / (0.015 * mad)
    
    # Compute Ehlers Fisher Transform
    midpoint = (data['High'] + data['Low']) / 2
    hh = midpoint.rolling(window=32).max()
    ll = midpoint.rolling(window=32).min()
    normalized = 0.66 * ((midpoint - ll) / (hh - ll) - 0.5)
    normalized = normalized.clip(-0.999, 0.999)
    data['Ehlers_Fisher'] = 1 * np.log((1 + normalized) / (1 - normalized))
    data['Ehlers_Fisher_Smoothed'] = data['Ehlers_Fisher'].ewm(span=3, adjust=False).mean()
    
    # Compute SMI Ergodic Indicator
    midpoint = (data['High'] + data['Low']) / 2
    price_change = midpoint.diff(20)
    momentum = midpoint - midpoint.shift(20)
    data['SMI_Ergodic'] = momentum.ewm(span=5, adjust=False).mean()
    data['SMI_Trigger'] = data['SMI_Ergodic'].ewm(span=3, adjust=False).mean()
    
    # Compute Bias Indicator
    rsi_bias = (data['RSI_14'] - 50) / 50
    macd_bias = data['MACD'] / (2 * data['MACD'].std())
    cci_bias = data['CCI'] / 200
    data['Bias'] = 0.4 * rsi_bias + 0.3 * macd_bias + 0.3 * cci_bias
    data['Bias_Smoothed'] = data['Bias'].ewm(span=5, adjust=False).mean()
    
    # Compute Inertia Indicator (Adaptive Momentum Strength)
    numerator = (data['Close'] - data['Open']).rolling(window=30).mean()
    denominator = (data['High'] - data['Low']).rolling(window=30).mean()
    rvi = numerator / denominator
    price_changes = data['Close'].diff()
    std_dev = price_changes.rolling(window=30).std()
    data['Inertia'] = rvi * std_dev
    data['Inertia_Smoothed'] = data['Inertia'].ewm(span=10, adjust=False).mean()
    
    # Compute Schaff Trend Cycle
    data['STC'] = compute_stc(data)
    
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

    # Track divergence confirmation
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
                rsi_10_colors.append('blue')
        elif rsi_crossover_state == -1:
            if price_line_colors[i] == 'red':
                rsi_10_colors.append('red')
            else:
                rsi_10_colors.append('blue')
        else:
            rsi_10_colors.append('blue')

    # Determine how many subplots we need (price + selected indicators)
    num_plots = 1 + len(visible_indicators)  # Price plot + indicators
    height_ratios = [2] + [1] * len(visible_indicators)  # Price plot is taller
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 6 + 2.5 * len(visible_indicators)))
    gs = fig.add_gridspec(num_plots, 1, height_ratios=height_ratios)
    
    # Create axes - first one is always price plot
    axes = [fig.add_subplot(gs[0])]
    for i in range(1, num_plots):
        axes.append(fig.add_subplot(gs[i], sharex=axes[0]))
    
    # Configure all axes with professional styling
    for ax in axes:
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        ax.grid(True, linestyle=':', linewidth=0.5, alpha=0.7)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        
    
    # Get current price and time
    current_price = data['Close'].iloc[-1]
    current_time = data.index[-1]
    
    # 1. Price Plot
    for i in range(1, len(data)):
        axes[0].plot(data.index[i-1:i+1], data['Close'].iloc[i-1:i+1], color=price_line_colors[i], label='Close Price' if i == 1 else "")
    
    axes[0].scatter(data.index[data['Confirmed_Divergence'] == 1], data['Close'][data['Confirmed_Divergence'] == 1],
                    color='green', marker='^', label='Confirmed Bullish Divergence', s=100)
    axes[0].scatter(data.index[data['Confirmed_Divergence'] == -1], data['Close'][data['Confirmed_Divergence'] == -1],
                    color='red', marker='v', label='Confirmed Bearish Divergence', s=100)
    
    # Mark current price with dashed line and annotation
    axes[0].axhline(y=current_price, color='blue', linestyle='--', alpha=0.7, linewidth=1)
    axes[0].annotate(f'{current_price:.4f} ({current_time.strftime("%H:%M")})', 
                    xy=(1, current_price), 
                    xycoords=('axes fraction', 'data'),
                    xytext=(5, 0), 
                    textcoords='offset points',
                    color='blue',
                    va='center',
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    
    axes[0].set_title(f'Price with Confirmed Reversal Points')
    axes[0].grid(True, linestyle='--', alpha=0.7)
    
    # Plot selected indicators
    plot_idx = 1
    if "RSI" in visible_indicators:
        # RSI plot with improved coloring
        for i in range(1, len(data)):
            axes[plot_idx].plot(data.index[i-1:i+1], data['RSI_10'].iloc[i-1:i+1], color=rsi_10_colors[i], label='RSI 10' if i == 1 else "")
        axes[plot_idx].plot(data.index, data['RSI_22'], color='orange', label='RSI 22')
        
        # Mark current RSI value with dashed line
        current_rsi = data['RSI_10'].iloc[-1]
        axes[plot_idx].axhline(y=current_rsi, color='blue', linestyle='--', alpha=0.7, linewidth=1)
        axes[plot_idx].annotate(f'{current_rsi:.2f}', 
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
        
        axes[plot_idx].scatter(rsi_up.index, rsi_up['RSI_10'], color='green', marker='^', s=80, label='Bullish')
        axes[plot_idx].scatter(rsi_down.index, rsi_down['RSI_10'], color='red', marker='v', s=80, label='Bearish')
        
        axes[plot_idx].axhline(70, color='gray', linestyle='--', alpha=0.5)
        axes[plot_idx].axhline(30, color='gray', linestyle='--', alpha=0.5)
        axes[plot_idx].set_title('Strength cutter')
        axes[plot_idx].grid(True, linestyle='--', alpha=0.7)
        plot_idx += 1
    
    if "CCI" in visible_indicators:
        # CCI Plot
        axes[plot_idx].plot(data.index, data['CCI'], color='blue', label='CCI (20)')
        axes[plot_idx].axhline(100, color='red', linestyle='--', alpha=0.5)
        axes[plot_idx].axhline(-100, color='green', linestyle='--', alpha=0.5)
        axes[plot_idx].axhline(0, color='gray', linestyle='-', alpha=0.5)
        axes[plot_idx].set_title('Gray Index')
        axes[plot_idx].grid(True, linestyle='--', alpha=0.7)
        plot_idx += 1
    
    if "Fisher" in visible_indicators:
        # Ehlers Fisher Transform
        axes[plot_idx].plot(data.index, data['Ehlers_Fisher_Smoothed'], color='darkorange', label='Smoothed Ehlers Fisher Transform')
        axes[plot_idx].axhline(0.5, color='red', linestyle='--', alpha=0.5, label='Overbought Level')
        axes[plot_idx].axhline(-0.5, color='green', linestyle='--', alpha=0.5, label='Oversold Level')
        axes[plot_idx].axhline(0, color='gray', linestyle='-', alpha=0.5)
        axes[plot_idx].set_title('Fisher Timetion')
        axes[plot_idx].grid(True, linestyle='--', alpha=0.7)
        plot_idx += 1
    
    if "SMI" in visible_indicators:
        # SMI Ergodic Indicator
        axes[plot_idx].plot(data.index, data['SMI_Ergodic'], color='blue', label='SMI Ergodic Line')
        axes[plot_idx].plot(data.index, data['SMI_Trigger'], color='red', label='Trigger Line', alpha=0.7)
        axes[plot_idx].axhline(0, color='gray', linestyle='-', alpha=0.5)
        axes[plot_idx].fill_between(data.index, data['SMI_Ergodic'], data['SMI_Trigger'],
                                  where=data['SMI_Ergodic'] >= data['SMI_Trigger'],
                                  facecolor='green', alpha=0.3, interpolate=True)
        axes[plot_idx].fill_between(data.index, data['SMI_Ergodic'], data['SMI_Trigger'],
                                  where=data['SMI_Ergodic'] < data['SMI_Trigger'],
                                  facecolor='red', alpha=0.3, interpolate=True)
        axes[plot_idx].set_title('Erg')
        axes[plot_idx].axhline(0.01, color='red', linestyle='--', alpha=0.5, label='Overbought Level')
        axes[plot_idx].axhline(-0.01, color='green', linestyle='--', alpha=0.5, label='Oversold Level')
        axes[plot_idx].grid(True, linestyle='--', alpha=0.7)
        plot_idx += 1
    
    if "Bias" in visible_indicators:
        # Bias Indicator
        axes[plot_idx].plot(data.index, data['Bias'], color='gray', alpha=0.5, label='Raw Bias')
        axes[plot_idx].plot(data.index, data['Bias_Smoothed'], color='purple', label='Smoothed Bias')
        axes[plot_idx].axhline(0.3, color='red', linestyle='--', alpha=0.5, label='Bullish Threshold')
        axes[plot_idx].axhline(-0.3, color='green', linestyle='--', alpha=0.5, label='Bearish Threshold')
        axes[plot_idx].axhline(0, color='black', linestyle='-', alpha=0.5)
        axes[plot_idx].fill_between(data.index, data['Bias_Smoothed'], 0.2,
                                  where=data['Bias_Smoothed'] >= 0.2,
                                  facecolor='green', alpha=0.2, interpolate=True)
        axes[plot_idx].fill_between(data.index, data['Bias_Smoothed'], -0.2,
                                  where=data['Bias_Smoothed'] <= -0.2,
                                  facecolor='red', alpha=0.2, interpolate=True)
        axes[plot_idx].set_title('Gray Bias ')
        axes[plot_idx].grid(True, linestyle='--', alpha=0.7)
        plot_idx += 1
    
    if "Inertia" in visible_indicators:
        # Inertia Indicator (Adaptive Momentum Strength)
        axes[plot_idx].plot(data.index, data['Inertia'], color='gray', alpha=0.5, label='Raw Inertia')
        axes[plot_idx].plot(data.index, data['Inertia_Smoothed'], color='blue', label='Smoothed Inertia')
        axes[plot_idx].axhline(0, color='black', linestyle='-', alpha=0.5)
        axes[plot_idx].fill_between(data.index, data['Inertia_Smoothed'], 0,
                                  where=data['Inertia_Smoothed'] >= 0,
                                  facecolor='green', alpha=0.2, interpolate=True)
        axes[plot_idx].fill_between(data.index, data['Inertia_Smoothed'], 0,
                                  where=data['Inertia_Smoothed'] < 0,
                                  facecolor='red', alpha=0.2, interpolate=True)
        axes[plot_idx].set_title('Timetion Inert')
        axes[plot_idx].grid(True, linestyle='--', alpha=0.7)
        plot_idx += 1
    
    if "STC" in visible_indicators:
        # Schaff Trend Cycle
        axes[plot_idx].plot(data.index, data['STC'], color='purple', label='Schaff Trend Cycle')
        axes[plot_idx].axhline(75, color='red', linestyle='--', alpha=0.5, label='Overbought Level')
        axes[plot_idx].axhline(25, color='green', linestyle='--', alpha=0.5, label='Oversold Level')
        axes[plot_idx].axhline(50, color='gray', linestyle='-', alpha=0.5)  # Center line
        axes[plot_idx].set_title('Timetion Schaff')
        axes[plot_idx].grid(True, linestyle='--', alpha=0.7)
        plot_idx += 1
    
    if "Divergence" in visible_indicators:
        # Divergence Score
        axes[plot_idx].bar(data.index, data['Divergence_Score'],
                          color=np.where(data['Divergence_Score'] > 0, 'green', 'red'),
                          width=0.8, alpha=0.7)
        axes[plot_idx].axhline(3, color='green', linestyle='--', alpha=0.3)
        axes[plot_idx].axhline(-3, color='red', linestyle='--', alpha=0.3)
        axes[plot_idx].axhline(0, color='gray', linestyle='-', alpha=0.5)
        axes[plot_idx].set_title('Timetion Divergence Score')
        
        # Highlight strong divergence signals
        strong_bullish = data['Divergence_Score'] >= 3
        strong_bearish = data['Divergence_Score'] <= -3
        axes[plot_idx].scatter(data.index[strong_bullish], data['Divergence_Score'][strong_bullish],
                             color='lime', marker='o', s=50, label='Strong Bullish')
        axes[plot_idx].scatter(data.index[strong_bearish], data['Divergence_Score'][strong_bearish],
                             color='darkred', marker='o', s=50, label='Strong Bearish')
        axes[plot_idx].grid(True, linestyle='--', alpha=0.7)
        plot_idx += 1
    
    plt.tight_layout()
    return fig, current_signals

# Main Flet App
def main(page: ft.Page):
    # App state
    class AppState:
        def __init__(self):
            self.symbol = "EUR"
            self.interval = "1h"
            self.page = "Swing 3"
            self.live_update = True
            self.lookback = 300
            self.update_interval = 10
            self.alert_enabled = True
            self.alert_sound = True
            self.alert_volume = 0.7
            self.alert_types = ["Bullish Divergence", "Bearish Divergence"]
            self.previous_signals = {
                "Bullish Divergence": [],
                "Bearish Divergence": [],
                "RSI Crossover": []
            }
            self.alert_history = []
            self.sse_client = None
            self.last_data = None
            self.api_key = "cef197ce3e054ee69d6c795401b229cd"
            self.update_timer = None
            self.visible_indicators = {
                "Swing 3": ["RSI", "Fisher", "STC"]
            }
            self.last_update_time = None
            
    state = AppState()
    
    # Set page properties
    page.title = "TIMETION 0.3"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = ft.Colors.BLUE_50
    
    # Create a gradient background
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.BLUE,
    )
    
    # ========== UI Components ==========
        
    # Replace your current header section with this code
    header = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Image(
                    src="mypiclogo.png",  # Replace with your logo URL
                    width=50,
                    height=50,
                    fit=ft.ImageFit.CONTAIN,
                    border_radius=10,
                ),
                ft.Column([
                    ft.Text("TIMETION 0.3", 
                        size=28, 
                        weight=ft.FontWeight.BOLD, 
                        color=ft.Colors.BLUE_900),
                    ft.Text("Financial Market Analysis System", 
                        size=16, 
                        color=ft.Colors.BLUE_700),
                ], spacing=0, expand=True),
                
                ft.Container(
                    content=ft.Column([
                        ft.Text("Developed by Uka Benjamin Imo", size=12),
                        ft.Text("benjaminukaimo@gmail.com | +2347067193071", size=12),
                    ], alignment=ft.MainAxisAlignment.END),
                    alignment=ft.alignment.top_right,
                    expand=True,
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Divider(height=1, color=ft.Colors.BLUE_200),
            
            ft.Container(
                content=ft.Column([
                    ft.Text("AI-Powered Market Dynamics Modeling", 
                        size=18, 
                        weight=ft.FontWeight.W_500,
                        color=ft.Colors.BLUE_800),
                    ft.Text("Uncovering hidden patterns in time series data through symmetric-antisymmetric pattern learning",
                        size=12,
                        color=ft.Colors.GREY_700),
                ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.only(top=10, bottom=10),
                alignment=ft.alignment.center,
                width=page.width,
            ),
            
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Applications:", size=12, weight=ft.FontWeight.BOLD),
                            ft.Text("• Market Timing", size=10),
                            ft.Text("• Fraud Detection", size=10),
                            ft.Text("• Decision Systems", size=10),
                        ], spacing=2),
                        padding=10,
                        bgcolor=ft.Colors.BLUE_50,
                        border_radius=5,
                    ),
                    ft.VerticalDivider(width=1),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Key Features:", size=12, weight=ft.FontWeight.BOLD),
                            ft.Text("• Multi-indicator divergence detection", size=10),
                            ft.Text("• Real-time pattern recognition", size=10),
                            ft.Text("• Adaptive momentum analysis", size=10),
                        ], spacing=2),
                        padding=10,
                        bgcolor=ft.Colors.BLUE_50,
                        border_radius=5,
                    ),
                ], spacing=20, alignment=ft.MainAxisAlignment.CENTER),
                padding=ft.padding.only(bottom=10),
            ),
        ]),
        padding=20,
        bgcolor=ft.Colors.WHITE,
        border=ft.border.only(
            bottom=ft.border.BorderSide(1, ft.Colors.BLUE_100)
        ),
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=5,
            color=ft.Colors.BLUE_100,
            offset=ft.Offset(0, 1),
        )
    )    
    # Chart display
    chart_container = ft.Container(
        content=ft.Image(fit=ft.ImageFit.CONTAIN),  # Fixed: removed src=None
        alignment=ft.alignment.center,
        expand=True,
        border_radius=10,
        padding=10,
        bgcolor=ft.Colors.WHITE,
        height=None,
    )
    
    # Status text
    status_text = ft.Text("", size=14, color=ft.Colors.GREY_700)
    
    # Debug text for timer status
    debug_text = ft.Text("Timer status: Not started", size=12, color=ft.Colors.RED)
    
    # Alert history container
    alert_history_container = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        height=200,
        spacing=5,
    )
    
    # Input controls
    symbol_input = ft.TextField(
        label="Symbol (EUR, BTC, ETH, AAPL, etc)",
        value=state.symbol,
        width=200,
        on_submit=lambda e: update_symbol(e.control.value),
    )
    
    interval_dropdown = ft.Dropdown(
        label="Interval",
        options=[
            ft.dropdown.Option("1min"),
            ft.dropdown.Option("5min"),
            ft.dropdown.Option("15min"),
            ft.dropdown.Option("1h"),
            ft.dropdown.Option("4h"),
            ft.dropdown.Option("1day"),
            ft.dropdown.Option("1week"),
            ft.dropdown.Option("1month"),
        ],
        value=state.interval,
        width=150,
        on_change=lambda e: update_interval(e.control.value),
    )
    
    strategy_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(text="Swing 3"),
        ],
        on_change=lambda e: update_strategy(e.control.tabs[e.control.selected_index].text),
    )
    
    # Manual update button
    update_button = ft.ElevatedButton(
        text="Force Update",
        on_click=lambda e: update_chart(),
        bgcolor=ft.Colors.BLUE_500,  # Fixed: changed from ft.colors to ft.Colors
        color=ft.Colors.WHITE,       # Fixed: changed from ft.colors to ft.Colors
    )
    
    # Indicator selection controls
    rsi_checkbox = ft.Checkbox(
        label="RSI",
        value="RSI" in state.visible_indicators["Swing 3"],
        on_change=lambda e: toggle_indicator("RSI", e.control.value), scale=0.8,
    )
    
    
    fisher_checkbox = ft.Checkbox(
        label="Fisher",
        value="Fisher" in state.visible_indicators["Swing 3"],
        on_change=lambda e: toggle_indicator("Fisher", e.control.value), scale=0.8,
    )
    
    stc_checkbox = ft.Checkbox(
        label="STC",
        value="STC" in state.visible_indicators["Swing 3"],
        on_change=lambda e: toggle_indicator("STC", e.control.value), scale=0.8,
    )
    
    cci_checkbox = ft.Checkbox(
        label="CCI",
        value="CCI" in state.visible_indicators["Swing 3"],
        on_change=lambda e: toggle_indicator("CCI", e.control.value),scale=0.8,
    )
    
    smi_checkbox = ft.Checkbox(
        label="SMI",
        value="SMI" in state.visible_indicators["Swing 3"],
        on_change=lambda e: toggle_indicator("SMI", e.control.value), scale=0.8,
    )
    
    bias_checkbox = ft.Checkbox(
        label="Bias",
        value="Bias" in state.visible_indicators["Swing 3"],
        on_change=lambda e: toggle_indicator("Bias", e.control.value),scale=0.8,
    )
    
    inertia_checkbox = ft.Checkbox(
        label="Inertia",
        value="Inertia" in state.visible_indicators["Swing 3"],
        on_change=lambda e: toggle_indicator("Inertia", e.control.value), scale=0.8,
    )
    
    divergence_checkbox = ft.Checkbox(
        label="Divergence",
        value="Divergence" in state.visible_indicators["Swing 3"],
        on_change=lambda e: toggle_indicator("Divergence", e.control.value), scale=0.8,
    )
    
    # Sidebar controls
    live_update_switch = ft.Switch(
        label="Live Update",
        value=state.live_update,
        on_change=lambda e: toggle_live_update(e.control.value), scale=0.8,
    )
    
    lookback_slider = ft.Slider(
        min=50,
        max=1000,
        divisions=19,
        value=state.lookback,
        label="{value} bars",
        on_change=lambda e: update_lookback(e.control.value), scale=0.8,
    )
    
    update_interval_slider = ft.Slider(
        min=5,
        max=300,
        divisions=59,
        value=state.update_interval,
        label="{value} seconds",
        on_change=lambda e: update_update_interval(e.control.value), scale=0.8,
    )
    
    alert_enabled_switch = ft.Switch(
        label="Enable Alerts",
        value=state.alert_enabled,
        on_change=lambda e: toggle_alerts(e.control.value), scale=0.8,
    )
    
    alert_sound_switch = ft.Switch(
        label="Play Alert Sound",
        value=state.alert_sound,
        on_change=lambda e: toggle_alert_sound(e.control.value), scale=0.8,
    )
    
    alert_volume_slider = ft.Slider(
        min=0.1,
        max=1.0,
        divisions=9,
        value=state.alert_volume,
        label="{value}",
        on_change=lambda e: update_alert_volume(e.control.value), scale=0.8,
    )
    
    alert_types_checkbox = ft.Checkbox(
        label="Bullish Divergence",
        value="Bullish Divergence" in state.alert_types,
        on_change=lambda e: toggle_alert_type("Bullish Divergence", e.control.value),scale=0.8,
    )
    
    alert_types_checkbox2 = ft.Checkbox(
        label="Bearish Divergence",
        value="Bearish Divergence" in state.alert_types,
        on_change=lambda e: toggle_alert_type("Bearish Divergence", e.control.value),scale=0.8,
    )
    
    alert_types_checkbox3 = ft.Checkbox(
        label="RSI Crossover",
        value="RSI Crossover" in state.alert_types,
        on_change=lambda e: toggle_alert_type("RSI Crossover", e.control.value), scale=0.8,
    )
    
    # Update functions
    def update_symbol(value):
        state.symbol = value.upper()
        state.last_data = None
        update_chart()
    
    def update_interval(value):
        state.interval = value
        state.last_data = None
        update_chart()
    
    def update_strategy(value):
        state.page = value
        update_chart()
    
    def toggle_indicator(indicator, value):
        if value and indicator not in state.visible_indicators[state.page]:
            state.visible_indicators[state.page].append(indicator)
        elif not value and indicator in state.visible_indicators[state.page]:
            state.visible_indicators[state.page].remove(indicator)
        update_chart()
    
    def toggle_live_update(value):
        state.live_update = value
        if value:
            start_live_updates()
        else:
            stop_live_updates()
        debug_text.value = f"Live update: {'ON' if value else 'OFF'}"
        page.update()
    
    def update_lookback(value):
        state.lookback = int(value)
        state.last_data = None
        update_chart()
    
    def update_update_interval(value):
        state.update_interval = int(value)
        if state.live_update:
            restart_update_timer()
    
    def toggle_alerts(value):
        state.alert_enabled = value
    
    def toggle_alert_sound(value):
        state.alert_sound = value
    
    def update_alert_volume(value):
        state.alert_volume = value
    
    def toggle_alert_type(alert_type, value):
        if value and alert_type not in state.alert_types:
            state.alert_types.append(alert_type)
        elif not value and alert_type in state.alert_types:
            state.alert_types.remove(alert_type)
    
    # Chart update function
    def update_chart(e=None):
        try:
            now = datetime.now()
            debug_text.value = f"Update triggered at {now.strftime('%H:%M:%S')}"
            page.update()
            
            # Get data based on update mode
            if state.live_update and state.sse_client:
                # Check for SSE updates
                update = state.sse_client.get_update()
                if update:
                    state.last_data = update_data_with_sse(
                        state.last_data,
                        update,
                        state.lookback
                    )
                data = state.last_data if state.last_data is not None else load_initial_data(
                    state.symbol, state.interval, state.lookback, state.api_key
                )[0]
            else:
                # Load regular data
                data, error = load_initial_data(state.symbol, state.interval, state.lookback, state.api_key)
                if error:
                    show_error(error)
                    return
                state.last_data = data
            
            if data.empty:
                show_error("No data available - check your API key and symbol")
                return
            
            # Strategy display
            if state.page == "Swing 3":
                fig, current_signals = swing_3(data, state.visible_indicators["Swing 3"])
            
            # Display the chart with WebP compression
            img_buf = compress_image(fig)
            img_base64 = base64.b64encode(img_buf.getvalue()).decode('utf-8')
            chart_container.content.src_base64 = img_base64  # Fixed: only set src_base64, not both
            plt.close(fig)  # Free memory
            
            # Check for new signals and trigger alerts
            if state.alert_enabled and state.live_update:
                new_signals = check_for_new_signals(current_signals, state.previous_signals)
                for signal_type, timestamps in new_signals.items():
                    if signal_type in state.alert_types:
                        for ts in timestamps:
                            trigger_alert(signal_type, data.loc[ts, 'Close'], ts)
            
            # Update previous signals
            state.previous_signals = current_signals
            
            # Update status
            state.last_update_time = now
            status_text.value = f"Last update: {now.strftime('%Y-%m-%d %H:%M:%S')} | {len(data)} bars loaded"
            status_text.color = ft.Colors.GREY_700
            
            # Update UI
            page.update()
        except Exception as e:
            show_error(f"Error updating chart: {str(e)}")
    
    def show_error(message):
        status_text.value = message
        status_text.color = ft.Colors.RED
        page.update()
    
    def trigger_alert(alert_type, price, timestamp):
        # Create alert UI
        if alert_type == "Bullish Divergence":
            color = ft.Colors.GREEN
            icon = "arrow_upward"
            message = f"BULLISH DIVERGENCE at {price:.4f}"
        elif alert_type == "Bearish Divergence":
            color = ft.Colors.RED
            icon = "arrow_downward"
            message = f"BEARISH DIVERGENCE at {price:.4f}"
        else:
            color = ft.Colors.ORANGE
            icon = "swap_vert"
            message = f"RSI CROSSOVER at {price:.4f}"
        
        alert_row = ft.Row([
            ft.Text(timestamp.strftime('%H:%M:%S'), size=12),
            ft.Icon(name=icon, color=color),
            ft.Text(message, color=color, weight=ft.FontWeight.BOLD),
        ])
        
        # Add to alert history
        alert_history_container.controls.insert(0, alert_row)
        if len(alert_history_container.controls) > 10:
            alert_history_container.controls.pop()
        
        # Add to alert history state
        state.alert_history.append({
            "timestamp": timestamp,
            "type": alert_type,
            "price": price,
            "symbol": state.symbol
        })
        
        # Keep only last 50 alerts
        state.alert_history = state.alert_history[-50:]
        
        # Play sound if enabled
        if state.alert_sound:
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"🔔 {message}"),
                bgcolor=color,
            )
            page.snack_bar.open = True
        
        page.update()
    
    # Live update functions
    def start_live_updates():
        try:
            if state.sse_client is None:
                state.sse_client = SSEClient(state.api_key, state.symbol, state.interval, state.lookback)
                state.sse_client.start()
            restart_update_timer()
            debug_text.value = "Live updates started"
            page.update()
        except Exception as e:
            show_error(f"Error starting live updates: {str(e)}")
    
    def stop_live_updates():
        try:
            if state.sse_client is not None:
                state.sse_client.stop()
                state.sse_client = None
            if state.update_timer:
                page.remove_timer(state.update_timer)
                state.update_timer = None
            debug_text.value = "Live updates stopped"
            page.update()
        except Exception as e:
            show_error(f"Error stopping live updates: {str(e)}")
    
    def timer_callback(e):
        try:
            now = datetime.now()
            debug_text.value = f"Timer fired at {now.strftime('%H:%M:%S')}"
            page.update()
            update_chart()
        except Exception as ex:
            show_error(f"Timer callback error: {str(ex)}")
    
    def restart_update_timer():
        try:
            if state.update_timer:
                page.remove_timer(state.update_timer)
                state.update_timer = None
            
            # Use the correct method to set the timer
            interval_ms = max(state.update_interval, 5) * 1000
            
            # Set the timer with the wrapper function
            state.update_timer = page.add_timer(callback=timer_callback, milliseconds=interval_ms, repeat=True)
            debug_text.value = f"Timer restarted with interval: {interval_ms}ms"
            page.update()
        except Exception as e:
            show_error(f"Error restarting timer: {str(e)}")
    
    # Layout
    sidebar = ft.Container(
        content=ft.Column([
            ft.Text("Controls", size=10, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            live_update_switch,
            lookback_slider,
            update_interval_slider,
            update_button,
            debug_text,
            ft.Divider(),
            ft.Text("Indicator Selection", size=10, weight=ft.FontWeight.BOLD),
            rsi_checkbox,
            fisher_checkbox,
            stc_checkbox,
            cci_checkbox,
            smi_checkbox,
            bias_checkbox,
            inertia_checkbox,
            divergence_checkbox,
            ft.Divider(),
            ft.Text("Alert Settings", size=10, weight=ft.FontWeight.BOLD),
            alert_enabled_switch,
            alert_sound_switch,
            alert_volume_slider,
            ft.Text("Alert Types:", size=10),
            alert_types_checkbox,
            alert_types_checkbox2,
            alert_types_checkbox3,
            ft.Divider(),
            ft.Text("Alert History", size=10, weight=ft.FontWeight.BOLD),
            alert_history_container,
        ], scroll=ft.ScrollMode.AUTO),
        width=140,
        padding=10,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_center,
            end=ft.alignment.bottom_center,
            colors=[ft.Colors.LIGHT_BLUE, ft.Colors.BLUE]
        ),
    )
    
    main_content = ft.Column([
        ft.Row([
            symbol_input,
            interval_dropdown,
        ], alignment=ft.MainAxisAlignment.CENTER),
        strategy_tabs,
        chart_container,
        status_text,
    ], scroll=ft.ScrollMode.AUTO, expand=True)
    
    # Main layout
    page.add(
        ft.Row([
            sidebar,
            ft.VerticalDivider(width=1),
            ft.Column([
                header,
                main_content,
            ], scroll=ft.ScrollMode.AUTO, expand=True),
        ], expand=True)
    )
    
    # Initial chart update
    update_chart()
    
    # Start automatic updates if live_update is enabled
    if state.live_update:
        start_live_updates()

# Run the app
if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets", view=ft.WEB_BROWSER, port=8082)
