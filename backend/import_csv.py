#!/usr/bin/env python3
"""
CSV Import utility for FirstRate Data historical files.
Use this to import 15+ years of historical 1h data for backtesting.

Expected CSV format (FirstRate Data):
    DateTime,Open,High,Low,Close,Volume
    2007-01-02 18:00:00,1234.50,1235.00,1234.25,1234.75,1000

Usage:
    python import_csv.py <csv_file> [--symbol NQ=F] [--timezone US/Eastern]

Options:
    --symbol      Symbol name (default: NQ=F)
    --timezone    Source timezone of CSV data (default: US/Eastern)
    --force       Replace existing data (default: skip duplicates)
"""

import csv
import sqlite3
import os
import sys
from datetime import datetime
import pytz

PARIS_TZ = pytz.timezone('Europe/Paris')
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
            UNIQUE(symbol, timestamp)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_backtest_timestamp ON backtest_candles(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_backtest_symbol_timestamp ON backtest_candles(symbol, timestamp)")
    conn.commit()


def import_firstrate_csv(
    csv_path: str,
    symbol: str = "NQ=F",
    source_tz: str = "US/Eastern",
    force: bool = False
):
    """Import FirstRate Data CSV into backtest_candles table."""

    if not os.path.exists(csv_path):
        print(f"ERROR: File not found: {csv_path}")
        return

    print(f"[Import] Reading {csv_path}")
    print(f"[Import] Symbol: {symbol}")
    print(f"[Import] Source timezone: {source_tz}")

    conn = sqlite3.connect(DB_PATH)
    init_backtest_table(conn)

    # Count rows for progress
    with open(csv_path, 'r') as f:
        total_rows = sum(1 for _ in f) - 1  # Minus header
    print(f"[Import] Total rows: {total_rows}")

    # Process CSV
    inserted = 0
    skipped = 0
    errors = 0
    source_timezone = pytz.timezone(source_tz)

    insert_sql = """
        INSERT OR IGNORE INTO backtest_candles
        (symbol, timestamp, open, high, low, close, volume, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """ if not force else """
        INSERT OR REPLACE INTO backtest_candles
        (symbol, timestamp, open, high, low, close, volume, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)

        batch = []
        for i, row in enumerate(reader):
            try:
                # Try multiple datetime formats
                dt_str = row.get('DateTime') or row.get('datetime') or row.get('Date') or row.get('date')

                # Common FirstRate formats
                for fmt in [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d %H:%M',
                    '%m/%d/%Y %H:%M:%S',
                    '%m/%d/%Y %H:%M',
                ]:
                    try:
                        dt = datetime.strptime(dt_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"Could not parse datetime: {dt_str}")

                # Convert to Paris timezone
                dt_source = source_timezone.localize(dt)
                dt_paris = dt_source.astimezone(PARIS_TZ)

                # Get OHLCV values (handle different column naming conventions)
                open_val = float(row.get('Open') or row.get('open') or row.get('OPEN'))
                high_val = float(row.get('High') or row.get('high') or row.get('HIGH'))
                low_val = float(row.get('Low') or row.get('low') or row.get('LOW'))
                close_val = float(row.get('Close') or row.get('close') or row.get('CLOSE'))
                volume_val = int(float(row.get('Volume') or row.get('volume') or row.get('VOLUME') or 0))

                batch.append((
                    symbol,
                    int(dt_paris.timestamp()),
                    open_val,
                    high_val,
                    low_val,
                    close_val,
                    volume_val,
                    "firstrate"
                ))

                # Batch insert every 1000 rows
                if len(batch) >= 1000:
                    cursor = conn.executemany(insert_sql, batch)
                    inserted += len(batch)
                    batch = []

                    if (i + 1) % 10000 == 0:
                        conn.commit()
                        print(f"[Import] Progress: {i + 1}/{total_rows} ({100 * (i + 1) / total_rows:.1f}%)")

            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"[Import] Error at row {i + 1}: {e}")
                elif errors == 6:
                    print("[Import] ... (suppressing further error messages)")

        # Insert remaining batch
        if batch:
            conn.executemany(insert_sql, batch)
            inserted += len(batch)

    conn.commit()

    # Report results
    cursor = conn.execute("SELECT COUNT(*) FROM backtest_candles WHERE symbol = ?", (symbol,))
    total_count = cursor.fetchone()[0]

    cursor = conn.execute(
        "SELECT MIN(timestamp), MAX(timestamp) FROM backtest_candles WHERE symbol = ?",
        (symbol,)
    )
    row = cursor.fetchone()

    if row[0]:
        min_date = datetime.fromtimestamp(row[0], tz=PARIS_TZ).strftime('%Y-%m-%d %H:%M')
        max_date = datetime.fromtimestamp(row[1], tz=PARIS_TZ).strftime('%Y-%m-%d %H:%M')
        days = (row[1] - row[0]) / 86400

        print(f"[Import] Complete!")
        print(f"[Import] Rows processed: {inserted}")
        print(f"[Import] Errors: {errors}")
        print(f"[Import] Total candles in DB: {total_count}")
        print(f"[Import] Date range: {min_date} to {max_date}")
        print(f"[Import] Coverage: ~{days:.0f} days ({days / 365:.1f} years)")
    else:
        print(f"[Import] Complete but no data in table")

    conn.close()


def print_usage():
    print(__doc__)
    print("\nExample:")
    print("  python import_csv.py NQ_continuous_1h.csv --symbol NQ=F")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    csv_path = sys.argv[1]

    # Parse optional arguments
    symbol = "NQ=F"
    timezone = "US/Eastern"
    force = False

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--symbol" and i + 1 < len(sys.argv):
            symbol = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--timezone" and i + 1 < len(sys.argv):
            timezone = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--force":
            force = True
            i += 1
        else:
            i += 1

    import_firstrate_csv(csv_path, symbol, timezone, force)
