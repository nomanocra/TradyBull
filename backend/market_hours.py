"""
Market Hours Utility for TradyBull
Provides market close times for CME futures (NQ=F).

CME Globex E-mini Nasdaq 100 (NQ) hours:
- Normal close: 23:00 Paris (17:00 ET) - daily break
- Early close days: varies based on CME calendar
- Strategies close on the LAST candle before market close (e.g., 22h for 23h close)
"""

import exchange_calendars as xcals
from datetime import datetime, date
from typing import Optional
import pytz

PARIS_TZ = pytz.timezone('Europe/Paris')
NY_TZ = pytz.timezone('America/New_York')

# CME calendar for futures
_calendar = None

# Default close hour in Paris (17:00 ET = 23:00 Paris)
DEFAULT_CLOSE_HOUR_PARIS = 23


def get_calendar():
    """Get CME calendar (cached)"""
    global _calendar
    if _calendar is None:
        _calendar = xcals.get_calendar("CME")
    return _calendar


def get_market_close_hour_paris(timestamp: int) -> int:
    """
    Get the CME futures close hour in Paris time for a given timestamp.

    CME Globex:
    - Normal close: 23:00 Paris (17:00 ET)
    - Early close days: earlier (e.g., Christmas Eve)
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
        # Get the session close time from CME calendar
        close_time = calendar.session_close(check_date)

        # Convert to Paris timezone
        close_paris = close_time.astimezone(PARIS_TZ)

        # CME calendar returns close at midnight (00:00 next day)
        # But actual futures close at 23:00 Paris (17:00 ET daily break)
        # Check if this is an early close day by comparing to default
        close_hour = close_paris.hour

        # If close is at midnight (0), it means normal close at 23:00 Paris
        if close_hour == 0:
            return DEFAULT_CLOSE_HOUR_PARIS

        # Otherwise it's an early close day
        return close_hour
    except Exception:
        # Fallback to default close time
        return DEFAULT_CLOSE_HOUR_PARIS


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


def is_too_close_to_close(timestamp: int, min_hours_before_close: int = 2) -> bool:
    """
    Check if we're too close to market close to open a new position.

    Args:
        timestamp: Unix timestamp of the candle
        min_hours_before_close: Minimum hours required before close (default 2)

    Returns:
        True if we're within min_hours_before_close of market close
    """
    close_hour = get_market_close_hour_paris(timestamp)

    if close_hour == -1:
        return True  # Market closed, don't open

    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    candle_hour = dt.hour

    # Hours remaining until close
    hours_until_close = close_hour - candle_hour

    return hours_until_close < min_hours_before_close
