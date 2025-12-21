"""
KPI Calculator for trading strategies.
Calculates key performance indicators from trading signals.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class StrategyKPIs:
    """Key Performance Indicators for a trading strategy"""
    total_return_pct: float          # Sum of all trade returns (%)
    avg_yearly_return_pct: float     # Annualized return (%)
    win_rate_pct: float              # Percentage of winning trades
    profit_factor: float             # Gross profit / Gross loss
    max_drawdown_pct: float          # Maximum peak-to-trough decline (%)
    num_trades: int                  # Number of completed trades
    avg_return_per_trade_pct: float  # Average return per trade (%)
    avg_trade_duration_hours: float  # Average trade duration in hours

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_kpis(signals: List[Dict[str, Any]]) -> StrategyKPIs:
    """
    Calculate KPIs from a list of signals.

    Signals should have:
    - time: Unix timestamp
    - type: 'buy' or 'sell'
    - price: Entry/exit price
    - metadata: Optional dict with buy_price and buy_time for sell signals
    """
    if not signals:
        return StrategyKPIs(
            total_return_pct=0.0,
            avg_yearly_return_pct=0.0,
            win_rate_pct=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            num_trades=0,
            avg_return_per_trade_pct=0.0,
            avg_trade_duration_hours=0.0,
        )

    # Pair buy and sell signals to calculate trade returns
    trades: List[Dict[str, Any]] = []

    # Sort signals by time
    sorted_signals = sorted(signals, key=lambda s: s['time'])

    # Match buy/sell pairs
    open_position: Optional[Dict[str, Any]] = None

    for signal in sorted_signals:
        if signal['type'] == 'buy':
            open_position = {
                'buy_time': signal['time'],
                'buy_price': signal['price'],
            }
        elif signal['type'] == 'sell' and open_position:
            # Use metadata if available, otherwise use tracked position
            buy_price = signal.get('metadata', {}).get('buy_price') or open_position['buy_price']
            buy_time = signal.get('metadata', {}).get('buy_time') or open_position['buy_time']

            sell_price = signal['price']
            sell_time = signal['time']

            # Calculate return percentage
            return_pct = ((sell_price - buy_price) / buy_price) * 100
            duration_hours = (sell_time - buy_time) / 3600

            trades.append({
                'buy_price': buy_price,
                'sell_price': sell_price,
                'buy_time': buy_time,
                'sell_time': sell_time,
                'return_pct': return_pct,
                'duration_hours': duration_hours,
            })

            open_position = None

    if not trades:
        return StrategyKPIs(
            total_return_pct=0.0,
            avg_yearly_return_pct=0.0,
            win_rate_pct=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            num_trades=0,
            avg_return_per_trade_pct=0.0,
            avg_trade_duration_hours=0.0,
        )

    # Calculate metrics
    num_trades = len(trades)
    returns = [t['return_pct'] for t in trades]
    durations = [t['duration_hours'] for t in trades]

    # Total return (sum of individual returns)
    total_return_pct = sum(returns)

    # Win rate
    winning_trades = [r for r in returns if r > 0]
    win_rate_pct = (len(winning_trades) / num_trades) * 100 if num_trades > 0 else 0

    # Profit factor (gross profit / gross loss)
    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = abs(sum(r for r in returns if r < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)

    # Average return per trade
    avg_return_per_trade_pct = total_return_pct / num_trades if num_trades > 0 else 0

    # Average trade duration
    avg_trade_duration_hours = sum(durations) / num_trades if num_trades > 0 else 0

    # Max drawdown (calculated on cumulative returns)
    max_drawdown_pct = calculate_max_drawdown(returns)

    # Annualized return
    # Calculate trading period from first buy to last sell
    first_trade_time = trades[0]['buy_time']
    last_trade_time = trades[-1]['sell_time']
    trading_period_years = (last_trade_time - first_trade_time) / (365.25 * 24 * 3600)

    if trading_period_years > 0 and total_return_pct > -100:
        # Annualized return = (1 + total_return)^(1/years) - 1
        total_return_decimal = total_return_pct / 100
        avg_yearly_return_pct = ((1 + total_return_decimal) ** (1 / trading_period_years) - 1) * 100
    else:
        avg_yearly_return_pct = 0.0

    return StrategyKPIs(
        total_return_pct=round(total_return_pct, 2),
        avg_yearly_return_pct=round(avg_yearly_return_pct, 2),
        win_rate_pct=round(win_rate_pct, 1),
        profit_factor=round(profit_factor, 2) if profit_factor != float('inf') else 999.99,
        max_drawdown_pct=round(max_drawdown_pct, 2),
        num_trades=num_trades,
        avg_return_per_trade_pct=round(avg_return_per_trade_pct, 2),
        avg_trade_duration_hours=round(avg_trade_duration_hours, 1),
    )


def calculate_max_drawdown(returns: List[float]) -> float:
    """
    Calculate maximum drawdown from a series of returns.

    Max drawdown = largest peak-to-trough decline in cumulative returns.
    """
    if not returns:
        return 0.0

    # Calculate cumulative returns
    cumulative = []
    total = 0
    for r in returns:
        total += r
        cumulative.append(total)

    # Find max drawdown
    peak = cumulative[0]
    max_dd = 0

    for value in cumulative:
        if value > peak:
            peak = value
        drawdown = peak - value
        if drawdown > max_dd:
            max_dd = drawdown

    return max_dd
