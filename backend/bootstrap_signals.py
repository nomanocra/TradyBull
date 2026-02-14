#!/usr/bin/env python3
"""
Bootstrap script to calculate all signals for backtest data.
Run this after bootstrap_backtest.py to populate the signals table.

Usage:
    python bootstrap_signals.py                     # Calculate for all strategies
    python bootstrap_signals.py --strategy bollinger-nosl  # Calculate for specific strategy
    python bootstrap_signals.py --force             # Clear existing and recalculate

Examples:
    # First time setup (after bootstrap_backtest.py)
    python bootstrap_signals.py

    # Force recalculation of all signals
    python bootstrap_signals.py --force

    # Recalculate only bollinger-nosl signals
    python bootstrap_signals.py --strategy bollinger-nosl --force
"""

import sqlite3
import os
import sys
import argparse
from datetime import datetime
import pytz

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from signal_calculator import calculate_signals_incremental, get_signals_from_db
from strategies import STRATEGIES

DB_PATH = os.path.join(os.path.dirname(__file__), "tradybull.db")
SYMBOL = "NQ=F"
PARIS_TZ = pytz.timezone('Europe/Paris')


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def clear_signals(conn: sqlite3.Connection, strategy_name: str = None, data_source: str = None):
    """Clear existing signals and processing state"""
    if strategy_name and data_source:
        conn.execute("DELETE FROM signals WHERE strategy_name = ? AND symbol = ? AND data_source = ?",
                     (strategy_name, SYMBOL, data_source))
        conn.execute("DELETE FROM signal_processing_state WHERE strategy_name = ? AND symbol = ? AND data_source = ?",
                     (strategy_name, SYMBOL, data_source))
        print(f"  Cleared existing signals for {strategy_name} ({data_source})")
    elif data_source:
        conn.execute("DELETE FROM signals WHERE symbol = ? AND data_source = ?", (SYMBOL, data_source))
        conn.execute("DELETE FROM signal_processing_state WHERE symbol = ? AND data_source = ?", (SYMBOL, data_source))
        print(f"  Cleared all existing signals for {data_source}")
    elif strategy_name:
        conn.execute("DELETE FROM signals WHERE strategy_name = ? AND symbol = ?", (strategy_name, SYMBOL))
        conn.execute("DELETE FROM signal_processing_state WHERE strategy_name = ? AND symbol = ?",
                     (strategy_name, SYMBOL))
        print(f"  Cleared existing signals for {strategy_name}")
    else:
        conn.execute("DELETE FROM signals WHERE symbol = ?", (SYMBOL,))
        conn.execute("DELETE FROM signal_processing_state WHERE symbol = ?", (SYMBOL,))
        print("  Cleared all existing signals")
    conn.commit()


def get_backtest_info(conn: sqlite3.Connection, source: str = None) -> dict:
    """Get information about available backtest data"""
    if source:
        cursor = conn.execute("""
            SELECT COUNT(*) as count, MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
            FROM backtest_candles
            WHERE symbol = ? AND source = ?
        """, (SYMBOL, source))
    else:
        cursor = conn.execute("""
            SELECT COUNT(*) as count, MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
            FROM backtest_candles
            WHERE symbol = ?
        """, (SYMBOL,))
    row = cursor.fetchone()

    if row['count'] == 0:
        return None

    min_date = datetime.fromtimestamp(row['min_ts'], tz=PARIS_TZ)
    max_date = datetime.fromtimestamp(row['max_ts'], tz=PARIS_TZ)

    return {
        'count': row['count'],
        'min_ts': row['min_ts'],
        'max_ts': row['max_ts'],
        'start_date': min_date.strftime('%Y-%m-%d'),
        'end_date': max_date.strftime('%Y-%m-%d'),
        'days': (max_date - min_date).days,
        'source': source
    }


def get_all_strategy_names(conn: sqlite3.Connection) -> list:
    """Get all strategy names from both registry and dynamic strategies"""
    names = list(STRATEGIES.keys())

    # Add dynamic strategies from database
    cursor = conn.execute("SELECT name FROM dynamic_strategies")
    for row in cursor:
        if row[0] not in names:
            names.append(row[0])

    return names


def bootstrap_signals(strategy_name: str = None, force: bool = False, source: str = None):
    """Bootstrap signals calculation for backtest data"""
    print(f"\n{'=' * 60}")
    print("Bootstrap Signals - TradyBull")
    print(f"{'=' * 60}\n")

    conn = get_db()

    # Get available data sources
    cursor = conn.execute("SELECT DISTINCT source FROM backtest_candles WHERE symbol = ?", (SYMBOL,))
    available_sources = [row[0] for row in cursor.fetchall()]

    if source and source not in available_sources:
        print(f"ERROR: Source '{source}' not found. Available: {available_sources}")
        conn.close()
        return

    # If no source specified, run for all available sources
    sources_to_run = [source] if source else available_sources
    print(f"Data sources to process: {sources_to_run}")
    print()

    # Determine which strategies to run (including dynamic strategies)
    all_strategies = get_all_strategy_names(conn)
    strategies_to_run = [strategy_name] if strategy_name else all_strategies

    # Validate strategy name
    if strategy_name and strategy_name not in all_strategies:
        print(f"ERROR: Unknown strategy '{strategy_name}'")
        print(f"Available strategies: {', '.join(all_strategies)}")
        conn.close()
        return

    # Process each data source
    grand_total = 0
    for src in sources_to_run:
        print(f"\n{'=' * 40}")
        print(f"Processing source: {src}")
        print(f"{'=' * 40}")

        # Check backtest data availability for this source
        info = get_backtest_info(conn, src)
        if not info:
            print(f"WARNING: No data for source '{src}'. Skipping.")
            continue

        print(f"Data: {info['count']:,} candles")
        print(f"Range: {info['start_date']} to {info['end_date']} ({info['days']} days)")
        print()

        # Clear existing signals if force
        if force:
            print("Force mode: clearing existing signals...")
            clear_signals(conn, strategy_name, src)
            print()

        # Calculate signals for each strategy
        source_signals = 0
        for strat_name in strategies_to_run:
            print(f"[{strat_name}] Calculating signals...")
            count, _ = calculate_signals_incremental(conn, strat_name, SYMBOL, src, 'backtest_candles')
            source_signals += count
            print(f"  Generated {count} new signal(s)")

        print(f"\nSource '{src}' total: {source_signals} signals")
        grand_total += source_signals

    # Print summary
    print(f"\n{'=' * 60}")
    print("Summary")
    print(f"{'=' * 60}\n")

    cursor = conn.execute("""
        SELECT strategy_name, type, COUNT(*) as count
        FROM signals
        WHERE symbol = ?
        GROUP BY strategy_name, type
        ORDER BY strategy_name, type
    """, (SYMBOL,))

    current_strategy = None
    for row in cursor:
        if row['strategy_name'] != current_strategy:
            if current_strategy is not None:
                print()
            current_strategy = row['strategy_name']
            print(f"  {current_strategy}:")
        print(f"    - {row['type']}: {row['count']} signals")

    # Get first and last signals
    print()
    for strat_name in strategies_to_run:
        signals = get_signals_from_db(conn, strat_name, SYMBOL, limit=1)
        if signals:
            first = signals[0]
            first_date = datetime.fromtimestamp(first['time'], tz=PARIS_TZ)
            print(f"  {strat_name} first signal: {first_date.strftime('%Y-%m-%d %H:%M')} ({first['type']})")

        # Get last signal
        cursor = conn.execute("""
            SELECT signal_timestamp, type FROM signals
            WHERE strategy_name = ? AND symbol = ?
            ORDER BY signal_timestamp DESC LIMIT 1
        """, (strat_name, SYMBOL))
        row = cursor.fetchone()
        if row:
            last_date = datetime.fromtimestamp(row['signal_timestamp'], tz=PARIS_TZ)
            print(f"  {strat_name} last signal: {last_date.strftime('%Y-%m-%d %H:%M')} ({row['type']})")

    conn.close()
    print(f"\nDone! Grand total: {grand_total} signals")


def main():
    parser = argparse.ArgumentParser(description='Bootstrap trading signals calculation')
    parser.add_argument('--strategy', '-s', type=str, help='Strategy name (e.g., bollinger-nosl)')
    parser.add_argument('--force', '-f', action='store_true', help='Clear existing signals and recalculate')
    parser.add_argument('--source', type=str, help='Data source (yfinance or firstrate)')

    args = parser.parse_args()

    bootstrap_signals(strategy_name=args.strategy, force=args.force, source=args.source)


if __name__ == "__main__":
    main()
