from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import sqlite3
import os
import asyncio
import threading
from typing import Literal, Optional
from contextlib import contextmanager

app = FastAPI(title="TradyBull API")

# CORS pour permettre les requêtes depuis Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3080", "http://127.0.0.1:3080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PARIS_TZ = pytz.timezone('Europe/Paris')
SYMBOL = "NQ=F"  # Nasdaq 100 Futures uniquement
DB_PATH = os.path.join(os.path.dirname(__file__), "tradybull.db")
FETCH_INTERVAL = 10  # seconds

# Retention periods (tripled)
RETENTION = {
    "15m": timedelta(days=6),      # 2 -> 6 jours
    "1h": timedelta(days=21),      # 7 -> 21 jours
    "1d": timedelta(days=540),     # 180 -> 540 jours (18 mois)
}

# Last fetch timestamp
last_fetch_time = None

# WebSocket connections
connected_clients: list[WebSocket] = []


@contextmanager
def get_db():
    """Context manager for database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database tables"""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interval TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER,
                UNIQUE(interval, timestamp)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_interval_timestamp ON candles(interval, timestamp)")
        conn.commit()


def cleanup_old_data():
    """Remove data older than retention period"""
    now = datetime.now(PARIS_TZ)
    with get_db() as conn:
        for interval, retention in RETENTION.items():
            cutoff = int((now - retention).timestamp())
            conn.execute(
                "DELETE FROM candles WHERE interval = ? AND timestamp < ?",
                (interval, cutoff)
            )
        conn.commit()


def store_candles(interval: str, candles: list):
    """Store candles in database, updating existing ones"""
    with get_db() as conn:
        for candle in candles:
            conn.execute("""
                INSERT OR REPLACE INTO candles (interval, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (interval, candle["time"], candle["open"], candle["high"], candle["low"], candle["close"], candle.get("volume", 0)))
        conn.commit()


def get_candles_from_db(interval: str) -> list:
    """Get all candles for an interval from database"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT timestamp, open, high, low, close, volume FROM candles WHERE interval = ? ORDER BY timestamp ASC",
            (interval,)
        ).fetchall()
        return [
            {
                "time": row["timestamp"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"]
            }
            for row in rows
        ]


def is_market_open() -> bool:
    """Check if US market is open (9:30-16:00 ET = 15:30-22:00 Paris)"""
    now = datetime.now(PARIS_TZ)
    day = now.weekday()

    # Weekend
    if day >= 5:
        return False

    hours = now.hour
    minutes = now.minute
    time_in_minutes = hours * 60 + minutes

    # Market hours: 15:30 (930min) to 22:00 (1320min) Paris time
    return 930 <= time_in_minutes < 1320


def get_period_for_gap(timeframe: str, gap: Optional[timedelta]) -> str:
    """Calculate the optimal period to fetch based on data gap.

    yfinance valid periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max

    Args:
        timeframe: The timeframe (15min, 1h, 1day)
        gap: Time since last data, or None if no data exists
    """
    # Default full history periods (tripled)
    full_history = {
        "15min": "7d",    # 7 days for 15min (covers 6 day retention + buffer)
        "1h": "1mo",      # 1 month for 1h (covers 21 day retention)
        "1day": "2y",     # 2 years for daily (covers 18 month retention)
    }

    # If no data, fetch full history
    if gap is None:
        return full_history[timeframe]

    # Add buffer to ensure overlap
    total_hours = gap.total_seconds() / 3600

    # yfinance only accepts: 1d, 5d, 1mo, 3mo, 6mo, 1y, etc.
    # Pick the smallest period that covers the gap
    if total_hours <= 24:
        return "1d"
    elif total_hours <= 5 * 24:
        return "5d"
    elif total_hours <= 30 * 24:
        return "1mo"
    elif total_hours <= 90 * 24:
        return "3mo"
    else:
        return full_history[timeframe]


def get_yf_interval(timeframe: str) -> str:
    """Convert our timeframe to yfinance interval"""
    return {"15min": "15m", "1h": "1h", "1day": "1d"}[timeframe]


def fetch_and_store_data(interval: str) -> list:
    """Fetch data from yfinance and store in database.
    Automatically determines the optimal period based on data gap.

    Args:
        interval: The interval to fetch (15min, 1h, 1day)
    """
    # Get the gap since last data
    yf_interval = get_yf_interval(interval)
    gap = get_data_gap(yf_interval)
    period = get_period_for_gap(interval, gap)

    gap_str = f"{gap.days}d {gap.seconds//3600}h" if gap else "no data"
    print(f"  [{interval}] gap: {gap_str} -> fetching period: {period}")

    ticker = yf.Ticker(SYMBOL)
    data = ticker.history(period=period, interval=yf_interval)

    if data.empty:
        return []

    # Convert to list of candles with Paris timezone
    candles = []
    for timestamp, row in data.iterrows():
        # Convert to Paris timezone
        if timestamp.tzinfo is None:
            ts_utc = pytz.utc.localize(timestamp)
        else:
            ts_utc = timestamp.astimezone(pytz.utc)
        ts_paris = ts_utc.astimezone(PARIS_TZ)

        candles.append({
            "time": int(ts_paris.timestamp()),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"]) if row["Volume"] else 0
        })

    # Store in database
    store_candles(yf_interval, candles)

    return candles


def get_all_data_payload() -> dict:
    """Get all data for WebSocket broadcast"""
    return {
        "type": "data_update",
        "symbol": SYMBOL,
        "market_open": is_market_open(),
        "last_fetch": last_fetch_time.strftime("%H:%M:%S") if last_fetch_time else None,
        "data": {
            "15min": get_candles_from_db("15m"),
            "1h": get_candles_from_db("1h"),
            "1day": get_candles_from_db("1d"),
        }
    }


def broadcast_to_clients(data: dict):
    """Send data to all connected WebSocket clients"""
    if not connected_clients:
        return

    message = json.dumps(data)
    disconnected = []

    for client in connected_clients:
        try:
            # Use asyncio to send from sync context
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                asyncio.ensure_future(client.send_text(message))
            else:
                loop.run_until_complete(client.send_text(message))
        except Exception as e:
            print(f"Error sending to client: {e}")
            disconnected.append(client)

    # Remove disconnected clients
    for client in disconnected:
        if client in connected_clients:
            connected_clients.remove(client)


def fetch_all_intervals():
    """Fetch data for all intervals. Automatically determines optimal period for each."""
    global last_fetch_time
    print(f"[{datetime.now(PARIS_TZ).strftime('%H:%M:%S')}] Fetching data from yfinance...")

    try:
        for interval in ["15min", "1h", "1day"]:
            fetch_and_store_data(interval)
        cleanup_old_data()
        last_fetch_time = datetime.now(PARIS_TZ)
        print(f"[{last_fetch_time.strftime('%H:%M:%S')}] Data fetched and stored successfully")

        # Broadcast to all WebSocket clients
        if connected_clients:
            print(f"  Broadcasting to {len(connected_clients)} client(s)")
            broadcast_to_clients(get_all_data_payload())

    except Exception as e:
        print(f"Error fetching data: {e}")


def get_last_candle_time(interval: str) -> Optional[datetime]:
    """Get the timestamp of the last candle for an interval"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT MAX(timestamp) FROM candles WHERE interval = ?", (interval,)
        ).fetchone()
        if row and row[0]:
            return datetime.fromtimestamp(row[0], tz=PARIS_TZ)
    return None


def get_data_gap(interval: str) -> Optional[timedelta]:
    """Calculate how long since last data update for an interval"""
    last_time = get_last_candle_time(interval)
    if not last_time:
        return None  # No data = need full fetch
    return datetime.now(PARIS_TZ) - last_time


def has_sufficient_data() -> bool:
    """Check if database has sufficient historical data"""
    with get_db() as conn:
        # Check if we have at least some data for each interval
        for interval in ["15m", "1h", "1d"]:
            count = conn.execute(
                "SELECT COUNT(*) FROM candles WHERE interval = ?", (interval,)
            ).fetchone()[0]
            if count < 10:  # Need at least 10 candles per interval
                return False
    return True


def background_fetcher():
    """Background thread that fetches data periodically"""
    import time

    while True:
        fetch_all_intervals()

        # Sleep for FETCH_INTERVAL seconds
        for _ in range(FETCH_INTERVAL):
            time.sleep(1)


# Initialize database on startup
init_db()

# Start background fetcher thread
fetcher_thread = threading.Thread(target=background_fetcher, daemon=True)
fetcher_thread.start()


@app.get("/")
def root():
    return {
        "service": "TradyBull API",
        "status": "running",
        "symbol": SYMBOL,
        "market_open": is_market_open(),
        "last_fetch": last_fetch_time.strftime("%H:%M:%S") if last_fetch_time else None
    }


@app.get("/api/nasdaq")
def get_nasdaq_data(
    interval: Literal["15min", "1h", "1day"] = Query(..., description="Timeframe: 15min, 1h, or 1day")
):
    """Get Nasdaq futures data from database"""
    try:
        # Map interval to db format
        db_interval_map = {"15min": "15m", "1h": "1h", "1day": "1d"}
        db_interval = db_interval_map[interval]

        # Get data from database (no fetch, just read)
        candles = get_candles_from_db(db_interval)

        if not candles:
            raise HTTPException(status_code=404, detail="No data available yet. Please wait for first fetch.")

        return {
            "symbol": SYMBOL,
            "interval": interval,
            "market_open": is_market_open(),
            "data": candles,
            "count": len(candles),
            "last_fetch": last_fetch_time.strftime("%H:%M:%S") if last_fetch_time else None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
def get_status():
    """Get current market status and data info"""
    now = datetime.now(PARIS_TZ)
    market_open = is_market_open()

    # Count records in database
    counts = {}
    with get_db() as conn:
        for interval in ["15m", "1h", "1d"]:
            count = conn.execute(
                "SELECT COUNT(*) FROM candles WHERE interval = ?", (interval,)
            ).fetchone()[0]
            counts[interval] = count

    # Calculate next fetch
    next_fetch = None
    if last_fetch_time:
        next_fetch_dt = last_fetch_time + timedelta(seconds=FETCH_INTERVAL)
        next_fetch = next_fetch_dt.strftime("%H:%M:%S")

    return {
        "current_time_paris": now.strftime("%Y-%m-%d %H:%M:%S"),
        "market_open": market_open,
        "symbol": SYMBOL,
        "database_records": counts,
        "last_fetch": last_fetch_time.strftime("%H:%M:%S") if last_fetch_time else None,
        "next_fetch": next_fetch,
        "fetch_interval_seconds": FETCH_INTERVAL
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data updates"""
    await websocket.accept()
    connected_clients.append(websocket)
    print(f"[WS] Client connected. Total: {len(connected_clients)}")

    try:
        # Send initial data immediately
        await websocket.send_text(json.dumps(get_all_data_payload()))

        # Keep connection alive
        while True:
            # Wait for any message (ping/pong or close)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        print(f"[WS] Total clients: {len(connected_clients)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
