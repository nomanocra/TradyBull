"""
Generate and evaluate multiple dynamic strategy combinations.
Finds the best performing strategies based on backtesting KPIs.
"""
import requests
import time
import warnings
from itertools import product
from typing import List, Dict, Any, Optional

# Suppress SSL warnings
warnings.filterwarnings('ignore')

API_BASE = "http://localhost:8000"

# Define parameter options - focused set for meaningful strategies
INDICATORS = [
    None,  # No indicator
    {"type": "bollinger", "mode": "buy"},  # Bollinger only for buy
    {"type": "rsi-late", "mode": "buy"},   # RSI exit oversold for buy
]

STOP_LOSSES = [None, 0.8, 1.0]  # Common values

MA_TRENDS = [None, 100, 150, 200]

VALUE_ABOVE_MAS = [None, 100, 150, 200]

INTRADAYS = ["multi-daily"]  # Focus on multi-daily for more trades

# Only generate sensible combinations
def is_valid_combination(config: Dict[str, Any]) -> bool:
    """Check if a strategy combination makes sense."""

    # Must have at least one entry/exit condition (not just SL)
    has_entry_exit = (
        config.get("indicator") is not None or
        config.get("ma_trend") is not None or
        config.get("value_above_ma") is not None or
        config.get("intraday") not in (None, "none")
    )
    if not has_entry_exit:
        return False

    # Don't combine ma_trend and value_above_ma with same period
    ma_trend = config.get("ma_trend")
    value_above = config.get("value_above_ma")
    if ma_trend and value_above and ma_trend == value_above:
        return False

    # If no indicator, must have intraday (otherwise no clear entry)
    if config.get("indicator") is None and config.get("intraday") == "none":
        # Need at least ma_trend or value_above_ma for entry logic
        if not ma_trend and not value_above:
            return False

    # Bollinger works best with intraday
    if config.get("indicator") and config["indicator"].get("type") == "bollinger":
        if config.get("intraday") == "none":
            return False  # Bollinger needs intraday exit

    return True


def generate_combinations() -> List[Dict[str, Any]]:
    """Generate all valid strategy combinations."""
    combinations = []

    for indicator, sl, ma_trend, value_above, intraday in product(
        INDICATORS, STOP_LOSSES, MA_TRENDS, VALUE_ABOVE_MAS, INTRADAYS
    ):
        config = {}

        if indicator:
            config["indicator"] = indicator
        if sl:
            config["stop_loss"] = sl
        if ma_trend:
            config["ma_trend"] = ma_trend
        if value_above:
            config["value_above_ma"] = value_above
        if intraday != "none":
            config["intraday"] = intraday

        if is_valid_combination(config):
            combinations.append(config)

    return combinations


def create_strategy(config: Dict[str, Any]) -> Optional[str]:
    """Create a dynamic strategy via API. Returns strategy name or None if failed."""
    try:
        response = requests.post(
            f"{API_BASE}/api/strategies/dynamic",
            json=config,
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("strategy", {}).get("name")
        elif response.status_code == 409:
            # Already exists - extract name from error message
            data = response.json()
            detail = data.get("detail", "")
            # Format: "Strategy 'xxx' already exists"
            if "'" in detail:
                name = detail.split("'")[1]
                return name
            return "exists"
        else:
            print(f"  Error {response.status_code}: {response.text[:100]}")
            return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def get_all_kpis() -> List[Dict[str, Any]]:
    """Fetch KPIs for all strategies."""
    try:
        response = requests.get(f"{API_BASE}/api/kpis/all", timeout=120)
        if response.status_code == 200:
            data = response.json()
            # Response format: {"symbol": "...", "strategies": [...]}
            return data.get("strategies", [])
        return []
    except Exception as e:
        print(f"Error fetching KPIs: {e}")
        return []


def rank_strategies(kpis: List[Dict[str, Any]], min_trades: int = 30) -> List[Dict[str, Any]]:
    """Rank strategies by score, filtered by minimum trades."""
    # Filter by minimum trades
    filtered = [k for k in kpis if k.get("kpis", {}).get("num_trades", 0) >= min_trades]

    # Sort by score descending
    ranked = sorted(filtered, key=lambda x: x.get("kpis", {}).get("score", 0), reverse=True)

    return ranked


def format_config_name(config: Dict[str, Any]) -> str:
    """Generate a readable name for a config."""
    parts = []
    if config.get("indicator"):
        parts.append(config["indicator"]["type"])
    if config.get("stop_loss"):
        parts.append(f"SL{config['stop_loss']}%")
    if config.get("ma_trend"):
        parts.append(f"Trend{config['ma_trend']}")
    if config.get("value_above_ma"):
        parts.append(f">MA{config['value_above_ma']}")
    if config.get("intraday"):
        parts.append("Intraday" if config["intraday"] == "multi-daily" else "IntraD-Single")
    return " ".join(parts) if parts else "Default"


def main():
    print("=" * 60)
    print("DYNAMIC STRATEGY GENERATOR & EVALUATOR")
    print("=" * 60)

    # Generate combinations
    print("\n1. Generating strategy combinations...")
    combinations = generate_combinations()
    print(f"   Generated {len(combinations)} valid combinations")

    # Create strategies
    print("\n2. Creating strategies...")
    created = 0
    skipped = 0
    failed = 0

    for i, config in enumerate(combinations):
        name = create_strategy(config)
        if name:
            created += 1
            if (i + 1) % 10 == 0:
                print(f"   Progress: {i + 1}/{len(combinations)}")
        else:
            failed += 1
        time.sleep(0.1)  # Small delay to not overwhelm API

    print(f"   Created: {created}, Failed: {failed}")

    # Wait for signal calculations
    print("\n3. Waiting for signal calculations...")
    time.sleep(2)

    # Fetch and rank KPIs
    print("\n4. Fetching KPIs...")
    kpis = get_all_kpis()
    print(f"   Retrieved KPIs for {len(kpis)} strategies")

    # Rank and display top strategies
    print("\n5. Ranking strategies (min 30 trades)...")
    ranked = rank_strategies(kpis, min_trades=30)

    print("\n" + "=" * 100)
    print("TOP 20 STRATEGIES BY SCORE")
    print("=" * 100)
    print(f"{'Rank':<5} {'Strategy':<45} {'Score':>8} {'Return':>10} {'WinRate':>8} {'Trades':>7} {'MaxDD':>8}")
    print("-" * 100)

    for i, strategy in enumerate(ranked[:20]):
        kpi = strategy.get("kpis", {})
        print(
            f"{i+1:<5} "
            f"{strategy.get('display_name', 'Unknown')[:44]:<45} "
            f"{kpi.get('score', 0):>7.1f} "
            f"{kpi.get('total_return_pct', 0):>+9.1f}% "
            f"{kpi.get('win_rate_pct', 0):>7.1f}% "
            f"{kpi.get('num_trades', 0):>7} "
            f"{kpi.get('max_drawdown_pct', 0):>7.1f}%"
        )

    # Show worst performers too
    print("\n" + "=" * 100)
    print("BOTTOM 10 STRATEGIES (for reference)")
    print("=" * 100)
    print(f"{'Rank':<5} {'Strategy':<45} {'Score':>8} {'Return':>10} {'WinRate':>8} {'Trades':>7} {'MaxDD':>8}")
    print("-" * 100)

    for i, strategy in enumerate(ranked[-10:]):
        kpi = strategy.get("kpis", {})
        print(
            f"{len(ranked)-9+i:<5} "
            f"{strategy.get('display_name', 'Unknown')[:44]:<45} "
            f"{kpi.get('score', 0):>7.1f} "
            f"{kpi.get('total_return_pct', 0):>+9.1f}% "
            f"{kpi.get('win_rate_pct', 0):>7.1f}% "
            f"{kpi.get('num_trades', 0):>7} "
            f"{kpi.get('max_drawdown_pct', 0):>7.1f}%"
        )

    print("\n" + "=" * 60)
    print(f"Total strategies evaluated: {len(ranked)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
