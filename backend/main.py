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
    was_notification_already_sent,
    get_last_notification_type
)

# Import bot engine and eToro client
from bot_engine import BotEngine
import etoro_client

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

# Flag to pause background fetching during heavy DB operations
is_recalculating = False


@contextmanager
def get_db():
    """Context manager for database connection"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)  # 30 second timeout for locks
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
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
                UNIQUE(symbol, timestamp, source)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_backtest_timestamp ON backtest_candles(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_backtest_symbol_timestamp ON backtest_candles(symbol, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_backtest_symbol_source ON backtest_candles(symbol, source, timestamp)")

        # Migration: update UNIQUE constraint to include source if needed
        cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='backtest_candles'")
        existing_schema = cursor.fetchone()
        if existing_schema and 'UNIQUE(symbol, timestamp)' in existing_schema[0] and 'UNIQUE(symbol, timestamp, source)' not in existing_schema[0]:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_candles_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL DEFAULT 'NQ=F',
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER,
                    source TEXT DEFAULT 'yfinance',
                    UNIQUE(symbol, timestamp, source)
                )
            """)
            conn.execute("INSERT OR IGNORE INTO backtest_candles_new SELECT * FROM backtest_candles")
            conn.execute("DROP TABLE backtest_candles")
            conn.execute("ALTER TABLE backtest_candles_new RENAME TO backtest_candles")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_backtest_timestamp ON backtest_candles(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_backtest_symbol_timestamp ON backtest_candles(symbol, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_backtest_symbol_source ON backtest_candles(symbol, source, timestamp)")
            print("[DB] Migrated backtest_candles UNIQUE constraint to include source")

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
                data_source TEXT DEFAULT 'yfinance',
                UNIQUE(strategy_name, symbol, signal_timestamp, type, data_source)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals(strategy_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_strategy_symbol ON signals(strategy_name, symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(signal_timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_strategy_timestamp ON signals(strategy_name, signal_timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_strategy_source ON signals(strategy_name, data_source)")

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

        # Trading bots table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trading_bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                strategy_name TEXT NOT NULL,
                etoro_instrument_id INTEGER DEFAULT 0,
                amount REAL NOT NULL,
                leverage INTEGER NOT NULL DEFAULT 1,
                account_type TEXT NOT NULL DEFAULT 'demo' CHECK(account_type IN ('demo', 'real')),
                enabled INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'stopped' CHECK(status IN ('active', 'stopped', 'error')),
                consecutive_errors INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
        """)

        # Migration: add leverage column if missing
        cursor = conn.execute("PRAGMA table_info(trading_bots)")
        columns = {row[1] for row in cursor.fetchall()}
        if "leverage" not in columns:
            conn.execute("ALTER TABLE trading_bots ADD COLUMN leverage INTEGER NOT NULL DEFAULT 1")
            print("[DB] Added leverage column to trading_bots")
        if "consecutive_errors" not in columns:
            conn.execute("ALTER TABLE trading_bots ADD COLUMN consecutive_errors INTEGER NOT NULL DEFAULT 0")
            print("[DB] Added consecutive_errors column to trading_bots")
        if "signal_source" not in columns:
            conn.execute("ALTER TABLE trading_bots ADD COLUMN signal_source TEXT NOT NULL DEFAULT 'yfinance'")
            print("[DB] Added signal_source column to trading_bots")

        # Bot trades table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                position_id INTEGER,
                signal_type TEXT NOT NULL CHECK(signal_type IN ('buy', 'sell')),
                price REAL NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('open', 'closed', 'error')),
                opened_at INTEGER NOT NULL,
                closed_at INTEGER,
                pnl REAL,
                error_message TEXT,
                FOREIGN KEY (bot_id) REFERENCES trading_bots(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_bot ON bot_trades(bot_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_status ON bot_trades(status)")

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


def store_backtest_candles(candles: list, source: str = "yfinance"):
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
                ON CONFLICT(symbol, timestamp, source) DO UPDATE SET
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
                source
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
    """Get all data for WebSocket broadcast, including signals for both yfinance and etoro"""
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
        "signals": {},
        "etoro_signals": {}
    }

    # Add signals for all strategies (hardcoded + dynamic)
    try:
        _, get_signals_from_db, _, _, _, _, STRATEGIES = get_signal_calculator()
        with get_db() as conn:
            all_strategy_names = list(STRATEGIES.keys())
            # Add dynamic strategies
            dynamic_rows = conn.execute("SELECT name FROM dynamic_strategies").fetchall()
            all_strategy_names.extend(row['name'] for row in dynamic_rows)

            for strategy_name in all_strategy_names:
                # yFinance signals
                payload["signals"][strategy_name] = get_signals_from_db(conn, strategy_name, SYMBOL, data_source='yfinance')
                # eToro signals
                payload["etoro_signals"][strategy_name] = get_signals_from_db(conn, strategy_name, SYMBOL, data_source='etoro')
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
    global last_fetch_time, is_recalculating

    # Skip if recalculation is in progress to avoid DB lock conflicts
    if is_recalculating:
        print(f"[{datetime.now(PARIS_TZ).strftime('%H:%M:%S')}] Skipping fetch - recalculation in progress")
        return

    print(f"[{datetime.now(PARIS_TZ).strftime('%H:%M:%S')}] Fetching data from yfinance...")

    try:
        for interval in ["15min", "1h", "1day"]:
            fetch_and_store_data(interval)
        cleanup_old_data()
        last_fetch_time = datetime.now(PARIS_TZ)
        print(f"[{last_fetch_time.strftime('%H:%M:%S')}] Data fetched and stored successfully")

        # Fetch eToro 1H candles and store in backtest_candles
        try:
            instrument_id = etoro_client.get_instrument_id("NSDQ100")
            # Use 500 candles for initial load, 50 for regular updates
            with get_db() as conn:
                etoro_count = conn.execute(
                    "SELECT COUNT(*) FROM backtest_candles WHERE source = 'etoro'"
                ).fetchone()[0]
            candle_count = 500 if etoro_count == 0 else 50
            etoro_candles = etoro_client.get_historical_candles(instrument_id, "OneHour", candle_count)
            if etoro_candles:
                store_backtest_candles(etoro_candles, source="etoro")
                print(f"  [eToro] Stored {len(etoro_candles)} 1H candles in backtest table")
        except Exception as e:
            print(f"  [eToro] Skipping: {e}")

        # Check signals on latest candle for all strategies (using backtest_candles as single source)
        try:
            _, _, _, _, _, check_all_strategies_latest_candle, STRATEGIES = get_signal_calculator()
            with get_db() as conn:
                # yFinance signals
                results = check_all_strategies_latest_candle(conn, SYMBOL, source='yfinance')
                new_signals_count = sum(len(signals) for signals in results.values())
                print(f"  yFinance signals: {len(results)} strategies checked, {new_signals_count} new signals")

                for strategy_name, signals in results.items():
                    if not signals:
                        continue

                    # Determine which signal type we need based on last notification
                    last_type = get_last_notification_type(strategy_name)
                    needed_type = "sell" if last_type == "buy" else "buy"

                    # Find the LAST signal of the needed type
                    # (e.g., if we need "sell" and signals are [buy, sell, buy, sell], take the last sell)
                    signal_to_notify = None
                    for signal in reversed(signals):
                        if signal.type == needed_type:
                            signal_to_notify = signal
                            break

                    if signal_to_notify is None:
                        # No signal of the needed type
                        if len(signals) > 0:
                            print(f"  [{strategy_name}] {len(signals)} new signals but none of type '{needed_type}' (last notif was '{last_type}')")
                        continue

                    print(f"  [{strategy_name}] Selected {signal_to_notify.type} signal at {signal_to_notify.price} (from {len(signals)} new signals)")

                    # Send notification for the selected signal
                    try:
                        # Only send notifications for recent signals (< 15 minutes old)
                        signal_age = int(time.time()) - signal_to_notify.signal_timestamp
                        if signal_age > 900:  # 15 minutes in seconds
                            print(f"    Skipping notification for old signal ({signal_age//60}min old)")
                            continue

                        # Check if notification was already sent for this signal
                        if was_notification_already_sent(strategy_name, signal_to_notify.signal_timestamp, signal_to_notify.type):
                            print(f"    Skipping notification already sent for {signal_to_notify.type} signal")
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
                            signal_type=signal_to_notify.type,
                            price=signal_to_notify.price,
                            timestamp=signal_to_notify.signal_timestamp
                        )
                    except Exception as notif_err:
                        print(f"  Warning: Could not send notification: {notif_err}")

                # Feed yFinance signals to bot engine for auto-trading
                try:
                    bot_engine.process_new_signals(results, source='yfinance')
                except Exception as bot_err:
                    print(f"  Warning: Bot engine error: {bot_err}")

                # eToro signals
                etoro_results = check_all_strategies_latest_candle(conn, SYMBOL, source='etoro')
                etoro_new_count = sum(len(s) for s in etoro_results.values() if s)
                print(f"  eToro signals: {len(etoro_results)} strategies checked, {etoro_new_count} new signals")

                # Feed eToro signals to bot engine for auto-trading
                try:
                    bot_engine.process_new_signals(etoro_results, source='etoro')
                except Exception as bot_err:
                    print(f"  Warning: Bot engine error (eToro): {bot_err}")

                # Sync open positions with eToro (detect SL/TP closures)
                try:
                    bot_engine.sync_open_positions()
                except Exception as sync_err:
                    print(f"  Warning: Position sync error: {sync_err}")
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

# Initialize bot engine
bot_engine = BotEngine(DB_PATH)

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


@app.get("/api/backtest/sources")
def get_backtest_sources():
    """Get available data sources for backtesting"""
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT source, COUNT(*) as count,
                       MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
                FROM backtest_candles
                WHERE symbol = ? AND source != 'etoro'
                GROUP BY source
            """, (SYMBOL,)).fetchall()

            sources = []
            for row in rows:
                min_date = datetime.fromtimestamp(row["min_ts"], tz=PARIS_TZ)
                max_date = datetime.fromtimestamp(row["max_ts"], tz=PARIS_TZ)
                days_coverage = (max_date - min_date).days
                years_coverage = days_coverage / 365.25

                sources.append({
                    "source": row["source"],
                    "count": row["count"],
                    "start_date": min_date.strftime("%Y-%m-%d"),
                    "end_date": max_date.strftime("%Y-%m-%d"),
                    "days_coverage": days_coverage,
                    "years_coverage": round(years_coverage, 1)
                })

            return {"sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtest/info")
def get_backtest_info(
    source: Optional[str] = Query(None, description="Data source: 'yfinance' or 'firstrate'")
):
    """Get information about available backtesting data"""
    try:
        with get_db() as conn:
            if source:
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as count,
                        MIN(timestamp) as min_ts,
                        MAX(timestamp) as max_ts
                    FROM backtest_candles
                    WHERE symbol = ? AND source = ?
                """, (SYMBOL, source))
            else:
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
                    "source": source,
                    "count": 0,
                    "message": "No backtesting data available. Run bootstrap script."
                }

            min_date = datetime.fromtimestamp(row["min_ts"], tz=PARIS_TZ)
            max_date = datetime.fromtimestamp(row["max_ts"], tz=PARIS_TZ)
            days_coverage = (max_date - min_date).days

            return {
                "symbol": SYMBOL,
                "source": source,
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
    source: Optional[str] = Query(None, description="Data source: 'yfinance' or 'firstrate'"),
    limit: int = Query(10000, description="Max candles to return")
):
    """Get backtesting data with optional date range and source filter"""
    try:
        with get_db() as conn:
            # Build query dynamically
            conditions = ["symbol = ?"]
            params = [SYMBOL]

            if source:
                conditions.append("source = ?")
                params.append(source)
            if start:
                conditions.append("timestamp >= ?")
                params.append(start)
            if end:
                conditions.append("timestamp <= ?")
                params.append(end)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            query = f"""
                SELECT timestamp, open, high, low, close, volume
                FROM backtest_candles
                WHERE {where_clause}
                ORDER BY timestamp ASC
                LIMIT ?
            """
            rows = conn.execute(query, params).fetchall()

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
                "source": source,
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
    data_source: Optional[str] = Query(None, description="Data source: 'yfinance' or 'firstrate'"),
    limit: int = Query(10000, description="Max signals to return")
):
    """Get signals for a strategy within optional date range and data source"""
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
            signals = get_signals_from_db(conn, strategy, SYMBOL, start, end, limit, data_source)

            return {
                "strategy": strategy,
                "symbol": SYMBOL,
                "data_source": data_source,
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


@app.post("/api/fetch")
def manual_fetch():
    """Manually trigger a fetch of latest market data from yfinance (15min, 1h, 1day).
    Also broadcasts updated data to all WebSocket clients."""
    try:
        fetch_all_intervals()
        # Broadcast fresh data to all connected clients
        if connected_clients:
            broadcast_to_clients(get_all_data_payload())
        return {"message": "Fetch complete", "last_fetch": last_fetch_time.strftime("%H:%M:%S") if last_fetch_time else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/signals/recalculate")
def recalculate_signals(
    strategy: Optional[str] = Query(default=None, description="Strategy name to recalculate (all if not specified)"),
    data_source: str = Query(default="yfinance", description="Data source: 'yfinance' or 'firstrate'")
):
    """
    Force full recalculation of signals from backtest_candles.
    Use in backtesting to catch missed signals when backend wasn't running.
    Does NOT send notifications (safe to use anytime).

    Args:
        data_source: Which candle data to use ('yfinance' or 'firstrate')
    """
    global is_recalculating
    try:
        is_recalculating = True
        print(f"[Recalculate] Starting recalculation for data_source={data_source}...")

        # Fetch latest yfinance data before recalculating
        if data_source == "yfinance":
            from bootstrap_backtest import fetch_latest_yfinance_data
            with get_db() as conn:
                new_candles = fetch_latest_yfinance_data(conn, SYMBOL)
                if new_candles > 0:
                    print(f"[Recalculate] Fetched {new_candles} new yfinance candles")

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
                count = recalculate_strategy_fn(conn, strategy, SYMBOL, data_source)
                print(f"[Recalculate] Done - {count} signals for {strategy} (data_source={data_source})")
                return {"strategy": strategy, "data_source": data_source, "signals_count": count, "message": "Recalculation complete (no notifications sent)"}
            else:
                results = recalculate_all_strategies_fn(conn, SYMBOL, data_source)
                total = sum(results.values())
                print(f"[Recalculate] Done - {total} signals across {len(results)} strategies (data_source={data_source})")
                return {"strategies": results, "data_source": data_source, "total_signals": total, "message": "Recalculation complete (no notifications sent)"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        is_recalculating = False


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

        # Run initial signal calculation for both data sources
        calculate_signals_incremental, _, _, _, _, _, _ = get_signal_calculator()
        with get_db() as conn:
            # Get available data sources
            sources = conn.execute(
                "SELECT DISTINCT source FROM backtest_candles WHERE symbol = ?", (SYMBOL,)
            ).fetchall()

            for (source,) in sources:
                calculate_signals_incremental(
                    conn, name, SYMBOL, source, 'backtest_candles',
                    strategy_instance=strategy
                )

            # Get actual counts from database
            signals_by_source = {}
            for (source,) in sources:
                count = conn.execute(
                    "SELECT COUNT(*) FROM signals WHERE strategy_name = ? AND data_source = ?",
                    (name, source)
                ).fetchone()[0]
                signals_by_source[source] = count

        return {
            "status": "created",
            "strategy": {
                "name": name,
                "display_name": display_name,
                "config": config,
                "signals_count": signals_by_source
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
        conn = sqlite3.connect(DB_PATH, timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            existing = conn.execute(
                "SELECT name FROM dynamic_strategies WHERE name = ?", (name,)
            ).fetchone()

            if not existing:
                conn.close()
                raise HTTPException(status_code=404, detail=f"Dynamic strategy not found: {name}")

            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM dynamic_strategies WHERE name = ?", (name,))
            conn.execute("DELETE FROM signals WHERE strategy_name = ?", (name,))
            conn.execute("DELETE FROM signal_processing_state WHERE strategy_name = ?", (name,))
            conn.execute("DELETE FROM notification_settings WHERE strategy_name = ?", (name,))
            conn.execute("DELETE FROM notification_history WHERE strategy_name = ?", (name,))
            conn.execute("DELETE FROM archived_strategies WHERE strategy_name = ?", (name,))
            conn.execute("COMMIT")
        except HTTPException:
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

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
    """Delete a strategy and all its data (signals, settings, history)."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM dynamic_strategies WHERE name = ?", (strategy_name,))
            conn.execute("DELETE FROM signals WHERE strategy_name = ?", (strategy_name,))
            conn.execute("DELETE FROM signal_processing_state WHERE strategy_name = ?", (strategy_name,))
            conn.execute("DELETE FROM notification_settings WHERE strategy_name = ?", (strategy_name,))
            conn.execute("DELETE FROM notification_history WHERE strategy_name = ?", (strategy_name,))
            conn.execute("DELETE FROM archived_strategies WHERE strategy_name = ?", (strategy_name,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

        return {"status": "deleted", "strategy": strategy_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kpis")
def get_kpis(
    strategy: str = Query(..., description="Strategy name (e.g., 'bollinger-nosl')"),
    start: Optional[int] = Query(None, description="Start timestamp (Unix)"),
    end: Optional[int] = Query(None, description="End timestamp (Unix)"),
    data_source: Optional[str] = Query(None, description="Data source: 'yfinance' or 'firstrate'"),
):
    """Get KPIs for a strategy within optional date range and data source"""
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
            signals = get_signals_from_db(conn, strategy, SYMBOL, start, end, data_source=data_source)
            kpis = calculate_kpis(signals)

            return {
                "strategy": strategy,
                "symbol": SYMBOL,
                "data_source": data_source,
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
    data_source: Optional[str] = Query(None, description="Data source: 'yfinance' or 'firstrate'"),
    include_archived: bool = Query(True, description="Include archived strategies"),
):
    """Get KPIs for all strategies (Python + dynamic) within optional date range and data source"""
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
                is_archived = strategy_name in archived_set
                if not include_archived and is_archived:
                    continue

                strategy_instance = strategy_class()
                signals = get_signals_from_db(conn, strategy_name, SYMBOL, start, end, data_source=data_source)
                kpis = calculate_kpis(signals)

                results.append({
                    "strategy": strategy_name,
                    "display_name": strategy_instance.display_config.display_name,
                    "kpis": kpis.to_dict(),
                    "signal_count": len(signals),
                    "is_archived": is_archived,
                    "is_dynamic": False
                })

            # Dynamic strategies from DB
            dynamic_rows = conn.execute(
                "SELECT name, display_name, config FROM dynamic_strategies"
            ).fetchall()

            for row in dynamic_rows:
                is_archived = row['name'] in archived_set
                if not include_archived and is_archived:
                    continue

                config = json.loads(row['config'])
                config['name'] = row['name']
                config['display_name'] = row['display_name']
                try:
                    strategy_instance = create_dynamic_strategy(config)
                    signals = get_signals_from_db(conn, row['name'], SYMBOL, start, end, data_source=data_source)
                    kpis = calculate_kpis(signals)

                    results.append({
                        "strategy": row['name'],
                        "display_name": row['display_name'],
                        "kpis": kpis.to_dict(),
                        "signal_count": len(signals),
                        "is_archived": is_archived,
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
# TRADING BOTS API ENDPOINTS
# ============================================================================

class BotCreateRequest(BaseModel):
    name: str
    strategy_name: str
    amount: float
    leverage: int = 1
    account_type: str = "demo"
    signal_source: str = "yfinance"


class BotUpdateRequest(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    leverage: Optional[int] = None
    account_type: Optional[str] = None
    signal_source: Optional[str] = None


@app.get("/api/bots")
def list_bots():
    """List all trading bots with their stats and live P&L for open positions."""
    try:
        bots = bot_engine.list_bots()
        for bot in bots:
            stats = bot_engine.get_bot_stats(bot["id"])
            # Fetch live P&L for open positions
            if stats["open_positions"] > 0:
                live_pnl = _get_bot_live_pnl(bot["id"], bot["account_type"])
                stats["live_pnl"] = live_pnl
            else:
                stats["live_pnl"] = None
            bot["stats"] = stats
        return {"bots": bots}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_bot_live_pnl(bot_id: int, account_type: str) -> Optional[float]:
    """Sum live P&L of all open positions for a bot.
    Tries eToro API first, falls back to price-based estimate."""
    try:
        with get_db() as conn:
            open_trades = conn.execute(
                "SELECT position_id, price, amount FROM bot_trades WHERE bot_id = ? AND status = 'open'",
                (bot_id,),
            ).fetchall()
        if not open_trades:
            return None

        # Try eToro API for each open position
        total = 0.0
        found_any = False
        for trade in open_trades:
            if trade["position_id"]:
                pnl = etoro_client.get_position_pnl(trade["position_id"], account_type)
                if pnl is not None:
                    total += pnl
                    found_any = True
                    continue
            # Fallback: estimate from last known price
            with get_db() as conn:
                last_price_row = conn.execute(
                    "SELECT close FROM backtest_candles WHERE source = 'yfinance' ORDER BY timestamp DESC LIMIT 1"
                ).fetchone()
            if last_price_row and trade["price"]:
                estimated = ((last_price_row[0] - trade["price"]) / trade["price"]) * trade["amount"]
                total += estimated
                found_any = True

        return round(total, 2) if found_any else None
    except Exception:
        return None


@app.post("/api/bots")
def create_bot(request: BotCreateRequest):
    """Create a new trading bot."""
    try:
        if not request.name.strip():
            raise HTTPException(status_code=400, detail="Bot name cannot be empty")
        if request.amount < 10:
            raise HTTPException(status_code=400, detail="Minimum amount is $10")
        if request.leverage < 1:
            raise HTTPException(status_code=400, detail="Leverage must be at least 1")
        if request.account_type not in ("demo", "real"):
            raise HTTPException(status_code=400, detail="Account type must be 'demo' or 'real'")
        # Check strategy exists (built-in or dynamic)
        from strategies import STRATEGIES
        strategy_exists = request.strategy_name in STRATEGIES
        if not strategy_exists:
            with get_db() as conn:
                dynamic = conn.execute(
                    "SELECT name FROM dynamic_strategies WHERE name = ?", (request.strategy_name,)
                ).fetchone()
                strategy_exists = dynamic is not None
        if not strategy_exists:
            raise HTTPException(status_code=400, detail=f"Strategy not found: {request.strategy_name}")
        if request.signal_source not in ("yfinance", "etoro"):
            raise HTTPException(status_code=400, detail="Signal source must be 'yfinance' or 'etoro'")
        bot = bot_engine.create_bot(
            name=request.name,
            strategy_name=request.strategy_name,
            amount=request.amount,
            leverage=request.leverage,
            account_type=request.account_type,
            signal_source=request.signal_source,
        )
        bot["stats"] = bot_engine.get_bot_stats(bot["id"])
        return {"bot": bot}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bots/{bot_id}")
def get_bot(bot_id: int):
    """Get a trading bot by ID."""
    bot = bot_engine.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot not found: {bot_id}")
    bot["stats"] = bot_engine.get_bot_stats(bot_id)
    return {"bot": bot}


@app.put("/api/bots/{bot_id}")
def update_bot(bot_id: int, request: BotUpdateRequest):
    """Update a trading bot."""
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        if "signal_source" in updates and updates["signal_source"] not in ("yfinance", "etoro"):
            raise HTTPException(status_code=400, detail="Signal source must be 'yfinance' or 'etoro'")
        bot = bot_engine.update_bot(bot_id, **updates)
        if not bot:
            raise HTTPException(status_code=404, detail=f"Bot not found: {bot_id}")
        bot["stats"] = bot_engine.get_bot_stats(bot_id)
        return {"bot": bot}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/bots/{bot_id}")
def delete_bot(bot_id: int):
    """Delete a trading bot and its trade history."""
    deleted = bot_engine.delete_bot(bot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Bot not found: {bot_id}")
    return {"status": "deleted", "bot_id": bot_id}


@app.post("/api/bots/{bot_id}/start")
def start_bot(bot_id: int):
    """Start a trading bot (enable auto-trading)."""
    bot = bot_engine.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot not found: {bot_id}")
    # Check account balance before starting
    try:
        balance = etoro_client.get_account_balance(bot["account_type"])
        available = balance.get("available", 0)
        if available < bot["amount"]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance: ${available:.2f} available, ${bot['amount']:.2f} required"
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Warning: Could not check balance: {e}")
        # Allow start even if balance check fails (eToro API might be down)
    bot = bot_engine.start_bot(bot_id)
    bot["stats"] = bot_engine.get_bot_stats(bot_id)
    return {"bot": bot}


@app.post("/api/bots/{bot_id}/stop")
def stop_bot(bot_id: int):
    """Stop a trading bot (kill switch)."""
    bot = bot_engine.stop_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot not found: {bot_id}")
    bot["stats"] = bot_engine.get_bot_stats(bot_id)
    return {"bot": bot}


@app.get("/api/bots/{bot_id}/trades")
def get_bot_trades(bot_id: int, limit: int = Query(default=50, le=200)):
    """Get trade history for a bot, with live P&L for open positions."""
    bot = bot_engine.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot not found: {bot_id}")
    trades = bot_engine.get_trades(bot_id, limit)
    # Enrich open trades with live P&L from eToro (fallback to price estimate)
    for trade in trades:
        if trade.get("status") == "open":
            live_pnl = None
            # Try eToro API first
            if trade.get("position_id"):
                try:
                    live_pnl = etoro_client.get_position_pnl(
                        position_id=trade["position_id"],
                        account_type=bot["account_type"],
                    )
                except Exception:
                    pass
            # Fallback: estimate from last known price
            if live_pnl is None and trade.get("price"):
                try:
                    with get_db() as conn:
                        last_price_row = conn.execute(
                            "SELECT close FROM backtest_candles WHERE source = 'yfinance' ORDER BY timestamp DESC LIMIT 1"
                        ).fetchone()
                    if last_price_row:
                        live_pnl = round(((last_price_row[0] - trade["price"]) / trade["price"]) * trade["amount"], 2)
                except Exception:
                    pass
            trade["live_pnl"] = live_pnl
        else:
            trade["live_pnl"] = None
    return {"trades": trades}


@app.get("/api/bots/trades/all")
def get_all_bot_trades(limit: int = Query(default=100, le=500)):
    """Get recent trades across all bots."""
    trades = bot_engine.get_all_trades(limit)
    return {"trades": trades}


# ============================================================================
# ETORO DATA ENDPOINTS
# ============================================================================

@app.get("/api/etoro/instrument")
def get_etoro_instrument(symbol: str = Query(default="NSDQ100")):
    """Search for an eToro instrument by symbol."""
    try:
        result = etoro_client.search_instrument(symbol)
        if not result:
            raise HTTPException(status_code=404, detail=f"Instrument not found: {symbol}")
        return {"instrument": result}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/etoro/rates")
def get_etoro_rates(symbol: str = Query(default="NSDQ100")):
    """Get current bid/ask rates from eToro."""
    try:
        instrument_id = etoro_client.get_instrument_id(symbol)
        rates = etoro_client.get_current_rates([instrument_id])
        return {"rates": rates, "instrument_id": instrument_id}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/etoro/candles")
def get_etoro_candles(
    symbol: str = Query(default="NSDQ100"),
    interval: str = Query(default="1h", description="Interval: 15min, 1h, 1day"),
    count: int = Query(default=500, le=1000),
):
    """Get historical candles from eToro."""
    try:
        instrument_id = etoro_client.get_instrument_id(symbol)
        etoro_interval = etoro_client.get_etoro_interval(interval)
        candles = etoro_client.get_historical_candles(instrument_id, etoro_interval, count)
        return {
            "symbol": symbol,
            "interval": interval,
            "instrument_id": instrument_id,
            "data": candles,
            "count": len(candles),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/etoro/portfolio")
def get_etoro_portfolio(account_type: str = Query(default="demo")):
    """Get eToro portfolio details."""
    try:
        portfolio = etoro_client.get_portfolio(account_type)
        return {"portfolio": portfolio}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/etoro/balance")
def get_etoro_balance():
    """Get eToro account balances for demo and real accounts."""
    balances = {}
    for account_type in ("demo", "real"):
        try:
            balances[account_type] = etoro_client.get_account_balance(account_type)
        except Exception as e:
            balances[account_type] = {"account_type": account_type, "error": str(e)}
    return {"balances": balances}


@app.get("/api/realtime/sources")
def get_realtime_sources():
    """Get available real-time data sources."""
    sources = [
        {
            "source": "yfinance",
            "label": "yFinance",
            "description": "Yahoo Finance data (~10min delay)",
        },
        {
            "source": "etoro",
            "label": "eToro",
            "description": "eToro real-time market data",
        },
    ]
    return {"sources": sources}


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
