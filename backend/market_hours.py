"""
Market Hours Utility for TradyBull
Provides market close times for CME futures (NQ=F).

All special dates are PRE-COMPUTED at module load for fast O(1) lookups.
"""

import exchange_calendars as xcals
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Set
import pytz

PARIS_TZ = pytz.timezone('Europe/Paris')
NY_TZ = pytz.timezone('America/New_York')

# Constants
DEFAULT_CLOSE_HOUR_PARIS = 23
DEFAULT_LAST_CANDLE_HOUR = 22
OVERNIGHT_SESSION_END_HOUR = 5
WITCHING_CLOSE_HOUR = 15
BLACK_FRIDAY_CLOSE_HOUR = 18

# Pre-computed caches (filled at module load)
_CLOSED_DATES: Set[date] = set()
_EARLY_CLOSE_HOURS: Dict[date, int] = {}  # date -> close hour
_LAST_CANDLE_HOURS: Dict[date, int] = {}  # date -> last candle hour (for yfinance quirks)


def _get_nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Get the nth occurrence of a weekday in a month (1-indexed)."""
    first_day = date(year, month, 1)
    first_weekday = first_day + timedelta(days=(weekday - first_day.weekday()) % 7)
    return first_weekday + timedelta(weeks=n - 1)


def _get_last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Get the last occurrence of a weekday in a month."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)
    days_back = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=days_back)


def _compute_us_holidays(year: int) -> Set[date]:
    """Compute US holidays with overnight-only sessions for a given year."""
    holidays = set()

    # MLK Day: 3rd Monday of January
    holidays.add(_get_nth_weekday_of_month(year, 1, 0, 3))

    # Presidents Day: 3rd Monday of February
    holidays.add(_get_nth_weekday_of_month(year, 2, 0, 3))

    # Memorial Day: last Monday of May
    holidays.add(_get_last_weekday_of_month(year, 5, 0))

    # Juneteenth: June 19 (observed on Monday if Sunday, Friday if Saturday)
    juneteenth = date(year, 6, 19)
    if juneteenth.weekday() == 6:  # Sunday
        juneteenth = date(year, 6, 20)
    elif juneteenth.weekday() == 5:  # Saturday
        juneteenth = date(year, 6, 18)
    holidays.add(juneteenth)

    # Labor Day: 1st Monday of September
    holidays.add(_get_nth_weekday_of_month(year, 9, 0, 1))

    # Thanksgiving: 4th Thursday of November
    holidays.add(_get_nth_weekday_of_month(year, 11, 3, 4))

    return holidays


def _compute_witching_days(year: int) -> Set[date]:
    """Compute witching days (3rd Friday of Mar/Jun/Sep/Dec) for a given year."""
    witching = set()
    for month in [3, 6, 9, 12]:
        witching.add(_get_nth_weekday_of_month(year, month, 4, 3))
    return witching


def _compute_black_fridays(year: int) -> Set[date]:
    """Compute Black Fridays (day after Thanksgiving) for a given year."""
    thanksgiving = _get_nth_weekday_of_month(year, 11, 3, 4)
    return {thanksgiving + timedelta(days=1)}


def _compute_july_3rd_dates(year: int) -> Set[date]:
    """Compute July 3rd dates (day before Independence Day)."""
    july_3 = date(year, 7, 3)
    # Skip if weekend
    if july_3.weekday() < 5:
        return {july_3}
    return set()


def _compute_christmas_eve_dates(year: int) -> Set[date]:
    """Compute Christmas Eve dates."""
    dec_24 = date(year, 12, 24)
    if dec_24.weekday() < 5:
        return {dec_24}
    return set()


def _get_easter(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _compute_good_friday_eve_dates(year: int) -> Set[date]:
    """Compute Thursday before Good Friday (day before Good Friday)."""
    easter = _get_easter(year)
    good_friday = easter - timedelta(days=2)
    thursday_before = good_friday - timedelta(days=1)
    return {thursday_before}


def _get_dst_offset(d: date) -> int:
    """Get DST offset (+1 during US DST gap with Europe)."""
    # US DST: 2nd Sunday of March to 1st Sunday of November
    # EU DST: Last Sunday of March to last Sunday of October
    # Gap in March: US switches before EU (+1h offset)
    us_dst_start = _get_nth_weekday_of_month(d.year, 3, 6, 2)
    eu_dst_start = _get_last_weekday_of_month(d.year, 3, 6)

    if us_dst_start <= d < eu_dst_start:
        return 1
    return 0


def _precompute_all_dates():
    """Pre-compute all special dates from calendar range."""
    global _CLOSED_DATES, _EARLY_CLOSE_HOURS, _LAST_CANDLE_HOURS

    calendar = xcals.get_calendar("CME")
    start_year = 2006
    end_year = 2028

    # Collect all special dates by year
    all_us_holidays: Set[date] = set()
    all_witching_days: Set[date] = set()
    all_black_fridays: Set[date] = set()
    all_july_3rd: Set[date] = set()
    all_christmas_eve: Set[date] = set()
    all_good_friday_eve: Set[date] = set()

    for year in range(start_year, end_year + 1):
        all_us_holidays.update(_compute_us_holidays(year))
        all_witching_days.update(_compute_witching_days(year))
        all_black_fridays.update(_compute_black_fridays(year))
        all_july_3rd.update(_compute_july_3rd_dates(year))
        all_christmas_eve.update(_compute_christmas_eve_dates(year))
        all_good_friday_eve.update(_compute_good_friday_eve_dates(year))

    # Build closed dates from calendar
    # Start from calendar's first session
    first_session = calendar.first_session.date()
    last_session = calendar.last_session.date()
    current = first_session
    while current <= last_session:
        if not calendar.is_session(current):
            _CLOSED_DATES.add(current)
        current += timedelta(days=1)

    # Build early close hours and last candle hours
    for d in all_us_holidays:
        if d not in _CLOSED_DATES:
            _EARLY_CLOSE_HOURS[d] = OVERNIGHT_SESSION_END_HOUR + 1  # Close at 06:00
            _LAST_CANDLE_HOURS[d] = OVERNIGHT_SESSION_END_HOUR  # Last candle at 05:00

    for d in all_witching_days:
        if d not in _CLOSED_DATES and d not in _EARLY_CLOSE_HOURS:
            dst_offset = _get_dst_offset(d)
            _EARLY_CLOSE_HOURS[d] = WITCHING_CLOSE_HOUR + dst_offset + 1
            _LAST_CANDLE_HOURS[d] = WITCHING_CLOSE_HOUR + dst_offset

    for d in all_black_fridays | all_july_3rd | all_christmas_eve:
        if d not in _CLOSED_DATES and d not in _EARLY_CLOSE_HOURS:
            _EARLY_CLOSE_HOURS[d] = BLACK_FRIDAY_CLOSE_HOUR + 1
            _LAST_CANDLE_HOURS[d] = BLACK_FRIDAY_CLOSE_HOUR

    for d in all_good_friday_eve:
        if d not in _CLOSED_DATES and d not in _EARLY_CLOSE_HOURS:
            _EARLY_CLOSE_HOURS[d] = 22  # Close at 22:00
            _LAST_CANDLE_HOURS[d] = 21  # Last candle at 21:00

    # Special one-time events
    # January 9, 2025 - National Day of Mourning for President Carter
    carter_day = date(2025, 1, 9)
    if carter_day not in _CLOSED_DATES:
        _EARLY_CLOSE_HOURS[carter_day] = 16
        _LAST_CANDLE_HOURS[carter_day] = 15


# Pre-compute at module load
_precompute_all_dates()


# ============== PUBLIC API ==============

def get_calendar():
    """Get CME calendar (cached)."""
    return xcals.get_calendar("CME")


def is_market_closed(d: date) -> bool:
    """Check if market is closed on this date."""
    return d in _CLOSED_DATES


def is_early_close_day(d: date) -> bool:
    """Check if this date is an early close day."""
    return d in _EARLY_CLOSE_HOURS


def get_market_close_hour_paris(timestamp: int) -> int:
    """Get market close hour in Paris time. Returns -1 if market closed."""
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    d = dt.date()

    if d in _CLOSED_DATES:
        return -1

    return _EARLY_CLOSE_HOURS.get(d, DEFAULT_CLOSE_HOUR_PARIS)


def get_last_candle_hour_paris(timestamp: int) -> int:
    """Get the last candle hour before market close."""
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    d = dt.date()

    if d in _CLOSED_DATES:
        return -1

    return _LAST_CANDLE_HOURS.get(d, DEFAULT_LAST_CANDLE_HOUR)


def get_yfinance_last_candle_hour(timestamp: int) -> int:
    """Get expected last candle hour in YFinance data."""
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    d = dt.date()

    return _LAST_CANDLE_HOURS.get(d, DEFAULT_LAST_CANDLE_HOUR)


def is_last_candle_of_day(timestamp: int) -> bool:
    """Check if this candle is the last one before market close."""
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    candle_hour = dt.hour
    expected_last_hour = _LAST_CANDLE_HOURS.get(dt.date(), DEFAULT_LAST_CANDLE_HOUR)
    return candle_hour == expected_last_hour


def is_too_close_to_close(timestamp: int, min_hours_before_close: int = 2) -> bool:
    """Check if we're too close to market close to open a new position."""
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    candle_hour = dt.hour
    d = dt.date()

    if d in _CLOSED_DATES:
        return True

    close_hour = _EARLY_CLOSE_HOURS.get(d, DEFAULT_CLOSE_HOUR_PARIS)
    hours_until_close = close_hour - candle_hour

    return hours_until_close < min_hours_before_close


def is_first_candle_of_session(timestamp: int) -> bool:
    """Check if this is the first candle of the trading session (00:00 Paris)."""
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    return dt.hour == 0


def get_paris_hour(timestamp: int) -> int:
    """Get the hour in Paris timezone."""
    dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
    return dt.hour
