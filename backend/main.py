from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import time
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import sqlite3
import os
import asyncio
import threading
from typing import Literal, Optional, List
from contextlib import contextmanager

# Import notification service
from notification_service import (
    get_notification_settings,
    get_all_notification_settings,
    save_notification_settings,
    delete_notification_settings,
    send_signal_notification,
    send_signal_notification_sync,
    test_telegram_notification,
    get_notification_history,
    was_notification_already_sent
)

# Import signal calculator (lazy import to avoid circular deps)
def get_signal_calculator():
    from signal_calculator import (
        calculate_signals_incremental,
        get_signals_from_db,
        calculate_all_strategies,
        recalculate_strategy,
        recalculate_all_strategies,
        check_all_strategies_latest_candle
    )
    from strategies import STRATEGIES
    return calculate_signals_incremental, get_signals_from_db, calculate_all_strategies, recalculate_strategy, recalculate_all_strategies, check_all_strategies_latest_candle, STRATEGIES

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
                strategy_name TEXT NOT NULL,
                symbol TEXT NOT NULL DEFAULT 'NQ=F',
                signal_timestamp INTEGER NOT NULL,
                trigger_timestamp INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('buy', 'sell')),
                price REAL NOT NULL,
                label TEXT,
                metadata TEXT,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                UNIQUE(strategy_name, symbol, signal_timestamp, type)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals(strategy_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_strategy_symbol ON signals(strategy_name, symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(signal_timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_strategy_timestamp ON signals(strategy_name, signal_timestamp)")

        # Signal processing state (for incremental updates)
        # Migration: recreate table to allow 'unified' data_source
        # Check if old table exists with incompatible CHECK constraint
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='signal_processing_state'")
        existing_schema = cursor.fetchone()
        if existing_schema and "'unified'" not in existing_schema[0]:
            # Migrate: create new table, copy data, swap
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signal_processing_state_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    symbol TEXT NOT NULL DEFAULT 'NQ=F',
                    data_source TEXT NOT NULL,
                    last_processed_timestamp INTEGER NOT NULL,
                    last_signal_state TEXT,
                    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                    UNIQUE(strategy_name, symbol, data_source)
                )
            """)
            conn.execute("INSERT OR IGNORE INTO signal_processing_state_new SELECT * FROM signal_processing_state")
            conn.execute("DROP TABLE signal_processing_state")
            conn.execute("ALTER TABLE signal_processing_state_new RENAME TO signal_processing_state")
            print("[DB] Migrated signal_processing_state table to support 'unified' data_source")
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signal_processing_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    symbol TEXT NOT NULL DEFAULT 'NQ=F',
                    data_source TEXT NOT NULL,
                    last_processed_timestamp INTEGER NOT NULL,
                    last_signal_state TEXT,
                    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                    UNIQUE(strategy_name, symbol, data_source)
                )
            """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signal_state_strategy ON signal_processing_state(strategy_name, symbol, data_source)")

        # Archived strategies table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS archived_strategies (
                strategy_name TEXT PRIMARY KEY,
                archived_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
        """)

        # Dynamic strategies table (user-created strategies with JSON config)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dynamic_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
        """)

        # Notification settings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_settings (
                strategy_name TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                desktop_enabled INTEGER NOT NULL DEFAULT 0,
                telegram_enabled INTEGER NOT NULL DEFAULT 0,
                telegram_bot_token TEXT,
                telegram_chat_id TEXT,
                notify_buy INTEGER NOT NULL DEFAULT 1,
                notify_sell INTEGER NOT NULL DEFAULT 1,
                time_start TEXT DEFAULT '00:00',
                time_end TEXT DEFAULT '23:59',
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
        """)

        # Notification history table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                sent_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                signal_type TEXT NOT NULL,
                price REAL NOT NULL,
                channel TEXT NOT NULL,
                message TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 1,
                error_message TEXT,
                FOREIGN KEY (strategy_name) REFERENCES notification_settings(strategy_name)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_history_strategy ON notification_history(strategy_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_history_sent_at ON notification_history(sent_at)")

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
                INSERT INTO backtest_candles
                (symbol, timestamp, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timestamp) DO UPDATE SET
                    high = MAX(backtest_candles.high, excluded.high),
                    low = MIN(backtest_candles.low, excluded.low),
                    close = excluded.close,
                    volume = excluded.volume
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

    return candles


def get_all_data_payload() -> dict:
    """Get all data for WebSocket broadcast, including signals"""
    payload = {
        "type": "data_update",
        "symbol": SYMBOL,
        "market_open": is_market_open(),
        "standby": is_weekend(),
        "last_fetch": last_fetch_time.strftime("%H:%M:%S") if last_fetch_time else None,
        "data": {
            "15min": get_candles_from_db("15m"),
            "1h": get_candles_from_db("1h"),
            "1day": get_candles_from_db("1d"),
        },
        "signals": {}
    }

    # Add signals for all strategies (hardcoded + dynamic)
    try:
        _, get_signals_from_db, _, _, _, _, STRATEGIES = get_signal_calculator()
        with get_db() as conn:
            # Hardcoded strategies
            for strategy_name in STRATEGIES:
                signals = get_signals_from_db(conn, strategy_name, SYMBOL)
                payload["signals"][strategy_name] = signals

            # Dynamic strategies from database
            dynamic_rows = conn.execute("SELECT name FROM dynamic_strategies").fetchall()
            for row in dynamic_rows:
                strategy_name = row['name']
                signals = get_signals_from_db(conn, strategy_name, SYMBOL)
                payload["signals"][strategy_name] = signals
    except Exception as e:
        print(f"Warning: Could not load signals: {e}")

    return payload


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

        # Check signals on latest candle for all strategies (using backtest_candles as single source)
        try:
            _, _, _, _, _, check_all_strategies_latest_candle, STRATEGIES = get_signal_calculator()
            with get_db() as conn:
                print(f"  Checking signals for {len(STRATEGIES)} strategies + dynamic...")
                results = check_all_strategies_latest_candle(conn, SYMBOL)
                new_signals_count = sum(1 for s in results.values() if s is not None)
                print(f"  Signal check complete: {new_signals_count} new signals found")
                for strategy_name, signal in results.items():
                    if signal is not None:
                        print(f"  [{strategy_name}] New {signal.type} signal at {signal.price}")

                        # Send notification for the new signal
                        try:
                            # Only send notifications for recent signals (< 15 minutes old)
                            signal_age = int(time.time()) - signal.signal_timestamp
                            if signal_age > 900:  # 15 minutes in seconds
                                print(f"    Skipping notification for old signal ({signal_age//60}min old)")
                                continue

                            # Check if notification was already sent for this signal
                            if was_notification_already_sent(strategy_name, signal.signal_timestamp, signal.type):
                                print(f"    Skipping notification already sent for {signal.type} signal")
                                continue

                            # Get display name for the strategy
                            strategy_class = STRATEGIES.get(strategy_name)
                            if strategy_class:
                                strategy_instance = strategy_class()
                                display_name = strategy_instance.display_config.display_name
                            else:
                                # For dynamic strategies, get display name from DB
                                row = conn.execute(
                                    "SELECT display_name FROM dynamic_strategies WHERE name = ?",
                                    (strategy_name,)
                                ).fetchone()
                                display_name = row[0] if row else strategy_name

                            send_signal_notification_sync(
                                strategy_name=strategy_name,
                                strategy_display_name=display_name,
                                signal_type=signal.type,
                                price=signal.price,
                                timestamp=signal.signal_timestamp
                            )
                        except Exception as notif_err:
                            print(f"  Warning: Could not send notification: {notif_err}")
        except Exception as e:
            print(f"Warning: Could not calculate signals: {e}")

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


# =============================================================================
# Signal Endpoints
# =============================================================================

@app.get("/api/signals")
def get_signals(
    strategy: str = Query(..., description="Strategy name (e.g., 'bollinger-nosl')"),
    start: Optional[int] = Query(None, description="Start timestamp (Unix)"),
    end: Optional[int] = Query(None, description="End timestamp (Unix)"),
    limit: int = Query(10000, description="Max signals to return")
):
    """Get signals for a strategy within optional date range"""
    try:
        _, get_signals_from_db, _, _, _, _, STRATEGIES = get_signal_calculator()

        if strategy not in STRATEGIES:
            # Check if it's a dynamic strategy
            with get_db() as conn:
                dynamic_row = conn.execute(
                    "SELECT name FROM dynamic_strategies WHERE name = ?", (strategy,)
                ).fetchone()
                if not dynamic_row:
                    raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")

        with get_db() as conn:
            signals = get_signals_from_db(conn, strategy, SYMBOL, start, end, limit)

            return {
                "strategy": strategy,
                "symbol": SYMBOL,
                "signals": signals,
                "count": len(signals)
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/signals/info")
def get_signals_info(
    strategy: str = Query(..., description="Strategy name")
):
    """Get information about signals for a strategy"""
    try:
        _, _, _, _, _, _, STRATEGIES = get_signal_calculator()

        if strategy not in STRATEGIES:
            # Check if it's a dynamic strategy
            with get_db() as conn:
                dynamic_row = conn.execute(
                    "SELECT name FROM dynamic_strategies WHERE name = ?", (strategy,)
                ).fetchone()
                if not dynamic_row:
                    raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")

        with get_db() as conn:
            # Get signal counts
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN type = 'buy' THEN 1 ELSE 0 END) as buy_count,
                    SUM(CASE WHEN type = 'sell' THEN 1 ELSE 0 END) as sell_count,
                    MIN(signal_timestamp) as first_signal,
                    MAX(signal_timestamp) as last_signal
                FROM signals
                WHERE strategy_name = ? AND symbol = ?
            """, (strategy, SYMBOL))
            row = cursor.fetchone()

            # Get processing state
            state_cursor = conn.execute("""
                SELECT data_source, last_processed_timestamp
                FROM signal_processing_state
                WHERE strategy_name = ? AND symbol = ?
            """, (strategy, SYMBOL))
            states = {r['data_source']: r['last_processed_timestamp'] for r in state_cursor}

            return {
                "strategy": strategy,
                "symbol": SYMBOL,
                "total_signals": row["total"] or 0,
                "buy_signals": row["buy_count"] or 0,
                "sell_signals": row["sell_count"] or 0,
                "first_signal_timestamp": row["first_signal"],
                "last_signal_timestamp": row["last_signal"],
                "processing_state": states
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/signals/calculate")
def calculate_signals_endpoint(
    strategy: str = Query(..., description="Strategy name")
):
    """Trigger incremental signal calculation for new candles (uses backtest_candles as single source)"""
    try:
        calculate_signals_incremental, _, _, _, _, _, STRATEGIES = get_signal_calculator()

        with get_db() as conn:
            # Check if strategy exists (hardcoded or dynamic)
            if strategy not in STRATEGIES:
                dynamic_row = conn.execute(
                    "SELECT name FROM dynamic_strategies WHERE name = ?", (strategy,)
                ).fetchone()
                if not dynamic_row:
                    raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")

            new_count, _ = calculate_signals_incremental(conn, strategy, SYMBOL, 'unified', 'backtest_candles')

            return {
                "strategy": strategy,
                "new_signals": new_count,
                "message": f"Generated {new_count} new signal(s)"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/signals/strategies")
def list_strategies():
    """List all available strategies with their display metadata (Python + dynamic)"""
    try:
        _, _, _, _, _, _, STRATEGIES = get_signal_calculator()
        from strategies.dynamic import create_dynamic_strategy

        with get_db() as conn:
            # Get archived strategies
            archived_rows = conn.execute("SELECT strategy_name FROM archived_strategies").fetchall()
            archived_set = {row['strategy_name'] for row in archived_rows}

            # Get dynamic strategies from DB
            dynamic_rows = conn.execute(
                "SELECT name, display_name, config FROM dynamic_strategies"
            ).fetchall()

        strategies_list = []

        # Add Python-defined strategies
        for name, strategy_class in STRATEGIES.items():
            strategy_instance = strategy_class()
            strategy_dict = strategy_instance.to_dict()
            strategy_dict['is_archived'] = name in archived_set
            strategy_dict['is_dynamic'] = False
            strategies_list.append(strategy_dict)

        # Add dynamic strategies from DB
        for row in dynamic_rows:
            config = json.loads(row['config'])
            config['name'] = row['name']
            config['display_name'] = row['display_name']
            try:
                strategy = create_dynamic_strategy(config)
                strategy_dict = strategy.to_dict()
                strategy_dict['is_archived'] = row['name'] in archived_set
                strategy_dict['is_dynamic'] = True
                strategies_list.append(strategy_dict)
            except Exception as e:
                print(f"Error loading dynamic strategy {row['name']}: {e}")

        return {
            "strategies": strategies_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/signals/recalculate")
def recalculate_signals(
    strategy: Optional[str] = Query(default=None, description="Strategy name to recalculate (all if not specified)")
):
    """
    Force full recalculation of signals from backtest_candles (single source of truth).
    Use in backtesting to catch missed signals when backend wasn't running.
    Does NOT send notifications (safe to use anytime).
    """
    try:
        _, _, _, recalculate_strategy_fn, recalculate_all_strategies_fn, _, STRATEGIES = get_signal_calculator()

        with get_db() as conn:
            if strategy:
                if strategy not in STRATEGIES:
                    # Check if it's a dynamic strategy
                    dynamic_row = conn.execute(
                        "SELECT name FROM dynamic_strategies WHERE name = ?", (strategy,)
                    ).fetchone()
                    if not dynamic_row:
                        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy}")
                count = recalculate_strategy_fn(conn, strategy, SYMBOL)
                return {"strategy": strategy, "signals_count": count, "message": "Recalculation complete (no notifications sent)"}
            else:
                results = recalculate_all_strategies_fn(conn, SYMBOL)
                total = sum(results.values())
                return {"strategies": results, "total_signals": total, "message": "Recalculation complete (no notifications sent)"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Dynamic Strategies ====================
# NOTE: These routes must come BEFORE /api/strategies/{strategy_name} routes
# to avoid "dynamic" being matched as a strategy_name parameter

class DynamicStrategyCreate(BaseModel):
    """Request body for creating a dynamic strategy"""
    indicator: Optional[dict] = None  # {"type": "bollinger", "mode": "both"}
    stop_loss: Optional[float] = None
    ma_trend: Optional[int] = None
    value_above_ma: Optional[int] = None
    ma_cross: Optional[dict] = None  # {"fast": 50, "slow": 200}
    intraday: str = "none"
    time_constraint: Optional[dict] = None  # {"open": "07:00", "close": "23:00"}


@app.post("/api/strategies/dynamic")
def create_dynamic_strategy_endpoint(body: DynamicStrategyCreate):
    """Create a new dynamic strategy and run initial backtest"""
    try:
        from strategies.dynamic import (
            create_dynamic_strategy,
            generate_strategy_name,
            generate_display_name
        )

        config = body.model_dump()

        # Generate name and display_name
        name = generate_strategy_name(config)
        display_name = generate_display_name(config)

        # Check if name already exists
        _, _, _, _, _, _, STRATEGIES = get_signal_calculator()
        with get_db() as conn:
            existing = conn.execute(
                "SELECT name FROM dynamic_strategies WHERE name = ?", (name,)
            ).fetchone()

        if name in STRATEGIES or existing:
            # Add timestamp suffix to make unique
            name = f"{name}-{int(datetime.now().timestamp())}"
            display_name = f"{display_name} ({int(datetime.now().timestamp()) % 10000})"

        config['name'] = name
        config['display_name'] = display_name

        # Validate by creating the strategy instance
        strategy = create_dynamic_strategy(config)

        # Save to database
        with get_db() as conn:
            conn.execute(
                """INSERT INTO dynamic_strategies (name, display_name, config, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, display_name, json.dumps(config), int(datetime.now().timestamp()), int(datetime.now().timestamp()))
            )
            conn.commit()

        # Run initial signal calculation from full history
        calculate_signals_incremental, _, _, _, _, _, _ = get_signal_calculator()
        with get_db() as conn:
            new_signals, _ = calculate_signals_incremental(
                conn, name, SYMBOL, 'unified', 'backtest_candles',
                strategy_instance=strategy
            )

        return {
            "status": "created",
            "strategy": {
                "name": name,
                "display_name": display_name,
                "config": config,
                "signals_count": new_signals
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategies/dynamic")
def list_dynamic_strategies():
    """List all dynamic strategies"""
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id, name, display_name, config, created_at, updated_at FROM dynamic_strategies ORDER BY created_at DESC"
            ).fetchall()

        strategies = []
        for row in rows:
            strategies.append({
                "id": row['id'],
                "name": row['name'],
                "display_name": row['display_name'],
                "config": json.loads(row['config']),
                "created_at": row['created_at'],
                "updated_at": row['updated_at']
            })

        return {"strategies": strategies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategies/dynamic/{name}")
def get_dynamic_strategy(name: str):
    """Get a specific dynamic strategy by name"""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, name, display_name, config, created_at, updated_at FROM dynamic_strategies WHERE name = ?",
                (name,)
            ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Dynamic strategy not found: {name}")

        return {
            "id": row['id'],
            "name": row['name'],
            "display_name": row['display_name'],
            "config": json.loads(row['config']),
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/strategies/dynamic/{name}")
def delete_dynamic_strategy(name: str):
    """Delete a dynamic strategy and all its data"""
    try:
        with get_db() as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT name FROM dynamic_strategies WHERE name = ?", (name,)
            ).fetchone()

            if not existing:
                raise HTTPException(status_code=404, detail=f"Dynamic strategy not found: {name}")

            # Delete all associated data
            conn.execute("DELETE FROM signals WHERE strategy_name = ?", (name,))
            conn.execute("DELETE FROM signal_processing_state WHERE strategy_name = ?", (name,))
            conn.execute("DELETE FROM notification_settings WHERE strategy_name = ?", (name,))
            conn.execute("DELETE FROM notification_history WHERE strategy_name = ?", (name,))
            conn.execute("DELETE FROM archived_strategies WHERE strategy_name = ?", (name,))
            conn.execute("DELETE FROM dynamic_strategies WHERE name = ?", (name,))
            conn.commit()

        return {"status": "deleted", "strategy": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Strategy Archive ====================

@app.post("/api/strategies/{strategy_name}/archive")
def archive_strategy(strategy_name: str):
    """Archive a strategy (hide from Real Time and Backtesting)"""
    try:
        _, _, _, _, _, _, STRATEGIES = get_signal_calculator()

        if strategy_name not in STRATEGIES:
            # Check if it's a dynamic strategy
            with get_db() as conn:
                dynamic_row = conn.execute(
                    "SELECT name FROM dynamic_strategies WHERE name = ?", (strategy_name,)
                ).fetchone()
                if not dynamic_row:
                    raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_name}")

        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO archived_strategies (strategy_name) VALUES (?)",
                (strategy_name,)
            )
            conn.commit()

        return {"status": "archived", "strategy": strategy_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/strategies/{strategy_name}/unarchive")
def unarchive_strategy(strategy_name: str):
    """Unarchive a strategy (restore to Real Time and Backtesting)"""
    try:
        _, _, _, _, _, _, STRATEGIES = get_signal_calculator()

        if strategy_name not in STRATEGIES:
            # Check if it's a dynamic strategy
            with get_db() as conn:
                dynamic_row = conn.execute(
                    "SELECT name FROM dynamic_strategies WHERE name = ?", (strategy_name,)
                ).fetchone()
                if not dynamic_row:
                    raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_name}")

        with get_db() as conn:
            conn.execute(
                "DELETE FROM archived_strategies WHERE strategy_name = ?",
                (strategy_name,)
            )
            conn.commit()

        return {"status": "unarchived", "strategy": strategy_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/strategies/{strategy_name}")
def delete_strategy(strategy_name: str):
    """Delete a strategy's data (signals, settings, history). Strategy stays archived."""
    try:
        with get_db() as conn:
            # Delete all data associated with the strategy
            conn.execute("DELETE FROM signals WHERE strategy_name = ?", (strategy_name,))
            conn.execute("DELETE FROM signal_processing_state WHERE strategy_name = ?", (strategy_name,))
            conn.execute("DELETE FROM notification_settings WHERE strategy_name = ?", (strategy_name,))
            conn.execute("DELETE FROM notification_history WHERE strategy_name = ?", (strategy_name,))
            # Keep in archived_strategies - strategy is defined in Python code
            conn.commit()

        return {"status": "deleted", "strategy": strategy_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kpis")
def get_kpis(
    strategy: str = Query(..., description="Strategy name (e.g., 'bollinger-nosl')"),
    start: Optional[int] = Query(None, description="Start timestamp (Unix)"),
    end: Optional[int] = Query(None, description="End timestamp (Unix)"),
):
    """Get KPIs for a strategy within optional date range"""
    try:
        from kpi_calculator import calculate_kpis

        _, get_signals_from_db, _, _, _, _, STRATEGIES = get_signal_calculator()

        # Check if strategy exists (Python or dynamic)
        with get_db() as conn:
            if strategy not in STRATEGIES:
                # Check dynamic strategies
                dynamic_row = conn.execute(
                    "SELECT name FROM dynamic_strategies WHERE name = ?", (strategy,)
                ).fetchone()
                if not dynamic_row:
                    raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")

        with get_db() as conn:
            signals = get_signals_from_db(conn, strategy, SYMBOL, start, end)
            kpis = calculate_kpis(signals)

            return {
                "strategy": strategy,
                "symbol": SYMBOL,
                "kpis": kpis.to_dict(),
                "signal_count": len(signals)
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kpis/all")
def get_all_kpis(
    start: Optional[int] = Query(None, description="Start timestamp (Unix)"),
    end: Optional[int] = Query(None, description="End timestamp (Unix)"),
):
    """Get KPIs for all strategies (Python + dynamic) within optional date range"""
    try:
        from kpi_calculator import calculate_kpis
        from strategies.dynamic import create_dynamic_strategy

        _, get_signals_from_db, _, _, _, _, STRATEGIES = get_signal_calculator()

        results = []
        with get_db() as conn:
            # Get archived strategies
            archived_rows = conn.execute("SELECT strategy_name FROM archived_strategies").fetchall()
            archived_set = {row['strategy_name'] for row in archived_rows}

            # Python-defined strategies
            for strategy_name, strategy_class in STRATEGIES.items():
                strategy_instance = strategy_class()
                signals = get_signals_from_db(conn, strategy_name, SYMBOL, start, end)
                kpis = calculate_kpis(signals)

                results.append({
                    "strategy": strategy_name,
                    "display_name": strategy_instance.display_config.display_name,
                    "kpis": kpis.to_dict(),
                    "signal_count": len(signals),
                    "is_archived": strategy_name in archived_set,
                    "is_dynamic": False
                })

            # Dynamic strategies from DB
            dynamic_rows = conn.execute(
                "SELECT name, display_name, config FROM dynamic_strategies"
            ).fetchall()

            for row in dynamic_rows:
                config = json.loads(row['config'])
                config['name'] = row['name']
                config['display_name'] = row['display_name']
                try:
                    strategy_instance = create_dynamic_strategy(config)
                    signals = get_signals_from_db(conn, row['name'], SYMBOL, start, end)
                    kpis = calculate_kpis(signals)

                    results.append({
                        "strategy": row['name'],
                        "display_name": row['display_name'],
                        "kpis": kpis.to_dict(),
                        "signal_count": len(signals),
                        "is_archived": row['name'] in archived_set,
                        "is_dynamic": True
                    })
                except Exception as e:
                    print(f"Error calculating KPIs for dynamic strategy {row['name']}: {e}")

        return {
            "symbol": SYMBOL,
            "strategies": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# NOTIFICATION API ENDPOINTS
# ============================================================================

class NotificationSettingsRequest(BaseModel):
    enabled: bool = False
    desktop_enabled: bool = False
    telegram_enabled: bool = False
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    notify_buy: bool = True
    notify_sell: bool = True
    time_start: str = "00:00"
    time_end: str = "23:59"


class TelegramTestRequest(BaseModel):
    bot_token: str
    chat_id: str


@app.get("/api/notifications/settings")
async def get_all_notifications():
    """Get notification settings for all strategies"""
    try:
        settings = get_all_notification_settings()
        return {"settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/notifications/settings/{strategy_name}")
async def get_strategy_notifications(strategy_name: str):
    """Get notification settings for a specific strategy"""
    try:
        settings = get_notification_settings(strategy_name)
        if settings is None:
            return {"settings": None}
        return {"settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/notifications/settings/{strategy_name}")
async def update_strategy_notifications(strategy_name: str, request: NotificationSettingsRequest):
    """Create or update notification settings for a strategy"""
    try:
        settings = save_notification_settings(
            strategy_name=strategy_name,
            enabled=request.enabled,
            desktop_enabled=request.desktop_enabled,
            telegram_enabled=request.telegram_enabled,
            telegram_bot_token=request.telegram_bot_token,
            telegram_chat_id=request.telegram_chat_id,
            notify_buy=request.notify_buy,
            notify_sell=request.notify_sell,
            time_start=request.time_start,
            time_end=request.time_end
        )
        return {"settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/notifications/settings/{strategy_name}")
async def delete_strategy_notifications(strategy_name: str):
    """Delete notification settings for a strategy"""
    try:
        deleted = delete_notification_settings(strategy_name)
        return {"deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notifications/test/telegram")
async def test_telegram(request: TelegramTestRequest):
    """Test Telegram notification configuration"""
    try:
        result = await test_telegram_notification(request.bot_token, request.chat_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notifications/test/{strategy_name}")
async def test_strategy_notification(strategy_name: str):
    """Send a test notification for a strategy"""
    try:
        # Get strategy display name
        _, _, _, _, _, _, STRATEGIES = get_signal_calculator()
        strategy_class = STRATEGIES.get(strategy_name)
        if not strategy_class:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_name} not found")

        strategy_instance = strategy_class()
        display_name = strategy_instance.display_config.display_name

        # Send test notification
        result = await send_signal_notification(
            strategy_name=strategy_name,
            strategy_display_name=display_name,
            signal_type="buy",
            price=20000.00,
            timestamp=int(datetime.now(PARIS_TZ).timestamp())
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/notifications/history/{strategy_name}")
def get_strategy_notification_history(strategy_name: str, limit: int = Query(default=50, le=200)):
    """Get notification history for a strategy"""
    try:
        history = get_notification_history(strategy_name, limit)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

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
