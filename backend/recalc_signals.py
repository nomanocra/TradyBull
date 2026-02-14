"""
Recalculate signals for strategies without indicators.
Uses multiprocessing for parallel calculation.
"""

import sqlite3
import pandas as pd
from multiprocessing import Pool, cpu_count
from itertools import product
import time
import sys

sys.path.insert(0, '/Users/davidduprat/Documents/Dev_local/tradybull/backend')
from strategies.dynamic import DynamicStrategy, DynamicStrategyConfig, generate_strategy_name

DB_PATH = '/Users/davidduprat/Documents/Dev_local/tradybull/backend/tradybull.db'

# Options
STOP_LOSSES = [0.8, 1.0, 2.5, 5.0]
MA_TRENDS = [None, 50, 100, 150, 200]
VALUE_ABOVE_MAS = [None, 50, 100, 150, 200]
INTRADAYS = ['none', 'daily', 'multi-daily']


def load_candles():
    """Load candles from DB"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('''
        SELECT timestamp as time, open, high, low, close, volume
        FROM backtest_candles
        WHERE source = 'yfinance'
        ORDER BY timestamp
    ''', conn)
    conn.close()
    return df.to_dict('records')


def generate_configs():
    """Generate all valid strategy configs"""
    configs = []

    for sl, ma_t, val_ma, intrad in product(STOP_LOSSES, MA_TRENDS, VALUE_ABOVE_MAS, INTRADAYS):
        # Must have at least one MA condition (trend or value_above)
        if ma_t is None and val_ma is None:
            continue

        config = {
            'stop_loss': sl,
            'intraday': intrad,
        }

        if ma_t is not None:
            config['ma_trend'] = ma_t

        if val_ma is not None:
            config['value_above_ma'] = val_ma

        configs.append(config)

    return configs


def calculate_strategy(args):
    """Calculate signals for a single strategy"""
    config, candles = args

    name = generate_strategy_name(config)

    config_dict = {
        'name': name,
        'display_name': name,
        **config
    }

    try:
        strategy_config = DynamicStrategyConfig.from_dict(config_dict)
        strategy = DynamicStrategy(strategy_config)
        signals, _ = strategy.calculate_signals(candles)

        return {
            'name': name,
            'signals': signals,
            'error': None
        }
    except Exception as e:
        return {
            'name': name,
            'signals': [],
            'error': str(e)
        }


def save_signals(results):
    """Save all signals to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_signals = 0

    for result in results:
        if result['error']:
            print(f"  Error for {result['name']}: {result['error']}")
            continue

        for sig in result['signals']:
            cursor.execute('''
                INSERT OR IGNORE INTO signals
                (strategy_name, symbol, signal_timestamp, trigger_timestamp, type, price, label, metadata, data_source)
                VALUES (?, 'NQ=F', ?, ?, ?, ?, ?, ?, 'yfinance')
            ''', (
                result['name'],
                sig.signal_timestamp,
                sig.trigger_timestamp,
                sig.type,
                sig.price,
                sig.label,
                str(sig.metadata) if sig.metadata else None
            ))

        total_signals += len(result['signals'])

    conn.commit()
    conn.close()

    return total_signals


def main():
    print("=" * 60)
    print("RECALCULATING SIGNALS (without indicators)")
    print("=" * 60)

    # Load candles once
    print("\nLoading candles...")
    candles = load_candles()
    print(f"Loaded {len(candles)} candles")

    # Generate configs
    configs = generate_configs()
    print(f"\nStrategies to calculate: {len(configs)}")

    # Prepare args for multiprocessing
    args = [(config, candles) for config in configs]

    # Calculate with multiprocessing
    num_workers = cpu_count()
    print(f"Using {num_workers} CPU cores")

    start_time = time.time()

    with Pool(num_workers) as pool:
        results = pool.map(calculate_strategy, args)

    calc_time = time.time() - start_time
    print(f"\nCalculation done in {calc_time:.1f}s ({calc_time/len(configs)*1000:.0f}ms per strategy)")

    # Save to DB
    print("\nSaving to database...")
    total_signals = save_signals(results)

    total_time = time.time() - start_time
    print(f"\nTotal: {total_signals} signals saved in {total_time:.1f}s")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successful = sum(1 for r in results if not r['error'])
    print(f"Successful: {successful}/{len(configs)}")


if __name__ == '__main__':
    main()
