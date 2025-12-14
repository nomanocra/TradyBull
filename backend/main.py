from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import sqlite3
import os
import asyncio
import threading
from typing import Literal, Optional
from contextlib import contextmanager

app = FastAPI(title="TradyBull API")

# CORS pour permettre les requêtes depuis Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3080", "http://127.0.0.1:3080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PARIS_TZ = pytz.timezone('Europe/Paris')
SYMBOL = "NQ=F"  # Nasdaq 100 Futures uniquement
DB_PATH = os.path.join(os.path.dirname(__file__), "tradybull.db")
FETCH_INTERVAL = 10  # seconds

# Retention periods (tripled)
RETENTION = {
    "15m": timedelta(days=6),      # 2 -> 6 jours
    "1h": timedelta(days=21),      # 7 -> 21 jours
    "1d": timedelta(days=540),     # 180 -> 540 jours (18 mois)
}

# Last fetch timestamp
last_fetch_time = None

# WebSocket connections
connected_clients: list[WebSocket] = []


@contextmanager
def get_db():
    """Context manager for database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database tables"""
    with get_db() as conn:
        # Real-time candles table (with retention limits)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interval TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER,
                UNIQUE(interval, timestamp)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_interval_timestamp ON candles(interval, timestamp)")

        # Backtest candles table (no retention, grows indefinitely)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL DEFAULT 'NQ=F',
                timestamp INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER,
                source TEXT DEFAULT 'yfinance',
                UNIQUE(symbol, timestamp)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_backtest_timestamp ON backtest_candles(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_backtest_symbol_timestamp ON backtest_candles(symbol, timestamp)")

        # Signals table (pre-calculated trading signals)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL DEFAULT 'NQ=F',
                indicator TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                candle_timestamp INTEGER NOT NULL,
                price REAL NOT NULL,
                is_major INTEGER DEFAULT 1,
                metadata TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(symbol, indicator, signal_type, candle_timestamp)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_indicator ON signals(indicator)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol_indicator ON signals(symbol, indicator, timestamp)")

        conn.commit()


def cleanup_old_data():
    """Remove data older than retention period"""
    now = datetime.now(PARIS_TZ)
    with get_db() as conn:
        for interval, retention in RETENTION.items():
            cutoff = int((now - retention).timestamp())
            conn.execute(
                "DELETE FROM candles WHERE interval = ? AND timestamp < ?",
                (interval, cutoff)
            )
        conn.commit()


def store_candles(interval: str, candles: list):
    """Store candles in database, updating existing ones"""
    with get_db() as conn:
        for candle in candles:
            conn.execute("""
                INSERT OR REPLACE INTO candles (interval, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (interval, candle["time"], candle["open"], candle["high"], candle["low"], candle["close"], candle.get("volume", 0)))
        conn.commit()


def store_backtest_candles(candles: list):
    """Store 1h candles in backtest table (no retention limit, grows indefinitely)"""
    if not candles:
        return 0

    with get_db() as conn:
        cursor = conn.cursor()
        for candle in candles:
            cursor.execute("""
                INSERT OR IGNORE INTO backtest_candles
                (symbol, timestamp, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                SYMBOL,
                candle["time"],
                candle["open"],
                candle["high"],
                candle["low"],
                candle["close"],
                candle.get("volume", 0),
                "yfinance"
            ))
        conn.commit()
        return cursor.rowcount


# ============================================================================
# INDICATOR CALCULATIONS
# ============================================================================

def calculate_sma(closes: list, period: int) -> list:
    """Calculate Simple Moving Average"""
    result = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        result[i] = sum(closes[i - period + 1:i + 1]) / period
    return result


def calculate_std_dev(closes: list, period: int, sma: list) -> list:
    """Calculate Standard Deviation"""
    result = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        if sma[i] is None:
            continue
        slice_data = closes[i - period + 1:i + 1]
        mean = sma[i]
        variance = sum((x - mean) ** 2 for x in slice_data) / period
        result[i] = variance ** 0.5
    return result


def calculate_bollinger_bands(closes: list, period: int = 20, std_dev_mult: float = 2.0):
    """Calculate Bollinger Bands"""
    sma = calculate_sma(closes, period)
    std_dev = calculate_std_dev(closes, period, sma)

    upper = [None] * len(closes)
    lower = [None] * len(closes)

    for i in range(len(closes)):
        if sma[i] is not None and std_dev[i] is not None:
            upper[i] = sma[i] + std_dev_mult * std_dev[i]
            lower[i] = sma[i] - std_dev_mult * std_dev[i]

    return {"middle": sma, "upper": upper, "lower": lower}


# ============================================================================
# SIGNAL DETECTION
# ============================================================================

def detect_bollinger_buy_signals(candles: list, bollinger: dict) -> list:
    """
    Detect Bollinger buy signals:
    - When candle LOW goes below lower band
    - Signal appears on the NEXT candle (buy at open)
    - No consecutive signals until recovery (low above lower band)
    - Only ONE major signal per day (first after 7:00 AM Paris), others are secondary
    """
    signals = []
    waiting_for_recovery = False
    last_major_signal_date = None

    for i in range(len(candles) - 1):
        candle = candles[i]
        lower_band = bollinger["lower"][i]
        next_candle = candles[i + 1]

        if lower_band is None:
            continue

        # Recovery: current candle's low is above lower band
        if waiting_for_recovery and candle["low"] > lower_band:
            waiting_for_recovery = False

        # Trigger: current candle's low went below lower band
        if not waiting_for_recovery and candle["low"] < lower_band:
            signal_time = next_candle["time"]
            signal_dt = datetime.fromtimestamp(signal_time, tz=PARIS_TZ)
            signal_date_str = signal_dt.strftime("%Y-%m-%d")
            signal_hour = signal_dt.hour

            # Check if major signal (first after 7:00 AM Paris time for this day)
            is_after_7am = signal_hour >= 7
            is_major = is_after_7am and last_major_signal_date != signal_date_str

            if is_major:
                last_major_signal_date = signal_date_str

            signals.append({
                "indicator": "bollinger",
                "signal_type": "buy",
                "timestamp": signal_time,
                "candle_timestamp": signal_time,
                "price": next_candle["open"],
                "is_major": 1 if is_major else 0,
            })
            waiting_for_recovery = True

    return signals


def detect_market_close_signals(candles: list) -> list:
    """
    Detect market close sell signals at 22h Paris time.
    One signal per day.
    """
    signals = []
    processed_dates = set()

    for candle in candles:
        candle_dt = datetime.fromtimestamp(candle["time"], tz=PARIS_TZ)
        candle_hour = candle_dt.hour
        candle_date_str = candle_dt.strftime("%Y-%m-%d")

        # Signal at 22h Paris time, one per day
        if candle_hour == 22 and candle_date_str not in processed_dates:
            processed_dates.add(candle_date_str)
            signals.append({
                "indicator": "market_close",
                "signal_type": "sell",
                "timestamp": candle["time"],
                "candle_timestamp": candle["time"],
                "price": candle["close"],
                "is_major": 1,
            })

    return signals


def calculate_and_store_signals(candles: list, indicator: str = "bollinger"):
    """Calculate signals for given candles and store in database"""
    if not candles or len(candles) < 20:
        return 0

    closes = [c["close"] for c in candles]
    all_signals = []

    if indicator == "bollinger":
        bollinger = calculate_bollinger_bands(closes)
        buy_signals = detect_bollinger_buy_signals(candles, bollinger)
        sell_signals = detect_market_close_signals(candles)
        all_signals = buy_signals + sell_signals

    if not all_signals:
        return 0

    with get_db() as conn:
        cursor = conn.cursor()
        for signal in all_signals:
            cursor.execute("""
                INSERT OR IGNORE INTO signals
                (symbol, indicator, signal_type, timestamp, candle_timestamp, price, is_major)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                SYMBOL,
                signal["indicator"],
                signal["signal_type"],
                signal["timestamp"],
                signal["candle_timestamp"],
                signal["price"],
                signal["is_major"],
            ))
        conn.commit()
        return len(all_signals)


def get_backtest_candles_for_signals() -> list:
    """Get all 1h candles from backtest table for signal calculation"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT timestamp as time, open, high, low, close, volume FROM backtest_candles WHERE symbol = ? ORDER BY timestamp ASC",
            (SYMBOL,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_candles_from_db(interval: str) -> list:
    """Get all candles for an interval from database"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT timestamp, open, high, low, close, volume FROM candles WHERE interval = ? ORDER BY timestamp ASC",
            (interval,)
        ).fetchall()
        return [
            {
                "time": row["timestamp"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"]
            }
            for row in rows
        ]


def is_weekend() -> bool:
    """Check if it's weekend (Saturday or Sunday)"""
    now = datetime.now(PARIS_TZ)
    return now.weekday() >= 5


def is_market_open() -> bool:
    """Check if US market is open (9:30-16:00 ET = 15:30-22:00 Paris)"""
    now = datetime.now(PARIS_TZ)
    day = now.weekday()

    # Weekend
    if day >= 5:
        return False

    hours = now.hour
    minutes = now.minute
    time_in_minutes = hours * 60 + minutes

    # Market hours: 15:30 (930min) to 22:00 (1320min) Paris time
    return 930 <= time_in_minutes < 1320


def get_period_for_gap(timeframe: str, gap: Optional[timedelta]) -> str:
    """Calculate the optimal period to fetch based on data gap.

    yfinance valid periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max

    Args:
        timeframe: The timeframe (15min, 1h, 1day)
        gap: Time since last data, or None if no data exists
    """
    # Default full history periods (tripled)
    full_history = {
        "15min": "7d",    # 7 days for 15min (covers 6 day retention + buffer)
        "1h": "1mo",      # 1 month for 1h (covers 21 day retention)
        "1day": "2y",     # 2 years for daily (covers 18 month retention)
    }

    # If no data, fetch full history
    if gap is None:
        return full_history[timeframe]

    # Add buffer to ensure overlap
    total_hours = gap.total_seconds() / 3600

    # yfinance only accepts: 1d, 5d, 1mo, 3mo, 6mo, 1y, etc.
    # Pick the smallest period that covers the gap
    if total_hours <= 24:
        return "1d"
    elif total_hours <= 5 * 24:
        return "5d"
    elif total_hours <= 30 * 24:
        return "1mo"
    elif total_hours <= 90 * 24:
        return "3mo"
    else:
        return full_history[timeframe]


def get_yf_interval(timeframe: str) -> str:
    """Convert our timeframe to yfinance interval"""
    return {"15min": "15m", "1h": "1h", "1day": "1d"}[timeframe]


def fetch_and_store_data(interval: str) -> list:
    """Fetch data from yfinance and store in database.
    Automatically determines the optimal period based on data gap.

    Args:
        interval: The interval to fetch (15min, 1h, 1day)
    """
    # Get the gap since last data
    yf_interval = get_yf_interval(interval)
    gap = get_data_gap(yf_interval)
    period = get_period_for_gap(interval, gap)

    gap_str = f"{gap.days}d {gap.seconds//3600}h" if gap else "no data"
    print(f"  [{interval}] gap: {gap_str} -> fetching period: {period}")

    ticker = yf.Ticker(SYMBOL)
    data = ticker.history(period=period, interval=yf_interval)

    if data.empty:
        return []

    # Convert to list of candles with Paris timezone
    candles = []
    for timestamp, row in data.iterrows():
        # Convert to Paris timezone
        if timestamp.tzinfo is None:
            ts_utc = pytz.utc.localize(timestamp)
        else:
            ts_utc = timestamp.astimezone(pytz.utc)
        ts_paris = ts_utc.astimezone(PARIS_TZ)

        candles.append({
            "time": int(ts_paris.timestamp()),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"]) if row["Volume"] else 0
        })

    # Store in database
    store_candles(yf_interval, candles)

    # Also store 1h candles in backtest table (for backtesting, no retention)
    if yf_interval == "1h" and candles:
        store_backtest_candles(candles)
        print(f"    -> Also stored {len(candles)} candles in backtest table")

        # Calculate and store signals for 1h data
        # Get all 1h candles from backtest table for full signal calculation
        all_1h_candles = get_backtest_candles_for_signals()
        if all_1h_candles:
            num_signals = calculate_and_store_signals(all_1h_candles, "bollinger")
            if num_signals > 0:
                print(f"    -> Calculated {num_signals} signals")

    return candles


def get_all_data_payload() -> dict:
    """Get all data for WebSocket broadcast"""
    return {
        "type": "data_update",
        "symbol": SYMBOL,
        "market_open": is_market_open(),
        "standby": is_weekend(),
        "last_fetch": last_fetch_time.strftime("%H:%M:%S") if last_fetch_time else None,
        "data": {
            "15min": get_candles_from_db("15m"),
            "1h": get_candles_from_db("1h"),
            "1day": get_candles_from_db("1d"),
        }
    }


def broadcast_to_clients(data: dict):
    """Send data to all connected WebSocket clients"""
    if not connected_clients:
        return

    message = json.dumps(data)
    disconnected = []

    for client in connected_clients:
        try:
            # Use asyncio to send from sync context
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                asyncio.ensure_future(client.send_text(message))
            else:
                loop.run_until_complete(client.send_text(message))
        except Exception as e:
            print(f"Error sending to client: {e}")
            disconnected.append(client)

    # Remove disconnected clients
    for client in disconnected:
        if client in connected_clients:
            connected_clients.remove(client)


def fetch_all_intervals():
    """Fetch data for all intervals. Automatically determines optimal period for each."""
    global last_fetch_time
    print(f"[{datetime.now(PARIS_TZ).strftime('%H:%M:%S')}] Fetching data from yfinance...")

    try:
        for interval in ["15min", "1h", "1day"]:
            fetch_and_store_data(interval)
        cleanup_old_data()
        last_fetch_time = datetime.now(PARIS_TZ)
        print(f"[{last_fetch_time.strftime('%H:%M:%S')}] Data fetched and stored successfully")

        # Broadcast to all WebSocket clients
        if connected_clients:
            print(f"  Broadcasting to {len(connected_clients)} client(s)")
            broadcast_to_clients(get_all_data_payload())

    except Exception as e:
        print(f"Error fetching data: {e}")


def get_last_candle_time(interval: str) -> Optional[datetime]:
    """Get the timestamp of the last candle for an interval"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT MAX(timestamp) FROM candles WHERE interval = ?", (interval,)
        ).fetchone()
        if row and row[0]:
            return datetime.fromtimestamp(row[0], tz=PARIS_TZ)
    return None


def get_data_gap(interval: str) -> Optional[timedelta]:
    """Calculate how long since last data update for an interval"""
    last_time = get_last_candle_time(interval)
    if not last_time:
        return None  # No data = need full fetch
    return datetime.now(PARIS_TZ) - last_time


def has_sufficient_data() -> bool:
    """Check if database has sufficient historical data"""
    with get_db() as conn:
        # Check if we have at least some data for each interval
        for interval in ["15m", "1h", "1d"]:
            count = conn.execute(
                "SELECT COUNT(*) FROM candles WHERE interval = ?", (interval,)
            ).fetchone()[0]
            if count < 10:  # Need at least 10 candles per interval
                return False
    return True


STANDBY_INTERVAL = 60  # seconds between status updates in standby mode


def background_fetcher():
    """Background thread that fetches data periodically"""
    import time

    while True:
        if is_weekend():
            # Weekend standby mode: no fetch, just broadcast status
            print(f"[{datetime.now(PARIS_TZ).strftime('%H:%M:%S')}] Weekend standby mode")
            if connected_clients:
                broadcast_to_clients(get_all_data_payload())

            # Sleep longer in standby mode
            for _ in range(STANDBY_INTERVAL):
                time.sleep(1)
        else:
            # Normal mode: fetch data
            fetch_all_intervals()

            # Sleep for FETCH_INTERVAL seconds
            for _ in range(FETCH_INTERVAL):
                time.sleep(1)


# Initialize database on startup
init_db()

# Start background fetcher thread
fetcher_thread = threading.Thread(target=background_fetcher, daemon=True)
fetcher_thread.start()


@app.get("/")
def root():
    return {
        "service": "TradyBull API",
        "status": "running",
        "symbol": SYMBOL,
        "market_open": is_market_open(),
        "last_fetch": last_fetch_time.strftime("%H:%M:%S") if last_fetch_time else None
    }


@app.get("/api/nasdaq")
def get_nasdaq_data(
    interval: Literal["15min", "1h", "1day"] = Query(..., description="Timeframe: 15min, 1h, or 1day")
):
    """Get Nasdaq futures data from database"""
    try:
        # Map interval to db format
        db_interval_map = {"15min": "15m", "1h": "1h", "1day": "1d"}
        db_interval = db_interval_map[interval]

        # Get data from database (no fetch, just read)
        candles = get_candles_from_db(db_interval)

        if not candles:
            raise HTTPException(status_code=404, detail="No data available yet. Please wait for first fetch.")

        return {
            "symbol": SYMBOL,
            "interval": interval,
            "market_open": is_market_open(),
            "data": candles,
            "count": len(candles),
            "last_fetch": last_fetch_time.strftime("%H:%M:%S") if last_fetch_time else None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
def get_status():
    """Get current market status and data info"""
    now = datetime.now(PARIS_TZ)
    market_open = is_market_open()

    # Count records in database
    counts = {}
    with get_db() as conn:
        for interval in ["15m", "1h", "1d"]:
            count = conn.execute(
                "SELECT COUNT(*) FROM candles WHERE interval = ?", (interval,)
            ).fetchone()[0]
            counts[interval] = count

    # Calculate next fetch
    next_fetch = None
    if last_fetch_time:
        next_fetch_dt = last_fetch_time + timedelta(seconds=FETCH_INTERVAL)
        next_fetch = next_fetch_dt.strftime("%H:%M:%S")

    return {
        "current_time_paris": now.strftime("%Y-%m-%d %H:%M:%S"),
        "market_open": market_open,
        "symbol": SYMBOL,
        "database_records": counts,
        "last_fetch": last_fetch_time.strftime("%H:%M:%S") if last_fetch_time else None,
        "next_fetch": next_fetch,
        "fetch_interval_seconds": FETCH_INTERVAL
    }


@app.get("/api/backtest/info")
def get_backtest_info():
    """Get information about available backtesting data"""
    try:
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as count,
                    MIN(timestamp) as min_ts,
                    MAX(timestamp) as max_ts
                FROM backtest_candles
                WHERE symbol = ?
            """, (SYMBOL,))
            row = cursor.fetchone()

            if row["count"] == 0:
                return {
                    "symbol": SYMBOL,
                    "count": 0,
                    "message": "No backtesting data available. Run bootstrap script."
                }

            min_date = datetime.fromtimestamp(row["min_ts"], tz=PARIS_TZ)
            max_date = datetime.fromtimestamp(row["max_ts"], tz=PARIS_TZ)
            days_coverage = (max_date - min_date).days

            return {
                "symbol": SYMBOL,
                "interval": "1h",
                "count": row["count"],
                "start_date": min_date.strftime("%Y-%m-%d %H:%M"),
                "end_date": max_date.strftime("%Y-%m-%d %H:%M"),
                "days_coverage": days_coverage,
                "start_timestamp": row["min_ts"],
                "end_timestamp": row["max_ts"]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtest/data")
def get_backtest_data(
    start: Optional[int] = Query(None, description="Start timestamp (Unix)"),
    end: Optional[int] = Query(None, description="End timestamp (Unix)"),
    limit: int = Query(10000, description="Max candles to return")
):
    """Get backtesting data with optional date range filter"""
    try:
        with get_db() as conn:
            if start and end:
                query = """
                    SELECT timestamp, open, high, low, close, volume
                    FROM backtest_candles
                    WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                """
                rows = conn.execute(query, (SYMBOL, start, end, limit)).fetchall()
            elif start:
                query = """
                    SELECT timestamp, open, high, low, close, volume
                    FROM backtest_candles
                    WHERE symbol = ? AND timestamp >= ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                """
                rows = conn.execute(query, (SYMBOL, start, limit)).fetchall()
            else:
                query = """
                    SELECT timestamp, open, high, low, close, volume
                    FROM backtest_candles
                    WHERE symbol = ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                """
                rows = conn.execute(query, (SYMBOL, limit)).fetchall()

            candles = [
                {
                    "time": row["timestamp"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"]
                }
                for row in rows
            ]

            return {
                "symbol": SYMBOL,
                "interval": "1h",
                "data": candles,
                "count": len(candles)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/signals")
def get_signals(
    indicator: str = Query("bollinger", description="Indicator name (bollinger, market_close)"),
    start: Optional[int] = Query(None, description="Start timestamp (Unix)"),
    end: Optional[int] = Query(None, description="End timestamp (Unix)"),
    major_only: bool = Query(False, description="Return only major signals")
):
    """Get pre-calculated trading signals"""
    try:
        with get_db() as conn:
            # Build query based on parameters
            query_parts = ["SELECT * FROM signals WHERE symbol = ?"]
            params = [SYMBOL]

            # Filter by indicator (can be 'bollinger', 'market_close', or 'all')
            if indicator != "all":
                query_parts.append("AND indicator = ?")
                params.append(indicator)

            if start:
                query_parts.append("AND timestamp >= ?")
                params.append(start)

            if end:
                query_parts.append("AND timestamp <= ?")
                params.append(end)

            if major_only:
                query_parts.append("AND is_major = 1")

            query_parts.append("ORDER BY timestamp ASC")
            query = " ".join(query_parts)

            rows = conn.execute(query, params).fetchall()

            signals = [
                {
                    "indicator": row["indicator"],
                    "signal_type": row["signal_type"],
                    "timestamp": row["timestamp"],
                    "candle_timestamp": row["candle_timestamp"],
                    "price": row["price"],
                    "is_major": bool(row["is_major"]),
                }
                for row in rows
            ]

            return {
                "symbol": SYMBOL,
                "indicator": indicator,
                "signals": signals,
                "count": len(signals)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/signals/recalculate")
def recalculate_signals(indicator: str = Query("bollinger", description="Indicator to recalculate")):
    """Recalculate all signals for an indicator (admin endpoint)"""
    try:
        # Clear existing signals for this indicator
        with get_db() as conn:
            if indicator == "all":
                conn.execute("DELETE FROM signals WHERE symbol = ?", (SYMBOL,))
            else:
                conn.execute("DELETE FROM signals WHERE symbol = ? AND indicator = ?", (SYMBOL, indicator))
            conn.commit()

        # Get all backtest candles and recalculate
        candles = get_backtest_candles_for_signals()
        if not candles:
            return {"message": "No candles available", "signals_created": 0}

        num_signals = calculate_and_store_signals(candles, indicator)

        return {
            "message": f"Signals recalculated for {indicator}",
            "signals_created": num_signals,
            "candles_processed": len(candles)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data updates"""
    await websocket.accept()
    connected_clients.append(websocket)
    print(f"[WS] Client connected. Total: {len(connected_clients)}")

    try:
        # Send initial data immediately
        await websocket.send_text(json.dumps(get_all_data_payload()))

        # Keep connection alive
        while True:
            # Wait for any message (ping/pong or close)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        print(f"[WS] Total clients: {len(connected_clients)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
