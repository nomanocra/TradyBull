"""
Market Hours Utility for TradyBull
Provides market close times based on US cash market (NYSE) hours.
For daily trading strategies, we use NYSE close time (16:00 NY = 22:00 Paris)
rather than CME futures hours (which are nearly 24h).
"""

import exchange_calendars as xcals
from datetime import datetime, date
from typing import Optional
import pytz

PARIS_TZ = pytz.timezone('Europe/Paris')
NY_TZ = pytz.timezone('America/New_York')

# NYSE calendar for cash market hours (more relevant for daily strategies)
_calendar = None


def get_calendar():
    """Get NYSE calendar (cached)"""
    global _calendar
    if _calendar is None:
        _calendar = xcals.get_calendar("XNYS")  # NYSE
    return _calendar


def get_market_close_hour_paris(timestamp: int) -> int:
    """
    Get the US cash market close hour in Paris time for a given timestamp.

    Uses NYSE calendar:
    - Normal close: 22:00 Paris (16:00 NY)
    - Early close days: 19:00 Paris (13:00 NY) - day after Thanksgiving, Christmas Eve, etc.
    - Closed days: returns -1

    Args:
        timestamp: Unix timestamp

    Returns:
        Hour in Paris time when market closes, or -1 if market is closed that day
    """
    calendar = get_calendar()

    # Convert timestamp to date
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    check_date = dt.date()

    # Check if market is open on this day
    if not calendar.is_session(check_date):
        return -1

    try:
        # Get the session close time
        close_time = calendar.session_close(check_date)

        # Convert to Paris timezone
        close_paris = close_time.astimezone(PARIS_TZ)

        return close_paris.hour
    except Exception:
        # Fallback to default close time
        return 22


def get_last_candle_hour_paris(timestamp: int) -> int:
    """
    Get the hour of the last 1h candle before market close.

    If market closes at 16:00 NY (22:00 Paris), last candle is 21:00-22:00 (timestamped 21:00)
    If market closes at 13:00 NY (19:00 Paris), last candle is 18:00-19:00 (timestamped 18:00)

    Args:
        timestamp: Unix timestamp

    Returns:
        Hour in Paris time for the last candle, or -1 if market is closed
    """
    close_hour = get_market_close_hour_paris(timestamp)

    if close_hour == -1:
        return -1

    # Last candle hour is close_hour - 1
    # (candle 21:00-22:00 is timestamped as 21:00)
    return close_hour - 1


def is_last_candle_of_day(timestamp: int) -> bool:
    """
    Check if the candle at this timestamp is the last one before market close.

    Args:
        timestamp: Unix timestamp of the candle

    Returns:
        True if this is the last candle before close
    """
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    candle_hour = dt.hour

    last_candle_hour = get_last_candle_hour_paris(timestamp)

    if last_candle_hour == -1:
        return False

    return candle_hour == last_candle_hour


def is_market_closed_day(timestamp: int) -> bool:
    """
    Check if the market is closed on this day.

    Args:
        timestamp: Unix timestamp

    Returns:
        True if market is closed
    """
    return get_market_close_hour_paris(timestamp) == -1
