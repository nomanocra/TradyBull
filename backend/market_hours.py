"""
Market Hours Utility for TradyBull
Provides market close times for CME futures (NQ=F).

CME Globex E-mini Nasdaq 100 (NQ) hours:
- Normal close: 23:00 Paris (17:00 ET) - daily break
- Early close days: varies based on CME calendar
- Strategies close on the LAST candle before market close (e.g., 22h for 23h close)

YFinance data quirks handled:
- US Holidays: Only overnight session available (closes ~05:00-06:00 Paris)
- Witching days (3rd Friday): Data ends at ~15:00 Paris
- Black Friday: Data ends at ~18:00 Paris
- DST transitions: +/- 1h offset during US/EU DST gap
"""

import exchange_calendars as xcals
from datetime import datetime, date, timedelta
from typing import Optional
import pytz

PARIS_TZ = pytz.timezone('Europe/Paris')
NY_TZ = pytz.timezone('America/New_York')

# CME calendar for futures
_calendar = None

# Default close hour in Paris (17:00 ET = 23:00 Paris)
DEFAULT_CLOSE_HOUR_PARIS = 23

# Overnight session end hour (Paris time)
OVERNIGHT_SESSION_END_HOUR = 5

# Early close threshold - if CME closes before this hour (Paris), it's a holiday
# Normal close is 23:00 Paris (shown as 00:00 next day in calendar)
EARLY_CLOSE_THRESHOLD_PARIS = 20

# Witching day close hour (Paris time) - 3rd Friday of Mar/Jun/Sep/Dec
WITCHING_CLOSE_HOUR = 15

# Black Friday close hour (Paris time)
BLACK_FRIDAY_CLOSE_HOUR = 18


def is_early_close_day(d: date) -> bool:
    """
    Check if this date is an early close day (holiday or special day).

    Uses CME calendar to detect early close days (close before 20:00 Paris).
    Returns True for holidays like MLK Day, Labor Day, Thanksgiving, etc.
    """
    calendar = get_calendar()

    # Check if market is open
    if not calendar.is_session(d):
        return False

    try:
        close_time = calendar.session_close(d)
        close_paris = close_time.astimezone(PARIS_TZ)
        close_hour = close_paris.hour

        # If close is at midnight (0), it's a normal day
        if close_hour == 0:
            return False

        # If close is before threshold, it's an early close day
        return close_hour < EARLY_CLOSE_THRESHOLD_PARIS
    except Exception:
        return False


def is_us_holiday_overnight_only(d: date) -> bool:
    """
    Check if this date is a US holiday with ONLY overnight session in YFinance.

    These are specific holidays where YFinance only has data until ~05:00:
    - MLK Day (3rd Monday of January)
    - Presidents Day (3rd Monday of February)
    - Memorial Day (last Monday of May)
    - Juneteenth (June 19)
    - Labor Day (1st Monday of September)
    - Thanksgiving (4th Thursday of November)

    Other early close days (Black Friday, Christmas Eve) have data until 18:00.
    """
    # MLK Day: 3rd Monday of January
    if d.weekday() == 0 and d.month == 1 and 15 <= d.day <= 21:
        return True

    # Presidents Day: 3rd Monday of February
    if d.weekday() == 0 and d.month == 2 and 15 <= d.day <= 21:
        return True

    # Memorial Day: last Monday of May (day 25-31)
    if d.weekday() == 0 and d.month == 5 and d.day >= 25:
        return True

    # Juneteenth: June 19 (or observed Monday if weekend)
    if d.month == 6 and d.day == 19:
        return True

    # Labor Day: 1st Monday of September (day 1-7)
    if d.weekday() == 0 and d.month == 9 and d.day <= 7:
        return True

    # Thanksgiving: 4th Thursday of November (day 22-28)
    if d.weekday() == 3 and d.month == 11 and 22 <= d.day <= 28:
        return True

    return False


def is_witching_day(d: date) -> bool:
    """Check if this is a witching day (3rd Friday of Mar/Jun/Sep/Dec)"""
    # Must be Friday
    if d.weekday() != 4:
        return False
    # Must be witching month
    if d.month not in (3, 6, 9, 12):
        return False
    # Must be 3rd Friday (day 15-21)
    return 15 <= d.day <= 21


def is_black_friday(d: date) -> bool:
    """Check if this is Black Friday (day after US Thanksgiving = 4th Thursday of November)"""
    if d.month != 11 or d.weekday() != 4:  # Must be Friday in November
        return False
    # Thanksgiving is 4th Thursday, so Black Friday is between 23rd and 29th
    return 23 <= d.day <= 29


def is_day_before_july_4th(d: date) -> bool:
    """Check if this is July 3rd (early close before Independence Day)"""
    return d.month == 7 and d.day == 3


def get_dst_offset(d: date) -> int:
    """
    Get DST offset adjustment for YFinance data.

    US DST: 2nd Sunday of March to 1st Sunday of November
    EU DST: Last Sunday of March to Last Sunday of October

    During transition gaps:
    - Mon-Thu: YFinance shows +1h (23:00 instead of 22:00)
    - Friday: YFinance shows -1h (21:00 instead of 22:00)

    Returns:
        +1 for Mon-Thu during DST gap
        -1 for Friday during DST gap
        0 otherwise
    """
    year = d.year

    # Find US DST start (2nd Sunday of March)
    march_1 = date(year, 3, 1)
    days_to_sunday = (6 - march_1.weekday()) % 7
    us_dst_start = march_1 + timedelta(days=days_to_sunday + 7)  # 2nd Sunday

    # Find EU DST start (last Sunday of March)
    march_31 = date(year, 3, 31)
    days_back_to_sunday = (march_31.weekday() + 1) % 7
    eu_dst_start = march_31 - timedelta(days=days_back_to_sunday)

    # Find EU DST end (last Sunday of October)
    oct_31 = date(year, 10, 31)
    days_back_to_sunday = (oct_31.weekday() + 1) % 7
    eu_dst_end = oct_31 - timedelta(days=days_back_to_sunday)

    # Find US DST end (1st Sunday of November)
    nov_1 = date(year, 11, 1)
    days_to_sunday = (6 - nov_1.weekday()) % 7
    us_dst_end = nov_1 + timedelta(days=days_to_sunday)

    # Check if in DST transition gap
    in_spring_gap = us_dst_start <= d < eu_dst_start
    in_fall_gap = eu_dst_end <= d < us_dst_end

    if in_spring_gap or in_fall_gap:
        # Friday shows -1h, other days show +1h
        if d.weekday() == 4:  # Friday
            return -1
        else:
            return 1

    return 0


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


def get_yfinance_last_candle_hour(timestamp: int) -> int:
    """
    Get the expected last candle hour in YFinance data, accounting for data quirks.

    This handles:
    - US Holidays: Only overnight session (close at 05:00)
    - Witching days: Early close at 15:00
    - Black Friday: Early close at 18:00
    - July 3rd: Early close at 18:00
    - DST transitions: +1h offset

    Args:
        timestamp: Unix timestamp

    Returns:
        Hour in Paris time for the expected last candle in YFinance data
    """
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    d = dt.date()

    # US Holiday - only overnight session available (MLK, Presidents, Memorial, Labor Day)
    if is_us_holiday_overnight_only(d):
        return OVERNIGHT_SESSION_END_HOUR

    # Other early close days (Thanksgiving, Black Friday, Christmas Eve) have data until 18:00
    if is_early_close_day(d):
        return BLACK_FRIDAY_CLOSE_HOUR

    # Witching day (3rd Friday of Mar/Jun/Sep/Dec)
    if is_witching_day(d):
        # Apply DST offset to witching days too
        dst_offset = get_dst_offset(d)
        return WITCHING_CLOSE_HOUR + dst_offset

    # Black Friday
    if is_black_friday(d):
        return BLACK_FRIDAY_CLOSE_HOUR

    # July 3rd (day before Independence Day)
    if is_day_before_july_4th(d):
        return BLACK_FRIDAY_CLOSE_HOUR  # Same early close

    # Normal day - use calendar with DST adjustment
    last_hour = get_last_candle_hour_paris(timestamp)
    if last_hour == -1:
        last_hour = DEFAULT_CLOSE_HOUR_PARIS - 1  # Default to 22:00

    # Apply DST offset
    dst_offset = get_dst_offset(d)
    return last_hour + dst_offset


def is_last_candle_of_day(timestamp: int) -> bool:
    """
    Check if the candle at this timestamp is the last one before market close.

    Uses YFinance-adjusted hours to handle:
    - US Holidays (overnight only)
    - Witching days
    - Black Friday
    - DST transitions

    Args:
        timestamp: Unix timestamp of the candle

    Returns:
        True if this is the last candle before close
    """
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    candle_hour = dt.hour

    # Use YFinance-adjusted last candle hour
    expected_last_hour = get_yfinance_last_candle_hour(timestamp)

    return candle_hour == expected_last_hour


def is_market_closed_day(timestamp: int) -> bool:
    """
    Check if the market is closed on this day.

    Args:
        timestamp: Unix timestamp

    Returns:
        True if market is closed
    """
    return get_market_close_hour_paris(timestamp) == -1


def get_paris_hour(timestamp: int) -> int:
    """
    Get the hour in Paris time for a given timestamp.

    Args:
        timestamp: Unix timestamp

    Returns:
        Hour in Paris time (0-23)
    """
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    return dt.hour


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


def is_first_candle_of_session(timestamp: int) -> bool:
    """
    Check if the candle at this timestamp is the first one after market reopen.

    Market reopens at 00:00 Paris (after 23:00 close).

    Args:
        timestamp: Unix timestamp of the candle

    Returns:
        True if this is the first candle of the trading session (00:00 Paris)
    """
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    return dt.hour == 0
