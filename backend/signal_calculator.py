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


def save_signals(conn: sqlite3.Connection, strategy_name: str, symbol: str, signals: List[Signal]) -> int:
    """Save signals to database. Returns number of new signals inserted."""
    inserted = 0
    for signal in signals:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO signals
            (strategy_name, symbol, signal_timestamp, trigger_timestamp, type, price, label, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_name,
            symbol,
            signal.signal_timestamp,
            signal.trigger_timestamp,
            signal.type,
            signal.price,
            signal.label,
            json.dumps(signal.metadata) if signal.metadata else None
        ))
        if cursor.rowcount > 0:
            inserted += 1
    conn.commit()
    return inserted


def save_signals_and_return_new(conn: sqlite3.Connection, strategy_name: str, symbol: str, signals: List[Signal]) -> tuple[int, List[Signal]]:
    """Save signals to database. Returns tuple of (count inserted, list of actually inserted signals)."""
    inserted_signals = []
    for signal in signals:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO signals
            (strategy_name, symbol, signal_timestamp, trigger_timestamp, type, price, label, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_name,
            symbol,
            signal.signal_timestamp,
            signal.trigger_timestamp,
            signal.type,
            signal.price,
            signal.label,
            json.dumps(signal.metadata) if signal.metadata else None
        ))
        if cursor.rowcount > 0:
            inserted_signals.append(signal)
    conn.commit()
    return len(inserted_signals), inserted_signals


def get_signals_from_db(conn: sqlite3.Connection, strategy_name: str, symbol: str,
                        start_ts: Optional[int] = None, end_ts: Optional[int] = None,
                        limit: int = 10000) -> List[Dict]:
    """Get signals from database for a strategy"""
    if start_ts and end_ts:
        query = """
            SELECT signal_timestamp, trigger_timestamp, type, price, label, metadata
            FROM signals
            WHERE strategy_name = ? AND symbol = ? AND signal_timestamp >= ? AND signal_timestamp <= ?
            ORDER BY signal_timestamp ASC
            LIMIT ?
        """
        rows = conn.execute(query, (strategy_name, symbol, start_ts, end_ts, limit)).fetchall()
    elif start_ts:
        query = """
            SELECT signal_timestamp, trigger_timestamp, type, price, label, metadata
            FROM signals
            WHERE strategy_name = ? AND symbol = ? AND signal_timestamp >= ?
            ORDER BY signal_timestamp ASC
            LIMIT ?
        """
        rows = conn.execute(query, (strategy_name, symbol, start_ts, limit)).fetchall()
    else:
        query = """
            SELECT signal_timestamp, trigger_timestamp, type, price, label, metadata
            FROM signals
            WHERE strategy_name = ? AND symbol = ?
            ORDER BY signal_timestamp ASC
            LIMIT ?
        """
        rows = conn.execute(query, (strategy_name, symbol, limit)).fetchall()

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
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """
            rows = conn.execute(query, (symbol, lookback_start)).fetchall()
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
                WHERE symbol = ?
                ORDER BY timestamp ASC
            """
            rows = conn.execute(query, (symbol,)).fetchall()
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
        new_count, new_signals = save_signals_and_return_new(conn, strategy_name, symbol, signals)

    # Update processing state
    if candles:
        last_candle_time = candles[-1]['time']
        save_processing_state(conn, strategy_name, symbol, data_source, last_candle_time, final_state)

    return new_count, new_signals


def calculate_all_strategies(conn: sqlite3.Connection, symbol: str, data_source: str, candles_table: str) -> Dict[str, tuple[int, List[Signal]]]:
    """
    Calculate signals for all registered strategies.

    Returns:
        Dict mapping strategy name to tuple of (count, new signals list)
    """
    results = {}
    for strategy_name in STRATEGIES:
        count, signals = calculate_signals_incremental(conn, strategy_name, symbol, data_source, candles_table)
        results[strategy_name] = (count, signals)
    return results


def recalculate_strategy(conn: sqlite3.Connection, strategy_name: str, symbol: str, data_source: str, candles_table: str) -> int:
    """
    Force full recalculation of a strategy by clearing its state first.
    Used when strategy code changes or for manual recalculation.
    Does NOT return signals to prevent notification spam.

    Returns:
        Number of signals calculated
    """
    # Clear existing state and signals for this strategy
    conn.execute("DELETE FROM signal_processing_state WHERE strategy_name = ? AND symbol = ? AND data_source = ?",
                 (strategy_name, symbol, data_source))
    conn.execute("DELETE FROM signals WHERE strategy_name = ? AND symbol = ?", (strategy_name, symbol))
    conn.commit()

    # Recalculate (will do full calculation since state was cleared)
    count, _ = calculate_signals_incremental(conn, strategy_name, symbol, data_source, candles_table)
    return count


def recalculate_all_strategies(conn: sqlite3.Connection, symbol: str, data_source: str, candles_table: str) -> Dict[str, int]:
    """
    Force full recalculation of ALL strategies.
    Used on startup or after strategy code changes.
    Does NOT return signals to prevent notification spam.

    Returns:
        Dict mapping strategy name to signal count
    """
    results = {}
    for strategy_name in STRATEGIES:
        count = recalculate_strategy(conn, strategy_name, symbol, data_source, candles_table)
        results[strategy_name] = count
    return results
