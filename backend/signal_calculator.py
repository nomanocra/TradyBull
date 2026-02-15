"""
Signal Calculator - Orchestrator for trading signal calculation

This module handles incremental signal calculation for all strategies,
storing results in the database and managing processing state.
"""

import sqlite3
import json
from typing import List, Dict, Optional, Type
from strategies import STRATEGIES, BaseStrategy, Signal


def get_strategy(name: str, conn: sqlite3.Connection = None) -> BaseStrategy:
    """Get a strategy instance by name (from registry or dynamic strategies)"""
    # First try the hardcoded registry
    if name in STRATEGIES:
        return STRATEGIES[name]()

    # Then try dynamic strategies from DB
    if conn:
        from strategies.dynamic import create_dynamic_strategy
        cursor = conn.execute(
            "SELECT name, display_name, config FROM dynamic_strategies WHERE name = ?",
            (name,)
        )
        row = cursor.fetchone()
        if row:
            import json
            config = json.loads(row[2])
            config['name'] = row[0]
            config['display_name'] = row[1]
            return create_dynamic_strategy(config)

    raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGIES.keys())}")


def get_processing_state(conn: sqlite3.Connection, strategy_name: str, symbol: str, data_source: str) -> Optional[Dict]:
    """Get the last processing state for a strategy"""
    cursor = conn.execute("""
        SELECT last_processed_timestamp, last_signal_state
        FROM signal_processing_state
        WHERE strategy_name = ? AND symbol = ? AND data_source = ?
    """, (strategy_name, symbol, data_source))
    row = cursor.fetchone()
    if row:
        return {
            'last_processed_timestamp': row[0],
            'state': json.loads(row[1]) if row[1] else {}
        }
    return None


def save_processing_state(conn: sqlite3.Connection, strategy_name: str, symbol: str,
                          data_source: str, last_timestamp: int, state: Dict):
    """Save the processing state for incremental updates"""
    conn.execute("""
        INSERT OR REPLACE INTO signal_processing_state
        (strategy_name, symbol, data_source, last_processed_timestamp, last_signal_state, updated_at)
        VALUES (?, ?, ?, ?, ?, strftime('%s', 'now'))
    """, (strategy_name, symbol, data_source, last_timestamp, json.dumps(state)))
    conn.commit()


def save_signals(conn: sqlite3.Connection, strategy_name: str, symbol: str, signals: List[Signal], data_source: str = 'yfinance') -> int:
    """Save signals to database. Returns number of new signals inserted."""
    inserted = 0
    for signal in signals:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO signals
            (strategy_name, symbol, signal_timestamp, trigger_timestamp, type, price, label, metadata, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_name,
            symbol,
            signal.signal_timestamp,
            signal.trigger_timestamp,
            signal.type,
            signal.price,
            signal.label,
            json.dumps(signal.metadata) if signal.metadata else None,
            data_source
        ))
        if cursor.rowcount > 0:
            inserted += 1
    conn.commit()
    return inserted


def save_signals_and_return_new(conn: sqlite3.Connection, strategy_name: str, symbol: str, signals: List[Signal], data_source: str = 'yfinance') -> tuple[int, List[Signal]]:
    """Save signals to database. Returns tuple of (count inserted, list of actually inserted signals)."""
    inserted_signals = []
    for signal in signals:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO signals
            (strategy_name, symbol, signal_timestamp, trigger_timestamp, type, price, label, metadata, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_name,
            symbol,
            signal.signal_timestamp,
            signal.trigger_timestamp,
            signal.type,
            signal.price,
            signal.label,
            json.dumps(signal.metadata) if signal.metadata else None,
            data_source
        ))
        if cursor.rowcount > 0:
            inserted_signals.append(signal)
    conn.commit()
    return len(inserted_signals), inserted_signals


def get_signals_from_db(conn: sqlite3.Connection, strategy_name: str, symbol: str,
                        start_ts: Optional[int] = None, end_ts: Optional[int] = None,
                        limit: int = 10000, data_source: Optional[str] = None) -> List[Dict]:
    """Get signals from database for a strategy, optionally filtered by data_source"""
    # Build WHERE clause
    conditions = ["strategy_name = ?", "symbol = ?"]
    params = [strategy_name, symbol]

    if data_source:
        conditions.append("data_source = ?")
        params.append(data_source)

    if start_ts:
        conditions.append("signal_timestamp >= ?")
        params.append(start_ts)

    if end_ts:
        conditions.append("signal_timestamp <= ?")
        params.append(end_ts)

    where_clause = " AND ".join(conditions)
    params.append(limit)

    query = f"""
        SELECT signal_timestamp, trigger_timestamp, type, price, label, metadata
        FROM signals
        WHERE {where_clause}
        ORDER BY signal_timestamp ASC
        LIMIT ?
    """
    rows = conn.execute(query, params).fetchall()

    return [
        {
            "time": row[0],
            "trigger_time": row[1],
            "type": row[2],
            "price": row[3],
            "label": row[4],
            "metadata": json.loads(row[5]) if row[5] else None
        }
        for row in rows
    ]


def calculate_signals_incremental(
    conn: sqlite3.Connection,
    strategy_name: str,
    symbol: str,
    data_source: str,  # 'backtest' or 'realtime'
    candles_table: str,  # 'backtest_candles' or 'candles'
    strategy_instance: Optional[BaseStrategy] = None  # For dynamic strategies
) -> tuple[int, List[Signal]]:
    """
    Calculate signals incrementally for new candles only.

    Args:
        conn: Database connection
        strategy_name: Name of the strategy to run
        symbol: Symbol to process (e.g., 'NQ=F')
        data_source: 'backtest' or 'realtime'
        candles_table: Table to read candles from
        strategy_instance: Optional pre-created strategy instance (for dynamic strategies)

    Returns:
        Tuple of (number of new signals, list of new Signal objects)
    """
    # Use provided instance or get from registry/DB
    if strategy_instance:
        strategy = strategy_instance
    else:
        strategy = get_strategy(strategy_name, conn)

    # Get last processing state
    proc_state = get_processing_state(conn, strategy_name, symbol, data_source)

    if proc_state:
        last_timestamp = proc_state['last_processed_timestamp']
        initial_state = proc_state['state']

        # Need to fetch lookback candles BEFORE last_timestamp for context
        # Plus all new candles AFTER last_timestamp
        # Use 2x lookback in hours to ensure we have enough context
        lookback_start = last_timestamp - (strategy.required_lookback * 3600 * 2)

        if candles_table == 'backtest_candles':
            query = f"""
                SELECT timestamp, open, high, low, close, volume
                FROM {candles_table}
                WHERE symbol = ? AND source = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """
            rows = conn.execute(query, (symbol, data_source, lookback_start)).fetchall()
        else:
            # For real-time candles table, filter by interval
            query = f"""
                SELECT timestamp, open, high, low, close, volume
                FROM {candles_table}
                WHERE interval = '1h' AND timestamp >= ?
                ORDER BY timestamp ASC
            """
            rows = conn.execute(query, (lookback_start,)).fetchall()
    else:
        # Full calculation - no previous state
        initial_state = None

        if candles_table == 'backtest_candles':
            query = f"""
                SELECT timestamp, open, high, low, close, volume
                FROM {candles_table}
                WHERE symbol = ? AND source = ?
                ORDER BY timestamp ASC
            """
            rows = conn.execute(query, (symbol, data_source)).fetchall()
        else:
            query = f"""
                SELECT timestamp, open, high, low, close, volume
                FROM {candles_table}
                WHERE interval = '1h'
                ORDER BY timestamp ASC
            """
            rows = conn.execute(query).fetchall()

    if not rows:
        return 0, []

    candles = [
        {
            'time': row[0],
            'open': row[1],
            'high': row[2],
            'low': row[3],
            'close': row[4],
            'volume': row[5]
        }
        for row in rows
    ]

    # Calculate signals
    signals, final_state = strategy.calculate_signals(candles, initial_state)

    # Filter out signals we've already stored (before last_processed_timestamp)
    if proc_state:
        signals = [s for s in signals if s.signal_timestamp > proc_state['last_processed_timestamp']]

    # Save new signals and track which ones were actually inserted
    new_count = 0
    new_signals = []
    if signals:
        new_count, new_signals = save_signals_and_return_new(conn, strategy_name, symbol, signals, data_source)

    # Update processing state
    if candles:
        last_candle_time = candles[-1]['time']
        save_processing_state(conn, strategy_name, symbol, data_source, last_candle_time, final_state)

    return new_count, new_signals


def calculate_all_strategies(conn: sqlite3.Connection, symbol: str, data_source: str, candles_table: str) -> Dict[str, tuple[int, List[Signal]]]:
    """
    Calculate signals for all registered strategies (hardcoded + dynamic).

    Returns:
        Dict mapping strategy name to tuple of (count, new signals list)
    """
    results = {}

    # Hardcoded strategies
    for strategy_name in STRATEGIES:
        count, signals = calculate_signals_incremental(conn, strategy_name, symbol, data_source, candles_table)
        results[strategy_name] = (count, signals)

    # Dynamic strategies from database
    dynamic_rows = conn.execute("SELECT name FROM dynamic_strategies").fetchall()
    for row in dynamic_rows:
        strategy_name = row['name'] if isinstance(row, dict) else row[0]
        count, signals = calculate_signals_incremental(conn, strategy_name, symbol, data_source, candles_table)
        results[strategy_name] = (count, signals)

    return results


def recalculate_strategy(conn: sqlite3.Connection, strategy_name: str, symbol: str, data_source: str = 'yfinance') -> int:
    """
    Force full recalculation of a strategy by clearing its state first.
    Used for manual recalculation in backtesting to catch missed signals.
    Does NOT return signals to prevent notification spam.

    Args:
        data_source: 'yfinance' or 'firstrate' - determines which candles to use

    Returns:
        Number of signals calculated
    """
    # Clear existing state and signals for this strategy AND data_source
    conn.execute("DELETE FROM signal_processing_state WHERE strategy_name = ? AND symbol = ? AND data_source = ?",
                 (strategy_name, symbol, data_source))
    conn.execute("DELETE FROM signals WHERE strategy_name = ? AND symbol = ? AND data_source = ?",
                 (strategy_name, symbol, data_source))
    conn.commit()

    # Get strategy instance
    strategy = get_strategy(strategy_name, conn)

    # Fetch candles from backtest_candles filtered by source
    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM backtest_candles
        WHERE symbol = ? AND source = ?
        ORDER BY timestamp ASC
    """
    rows = conn.execute(query, (symbol, data_source)).fetchall()

    if not rows:
        return 0

    candles = [
        {
            'time': row[0],
            'open': row[1],
            'high': row[2],
            'low': row[3],
            'close': row[4],
            'volume': row[5]
        }
        for row in rows
    ]

    # Calculate signals
    signals, final_state = strategy.calculate_signals(candles, None)

    # Save signals with data_source
    new_count = save_signals(conn, strategy_name, symbol, signals, data_source)

    # Save processing state
    if candles:
        save_processing_state(conn, strategy_name, symbol, data_source, candles[-1]['time'], final_state)

    return new_count


def recalculate_all_strategies(conn: sqlite3.Connection, symbol: str, data_source: str = 'yfinance', include_archived: bool = False) -> Dict[str, int]:
    """
    Force full recalculation of strategies (hardcoded + dynamic).
    Used on startup or after strategy code changes.
    Does NOT return signals to prevent notification spam.

    Args:
        conn: Database connection
        symbol: Trading symbol
        data_source: 'yfinance' or 'firstrate' - determines which candles to use
        include_archived: If False, skip archived strategies (default: False)

    Returns:
        Dict mapping strategy name to signal count
    """
    results = {}

    # Get archived strategies set
    archived_set = set()
    if not include_archived:
        archived_rows = conn.execute("SELECT strategy_name FROM archived_strategies").fetchall()
        archived_set = {row[0] for row in archived_rows}

    # Hardcoded strategies
    for strategy_name in STRATEGIES:
        if strategy_name in archived_set:
            continue
        count = recalculate_strategy(conn, strategy_name, symbol, data_source)
        results[strategy_name] = count

    # Dynamic strategies from database
    dynamic_rows = conn.execute("SELECT name FROM dynamic_strategies").fetchall()
    for row in dynamic_rows:
        strategy_name = row[0]
        if strategy_name in archived_set:
            continue
        count = recalculate_strategy(conn, strategy_name, symbol, data_source)
        results[strategy_name] = count

    return results


# ==================== NEW: Optimized signal check on latest candle ====================

def get_strategy_state(conn: sqlite3.Connection, strategy_name: str, symbol: str, source: str = 'yfinance') -> Optional[Dict]:
    """Get the current state for a strategy, per data source."""
    data_source_key = 'unified' if source == 'yfinance' else f'unified_{source}'
    cursor = conn.execute("""
        SELECT last_processed_timestamp, last_signal_state
        FROM signal_processing_state
        WHERE strategy_name = ? AND symbol = ? AND data_source = ?
    """, (strategy_name, symbol, data_source_key))
    row = cursor.fetchone()
    if row:
        return {
            'last_processed_timestamp': row[0],
            'state': json.loads(row[1]) if row[1] else {}
        }
    return None


def save_strategy_state(conn: sqlite3.Connection, strategy_name: str, symbol: str,
                        last_timestamp: int, state: Dict, source: str = 'yfinance'):
    """Save the strategy state, per data source."""
    data_source_key = 'unified' if source == 'yfinance' else f'unified_{source}'
    conn.execute("""
        INSERT OR REPLACE INTO signal_processing_state
        (strategy_name, symbol, data_source, last_processed_timestamp, last_signal_state, updated_at)
        VALUES (?, ?, ?, ?, ?, strftime('%s', 'now'))
    """, (strategy_name, symbol, data_source_key, last_timestamp, json.dumps(state)))
    conn.commit()


def check_signal_on_latest_candle(
    conn: sqlite3.Connection,
    strategy_name: str,
    symbol: str,
    source: str = 'yfinance'
) -> List[Signal]:
    """
    Check for signals on new candles since last processed.

    Saves ALL new signals to the database (for history/backtesting).
    Returns ALL inserted signals so the caller can decide which one to notify
    based on the last notification type sent.

    Uses backtest_candles as the single source of truth.
    The `source` parameter determines which candle data and state to use.

    Returns:
        List of all newly inserted signals (can be empty)
    """
    # Get strategy instance
    strategy = get_strategy(strategy_name, conn)

    # Get current state (per source)
    proc_state = get_strategy_state(conn, strategy_name, symbol, source=source)

    if proc_state:
        last_timestamp = proc_state['last_processed_timestamp']
        current_state = proc_state['state']
    else:
        last_timestamp = 0
        current_state = None

    # Fetch lookback candles + new candles from backtest_candles
    lookback_start = last_timestamp - (strategy.required_lookback * 3600 * 2) if last_timestamp > 0 else 0

    query = """
        SELECT timestamp, open, high, low, close, volume
        FROM backtest_candles
        WHERE symbol = ? AND source = ? AND timestamp >= ?
        ORDER BY timestamp ASC
    """
    rows = conn.execute(query, (symbol, source, lookback_start)).fetchall()

    if not rows:
        return []

    candles = [
        {
            'time': row[0],
            'open': row[1],
            'high': row[2],
            'low': row[3],
            'close': row[4],
            'volume': row[5]
        }
        for row in rows
    ]

    latest_candle = candles[-1]

    # Skip if we've already processed this candle
    if latest_candle['time'] <= last_timestamp:
        return []

    # Calculate signals using the strategy
    signals, final_state = strategy.calculate_signals(candles, current_state)

    # Filter to only get signals for candles after last processed
    new_signals = [s for s in signals if s.signal_timestamp > last_timestamp]

    # Save updated state (per source)
    save_strategy_state(conn, strategy_name, symbol, latest_candle['time'], final_state, source=source)

    # Save all new signals to database and track which ones were actually inserted
    inserted_signals = []
    for signal in new_signals:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO signals
            (strategy_name, symbol, signal_timestamp, trigger_timestamp, type, price, label, metadata, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_name,
            symbol,
            signal.signal_timestamp,
            signal.trigger_timestamp,
            signal.type,
            signal.price,
            signal.label,
            json.dumps(signal.metadata) if signal.metadata else None,
            source
        ))
        if cursor.rowcount > 0:
            inserted_signals.append(signal)
    conn.commit()

    return inserted_signals


def check_all_strategies_latest_candle(conn: sqlite3.Connection, symbol: str, source: str = 'yfinance') -> Dict[str, List[Signal]]:
    """
    Check all strategies (hardcoded + dynamic) for signals on new candles.

    Returns:
        Dict mapping strategy name to list of new signals (can be empty)
    """
    results = {}

    # Hardcoded strategies
    for strategy_name in STRATEGIES:
        signals = check_signal_on_latest_candle(conn, strategy_name, symbol, source=source)
        results[strategy_name] = signals

    # Dynamic strategies from database
    dynamic_rows = conn.execute("SELECT name FROM dynamic_strategies").fetchall()
    for row in dynamic_rows:
        strategy_name = row[0]
        signals = check_signal_on_latest_candle(conn, strategy_name, symbol, source=source)
        results[strategy_name] = signals

    return results
