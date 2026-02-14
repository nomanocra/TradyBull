#!/usr/bin/env python3
"""
Bootstrap script to download maximum historical 1h data for backtesting.
Run this once to populate the backtest_candles table with ~730 days of data.

Usage:
    python bootstrap_backtest.py [--force]

Options:
    --force    Re-download and update existing data (uses INSERT OR REPLACE)
"""

import yfinance as yf
import sqlite3
import os
import sys
from datetime import datetime
import pytz

PARIS_TZ = pytz.timezone('Europe/Paris')
SYMBOL = "NQ=F"
DB_PATH = os.path.join(os.path.dirname(__file__), "tradybull.db")


def init_backtest_table(conn):
    """Ensure the backtest_candles table exists"""
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
    conn.commit()


def fetch_latest_yfinance_data(conn, symbol=SYMBOL):
    """Fetch only new yfinance candles since the last one in the database.
    Uses INSERT OR IGNORE so existing data is never deleted or overwritten.
    Returns the number of new candles inserted."""

    cursor = conn.execute(
        "SELECT COUNT(*), MAX(timestamp) FROM backtest_candles WHERE symbol = ? AND source = 'yfinance'",
        (symbol,)
    )
    row = cursor.fetchone()
    existing_count = row[0]
    last_ts = row[1]

    if existing_count == 0 or last_ts is None:
        print("[FetchLatest] No existing yfinance data. Run bootstrap_backtest.py first.")
        return 0

    last_dt = datetime.fromtimestamp(last_ts, tz=PARIS_TZ)
    gap_hours = (datetime.now(PARIS_TZ) - last_dt).total_seconds() / 3600

    if gap_hours < 2:
        print(f"[FetchLatest] Data is up to date (last candle: {last_dt.strftime('%Y-%m-%d %H:%M')})")
        return 0

    print(f"[FetchLatest] Fetching gap data ({gap_hours:.1f} hours since last candle at {last_dt.strftime('%Y-%m-%d %H:%M')})")
    period = "7d" if gap_hours <= 168 else "1mo"

    ticker = yf.Ticker(symbol)
    try:
        data = ticker.history(period=period, interval="1h")
    except Exception as e:
        print(f"[FetchLatest] Error fetching with period={period}: {e}")
        return 0

    if data.empty:
        print("[FetchLatest] No data received from yfinance")
        return 0

    print(f"[FetchLatest] Received {len(data)} candles from yfinance")

    candles = []
    for timestamp_idx, candle_row in data.iterrows():
        if timestamp_idx.tzinfo is None:
            ts_utc = pytz.utc.localize(timestamp_idx)
        else:
            ts_utc = timestamp_idx.astimezone(pytz.utc)
        ts_paris = ts_utc.astimezone(PARIS_TZ)

        candles.append((
            symbol,
            int(ts_paris.timestamp()),
            round(candle_row["Open"], 2),
            round(candle_row["High"], 2),
            round(candle_row["Low"], 2),
            round(candle_row["Close"], 2),
            int(candle_row["Volume"]) if candle_row["Volume"] else 0,
            "yfinance"
        ))

    # INSERT OR IGNORE: never overwrite existing data
    conn.executemany(
        """INSERT OR IGNORE INTO backtest_candles
           (symbol, timestamp, open, high, low, close, volume, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        candles
    )
    conn.commit()

    new_count = conn.execute(
        "SELECT COUNT(*) FROM backtest_candles WHERE symbol = ? AND source = 'yfinance' AND timestamp > ?",
        (symbol, last_ts)
    ).fetchone()[0]

    print(f"[FetchLatest] Inserted {new_count} new candles")
    return new_count


def bootstrap_backtest_data(force: bool = False):
    """Download maximum available 1h data and store in backtest_candles table."""

    print(f"[Bootstrap] Starting historical data download for {SYMBOL}")
    print(f"[Bootstrap] Database: {DB_PATH}")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Ensure table exists
    init_backtest_table(conn)

    # Check current state
    cursor = conn.execute(
        "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM backtest_candles WHERE symbol = ?",
        (SYMBOL,)
    )
    row = cursor.fetchone()
    existing_count = row[0]

    if existing_count > 0 and not force:
        min_date = datetime.fromtimestamp(row[1], tz=PARIS_TZ).strftime('%Y-%m-%d')
        max_date = datetime.fromtimestamp(row[2], tz=PARIS_TZ).strftime('%Y-%m-%d')
        print(f"[Bootstrap] Found {existing_count} existing candles ({min_date} to {max_date})")
        print("[Bootstrap] Use --force to re-download and update")

        # In non-force mode, only fetch new data
        last_ts = row[2]
        last_dt = datetime.fromtimestamp(last_ts, tz=PARIS_TZ)
        gap_hours = (datetime.now(PARIS_TZ) - last_dt).total_seconds() / 3600

        if gap_hours < 2:
            print("[Bootstrap] Data is up to date. Nothing to do.")
            conn.close()
            return

        print(f"[Bootstrap] Fetching gap data ({gap_hours:.1f} hours since last candle)")
        period = "7d" if gap_hours <= 168 else "1mo"
    else:
        # Full bootstrap - fetch maximum data (730 days for 1h)
        period = "730d"
        print("[Bootstrap] Full bootstrap - fetching maximum available data (730 days)")

    # Fetch from yfinance
    print(f"[Bootstrap] Downloading {SYMBOL} 1h data (period={period})...")
    ticker = yf.Ticker(SYMBOL)

    try:
        data = ticker.history(period=period, interval="1h")
    except Exception as e:
        print(f"[Bootstrap] Error fetching with period={period}: {e}")
        print("[Bootstrap] Trying with period=max...")
        try:
            data = ticker.history(period="max", interval="1h")
        except Exception as e2:
            print(f"[Bootstrap] Error with period=max: {e2}")
            print("[Bootstrap] Trying with period=2y...")
            data = ticker.history(period="2y", interval="1h")

    if data.empty:
        print("[Bootstrap] ERROR: No data received from yfinance")
        conn.close()
        return

    print(f"[Bootstrap] Received {len(data)} candles")

    # Convert and prepare for insertion
    candles = []
    for timestamp, row in data.iterrows():
        # Convert to Paris timezone
        if timestamp.tzinfo is None:
            ts_utc = pytz.utc.localize(timestamp)
        else:
            ts_utc = timestamp.astimezone(pytz.utc)
        ts_paris = ts_utc.astimezone(PARIS_TZ)

        candles.append((
            SYMBOL,
            int(ts_paris.timestamp()),
            round(row["Open"], 2),
            round(row["High"], 2),
            round(row["Low"], 2),
            round(row["Close"], 2),
            int(row["Volume"]) if row["Volume"] else 0,
            "yfinance"
        ))

    # Insert into database
    insert_sql = """
        INSERT OR IGNORE INTO backtest_candles
        (symbol, timestamp, open, high, low, close, volume, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """ if not force else """
        INSERT OR REPLACE INTO backtest_candles
        (symbol, timestamp, open, high, low, close, volume, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    print(f"[Bootstrap] Inserting into backtest_candles...")
    conn.executemany(insert_sql, candles)
    conn.commit()

    # Report results
    cursor = conn.execute("SELECT COUNT(*) FROM backtest_candles WHERE symbol = ?", (SYMBOL,))
    total_count = cursor.fetchone()[0]

    cursor = conn.execute(
        "SELECT MIN(timestamp), MAX(timestamp) FROM backtest_candles WHERE symbol = ?",
        (SYMBOL,)
    )
    row = cursor.fetchone()
    min_date = datetime.fromtimestamp(row[0], tz=PARIS_TZ).strftime('%Y-%m-%d %H:%M')
    max_date = datetime.fromtimestamp(row[1], tz=PARIS_TZ).strftime('%Y-%m-%d %H:%M')

    print(f"[Bootstrap] Complete!")
    print(f"[Bootstrap] Total candles: {total_count}")
    print(f"[Bootstrap] Date range: {min_date} to {max_date}")

    # Calculate approximate days
    days = (row[1] - row[0]) / 86400
    print(f"[Bootstrap] Coverage: ~{days:.0f} days ({days/365:.1f} years)")

    conn.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    bootstrap_backtest_data(force=force)
