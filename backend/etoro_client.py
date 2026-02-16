"""
eToro API Client for TradyBull.
Handles market data retrieval and trade execution via the eToro public API.
"""

import os
import uuid
import httpx
from datetime import datetime
from typing import Optional
from pathlib import Path

import pytz


# Load .env.local from project root
def _load_env():
    env_path = Path(__file__).parent.parent / '.env.local'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

_load_env()

BASE_URL = "https://public-api.etoro.com/api/v1"
ETORO_PUBLIC_KEY = os.environ.get("ETORO_PUBLIC_KEY", "")
ETORO_USER_KEY_DEMO = os.environ.get("ETORO_USER_KEY_DEMO", "") or os.environ.get("ETORO_USER_KEY", "")
ETORO_USER_KEY_REAL = os.environ.get("ETORO_USER_KEY_REAL", "")

# Instrument ID cache
_instrument_cache: dict[str, int] = {}


def _get_user_key(account_type: str = "demo") -> str:
    """Get the appropriate user key for the account type."""
    if account_type == "real" and ETORO_USER_KEY_REAL:
        return ETORO_USER_KEY_REAL
    return ETORO_USER_KEY_DEMO


def _headers(account_type: str = "demo") -> dict:
    return {
        "x-api-key": ETORO_PUBLIC_KEY,
        "x-user-key": _get_user_key(account_type),
        "x-request-id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def _check_credentials(account_type: str = "demo"):
    user_key = _get_user_key(account_type)
    if not ETORO_PUBLIC_KEY or not user_key:
        raise RuntimeError(f"eToro API keys not configured for {account_type}. Set ETORO_PUBLIC_KEY and ETORO_USER_KEY_{account_type.upper()} in .env.local")


# =============================================================================
# Market Data
# =============================================================================

def search_instrument(symbol: str) -> Optional[dict]:
    """Search for an instrument by ticker symbol. Returns first match or None."""
    _check_credentials()
    resp = httpx.get(
        f"{BASE_URL}/market-data/search",
        params={"internalSymbolFull": symbol},
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    items = data.get("items") or data.get("Items") or []
    if items:
        return items[0]
    return None


def get_instrument_id(symbol: str) -> int:
    """Resolve a ticker symbol to its eToro instrument ID. Results are cached."""
    if symbol in _instrument_cache:
        return _instrument_cache[symbol]

    result = search_instrument(symbol)
    if not result:
        raise ValueError(f"Instrument not found on eToro: {symbol}")

    instrument_id = result.get("instrumentId") or result.get("InstrumentId") or result.get("instrumentID")
    if not instrument_id:
        raise ValueError(f"No instrumentId in search result for {symbol}: {result}")

    _instrument_cache[symbol] = int(instrument_id)
    return int(instrument_id)


def get_historical_candles(
    instrument_id: int,
    interval: str = "OneHour",
    count: int = 500,
    direction: str = "desc",
) -> list[dict]:
    """
    Fetch historical OHLCV candles from eToro.

    Args:
        instrument_id: eToro instrument ID
        interval: OneMinute, FiveMinutes, FifteenMinutes, ThirtyMinutes, OneHour, FourHours, OneDay, OneWeek
        count: Number of candles to fetch
        direction: desc (newest first) or asc (oldest first)
    """
    _check_credentials()
    resp = httpx.get(
        f"{BASE_URL}/market-data/instruments/{instrument_id}/history/candles/{direction}/{interval}/{count}",
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    paris_tz = pytz.timezone("Europe/Paris")
    candles = []

    # eToro response: { "candles": [{ "instrumentId": ..., "candles": [...] }] }
    outer_candles = data.get("candles") or data.get("Candles") or []
    raw_candles = []
    for group in outer_candles:
        if isinstance(group, dict) and ("candles" in group or "Candles" in group):
            raw_candles.extend(group.get("candles") or group.get("Candles") or [])
        else:
            raw_candles.append(group)

    for c in raw_candles:
        raw_time = c.get("fromDate") or c.get("FromDate") or ""
        try:
            if isinstance(raw_time, str) and raw_time:
                raw_time = raw_time.replace("Z", "+00:00")
                dt = datetime.fromisoformat(raw_time)
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)
                dt_paris = dt.astimezone(paris_tz)
                timestamp = int(dt_paris.timestamp())
            else:
                timestamp = int(raw_time) if raw_time else 0
        except (ValueError, TypeError):
            timestamp = 0

        candles.append({
            "time": timestamp,
            "open": round(float(c.get("open") or c.get("Open") or 0), 2),
            "high": round(float(c.get("high") or c.get("High") or 0), 2),
            "low": round(float(c.get("low") or c.get("Low") or 0), 2),
            "close": round(float(c.get("close") or c.get("Close") or 0), 2),
            "volume": int(c.get("volume") or c.get("Volume") or 0),
        })
    return candles


def get_current_rates(instrument_ids: Optional[list[int]] = None) -> list[dict]:
    """
    Get current bid/ask rates for instruments.

    Args:
        instrument_ids: List of instrument IDs. If None, returns all available.
    """
    _check_credentials()
    params = {}
    if instrument_ids:
        params["InstrumentIds"] = ",".join(str(i) for i in instrument_ids)

    resp = httpx.get(
        f"{BASE_URL}/market-data/instruments/rates",
        params=params,
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("Rates") or data.get("rates") or (data if isinstance(data, list) else [])


# =============================================================================
# Trading
# =============================================================================

def open_position_by_cash(
    instrument_id: int,
    amount: float,
    is_buy: bool,
    leverage: int = 1,
    account_type: str = "demo",
    stop_loss_rate: Optional[float] = None,
    take_profit_rate: Optional[float] = None,
) -> dict:
    """
    Open a position by cash amount.

    Args:
        instrument_id: eToro instrument ID
        amount: Investment amount in USD
        is_buy: True for buy, False for sell (short)
        leverage: Leverage multiplier (default 1)
        account_type: 'demo' or 'real'
        stop_loss_rate: Stop loss price level (optional)
        take_profit_rate: Take profit price level (optional)
    """
    _check_credentials(account_type)
    prefix = "demo/" if account_type == "demo" else ""
    path = f"/trading/{prefix}execution/market-open-orders/by-amount"

    body = {
        "InstrumentId": instrument_id,
        "Amount": amount,
        "IsBuy": is_buy,
        "Leverage": leverage,
    }
    if stop_loss_rate is not None:
        body["StopLossRate"] = stop_loss_rate
    if take_profit_rate is not None:
        body["TakeProfitRate"] = take_profit_rate

    resp = httpx.post(
        f"{BASE_URL}{path}",
        json=body,
        headers=_headers(account_type),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def close_position(
    position_id: int,
    units_to_deduct: Optional[float] = None,
    account_type: str = "demo",
) -> dict:
    """
    Close a position (full or partial).

    Args:
        position_id: eToro position ID
        units_to_deduct: Units to close (None for full close)
        account_type: 'demo' or 'real'
    """
    _check_credentials(account_type)
    prefix = "demo/" if account_type == "demo" else ""
    path = f"/trading/{prefix}execution/market-close-orders/positions/{position_id}"

    body = {}
    if units_to_deduct is not None:
        body["UnitsToDeduct"] = units_to_deduct

    resp = httpx.post(
        f"{BASE_URL}{path}",
        json=body,
        headers=_headers(account_type),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_portfolio(account_type: str = "demo") -> dict:
    """
    Get portfolio details including positions and orders.

    Args:
        account_type: 'demo' or 'real'
    """
    _check_credentials(account_type)
    prefix = "demo/" if account_type == "demo" else ""
    resp = httpx.get(
        f"{BASE_URL}/trading/info/{prefix}portfolio",
        headers=_headers(account_type),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_trading_history(account_type: str = "demo") -> dict:
    """Get trading history."""
    _check_credentials(account_type)
    prefix = "demo/" if account_type == "demo" else ""
    resp = httpx.get(
        f"{BASE_URL}/trading/{prefix}info/trade/history",
        headers=_headers(account_type),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_account_balance(account_type: str = "demo") -> dict:
    """
    Get account balance info from eToro portfolio.

    Args:
        account_type: 'demo' or 'real'

    Returns:
        Dict with balance fields from portfolio response.
    """
    portfolio = get_portfolio(account_type)

    def _find(d: dict, *keys):
        """Get value from dict trying multiple keys, None-safe."""
        for k in keys:
            if k in d:
                return d[k]
        return None

    # Try AggregatedBalance format first
    balance = _find(portfolio, "AggregatedBalance", "aggregatedBalance")
    if balance and isinstance(balance, dict):
        available = _find(balance, "Available", "available")
        if available is None:
            available = 0
        total_equity = _find(balance, "TotalEquity", "totalEquity")
        if total_equity is None:
            total_equity = 0
        invested = _find(balance, "Invested", "invested")
        if invested is None:
            invested = 0
        profit_loss = _find(balance, "ProfitLoss", "profitLoss")
        if profit_loss is None:
            profit_loss = 0
        return {
            "account_type": account_type,
            "available": available,
            "total_equity": total_equity,
            "invested": invested,
            "profit_loss": profit_loss,
        }

    # Fallback: clientPortfolio format (credit = available balance)
    client_portfolio = _find(portfolio, "clientPortfolio", "ClientPortfolio") or {}
    if isinstance(client_portfolio, dict):
        credit = _find(client_portfolio, "credit", "Credit")
        if credit is None:
            credit = 0
        # Sum invested from open positions
        positions = client_portfolio.get("positions") or client_portfolio.get("Positions") or []
        invested = sum(p.get("investedAmount", p.get("InvestedAmount", 0)) or 0 for p in positions)
        return {
            "account_type": account_type,
            "available": credit,
            "total_equity": round(credit + invested, 2),
            "invested": round(invested, 2),
            "profit_loss": 0,
        }

    return {
        "account_type": account_type,
        "available": 0,
        "total_equity": 0,
        "invested": 0,
        "profit_loss": 0,
    }


def get_position_pnl(position_id: int, account_type: str = "demo") -> Optional[float]:
    """
    Fetch the P&L for a specific position from the eToro portfolio.

    Args:
        position_id: eToro position ID
        account_type: 'demo' or 'real'

    Returns:
        The position's profit/loss value, or None if not found.
    """
    try:
        portfolio = get_portfolio(account_type)
        # Try different portfolio response formats
        client_portfolio = portfolio.get("clientPortfolio") or portfolio.get("ClientPortfolio") or {}
        positions = client_portfolio.get("positions") or client_portfolio.get("Positions") or []
        for pos in positions:
            pid = pos.get("positionId") or pos.get("PositionId") or pos.get("positionID")
            if pid == position_id:
                pnl = pos.get("profitLoss") or pos.get("ProfitLoss") or pos.get("netProfit") or pos.get("NetProfit")
                if pnl is not None:
                    return float(pnl)
        return None
    except Exception:
        return None


# =============================================================================
# Interval mapping (TradyBull -> eToro)
# =============================================================================

INTERVAL_MAP = {
    "15min": "FifteenMinutes",
    "15m": "FifteenMinutes",
    "1h": "OneHour",
    "1day": "OneDay",
    "1d": "OneDay",
}


def get_etoro_interval(tradybull_interval: str) -> str:
    """Convert TradyBull interval to eToro interval string."""
    return INTERVAL_MAP.get(tradybull_interval, "OneHour")
