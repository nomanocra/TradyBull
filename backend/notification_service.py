"""
Notification Service for TradyBull
Handles sending notifications via Telegram and Desktop (browser)
"""

import httpx
import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any
import pytz

DB_PATH = os.path.join(os.path.dirname(__file__), "tradybull.db")
PARIS_TZ = pytz.timezone('Europe/Paris')


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_notification_settings(strategy_name: str) -> Optional[Dict[str, Any]]:
    """Get notification settings for a strategy"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM notification_settings WHERE strategy_name = ?",
            (strategy_name,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_all_notification_settings() -> list[Dict[str, Any]]:
    """Get all notification settings"""
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM notification_settings").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def save_notification_settings(
    strategy_name: str,
    enabled: bool = False,
    desktop_enabled: bool = False,
    telegram_enabled: bool = False,
    telegram_bot_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    notify_buy: bool = True,
    notify_sell: bool = True,
    time_start: str = "00:00",
    time_end: str = "23:59"
) -> Dict[str, Any]:
    """Save or update notification settings for a strategy"""
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO notification_settings
            (strategy_name, enabled, desktop_enabled, telegram_enabled,
             telegram_bot_token, telegram_chat_id, notify_buy, notify_sell,
             time_start, time_end, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%s', 'now'))
            ON CONFLICT(strategy_name) DO UPDATE SET
                enabled = excluded.enabled,
                desktop_enabled = excluded.desktop_enabled,
                telegram_enabled = excluded.telegram_enabled,
                telegram_bot_token = excluded.telegram_bot_token,
                telegram_chat_id = excluded.telegram_chat_id,
                notify_buy = excluded.notify_buy,
                notify_sell = excluded.notify_sell,
                time_start = excluded.time_start,
                time_end = excluded.time_end,
                updated_at = strftime('%s', 'now')
        """, (
            strategy_name,
            int(enabled),
            int(desktop_enabled),
            int(telegram_enabled),
            telegram_bot_token,
            telegram_chat_id,
            int(notify_buy),
            int(notify_sell),
            time_start,
            time_end
        ))
        conn.commit()
        return get_notification_settings(strategy_name)
    finally:
        conn.close()


def delete_notification_settings(strategy_name: str) -> bool:
    """Delete notification settings for a strategy"""
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM notification_settings WHERE strategy_name = ?",
            (strategy_name,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def log_notification(
    strategy_name: str,
    signal_type: str,
    price: float,
    channel: str,
    message: str,
    signal_timestamp: int,
    success: bool = True,
    error_message: Optional[str] = None
) -> None:
    """Log a notification to the history table"""
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO notification_history
            (strategy_name, signal_type, price, channel, message, signal_timestamp, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_name,
            signal_type,
            price,
            channel,
            message,
            signal_timestamp,
            int(success),
            error_message
        ))
        conn.commit()
    finally:
        conn.close()


def get_notification_history(
    strategy_name: str,
    limit: int = 50
) -> list[Dict[str, Any]]:
    """Get notification history for a strategy"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT id, strategy_name, sent_at, signal_type, price, channel, message, success, error_message, signal_timestamp
            FROM notification_history
            WHERE strategy_name = ?
            ORDER BY sent_at DESC
            LIMIT ?
        """, (strategy_name, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def was_notification_already_sent(
    strategy_name: str,
    signal_timestamp: int,
    signal_type: str
) -> bool:
    """Check if a notification was already sent for this signal"""
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT COUNT(*) as count FROM notification_history
            WHERE strategy_name = ? AND signal_timestamp = ? AND signal_type = ?
        """, (strategy_name, signal_timestamp, signal_type)).fetchone()
        return row['count'] > 0
    finally:
        conn.close()


def is_within_time_window(time_start: str, time_end: str) -> bool:
    """Check if current time is within the notification time window"""
    now = datetime.now(PARIS_TZ)
    current_time = now.strftime("%H:%M")

    # Handle overnight windows (e.g., 22:00 - 06:00)
    if time_start <= time_end:
        return time_start <= current_time <= time_end
    else:
        return current_time >= time_start or current_time <= time_end


async def send_telegram_message(
    bot_token: str,
    chat_id: str,
    message: str
) -> Dict[str, Any]:
    """Send a message via Telegram Bot API"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        })
        return response.json()


def format_signal_message(
    strategy_name: str,
    strategy_display_name: str,
    signal_type: str,
    price: float,
    timestamp: int
) -> str:
    """Format a signal notification message"""
    dt = datetime.fromtimestamp(timestamp, PARIS_TZ)
    time_str = dt.strftime("%d/%m/%Y %H:%M")

    emoji = "🟢" if signal_type == "buy" else "🔴"
    action = "BUY" if signal_type == "buy" else "SELL"

    return (
        f"{emoji} <b>{action}</b> Signal\n\n"
        f"📊 Strategy: {strategy_display_name}\n"
        f"💰 Price: {price:,.2f}\n"
        f"🕐 Time: {time_str}\n"
    )


async def send_signal_notification(
    strategy_name: str,
    strategy_display_name: str,
    signal_type: str,
    price: float,
    timestamp: int
) -> Dict[str, Any]:
    """
    Send notification for a new signal.
    Returns dict with status of each notification channel.
    """
    result = {
        "strategy": strategy_name,
        "signal_type": signal_type,
        "notifications_sent": [],
        "errors": []
    }

    # Get notification settings
    settings = get_notification_settings(strategy_name)
    if not settings:
        result["errors"].append("No notification settings found")
        return result

    if not settings["enabled"]:
        result["errors"].append("Notifications disabled for this strategy")
        return result

    # Check signal type filter
    if signal_type == "buy" and not settings["notify_buy"]:
        result["errors"].append("Buy notifications disabled")
        return result
    if signal_type == "sell" and not settings["notify_sell"]:
        result["errors"].append("Sell notifications disabled")
        return result

    # Check time window
    if not is_within_time_window(settings["time_start"], settings["time_end"]):
        result["errors"].append(f"Outside notification window ({settings['time_start']}-{settings['time_end']})")
        return result

    # Format message
    message = format_signal_message(
        strategy_name,
        strategy_display_name,
        signal_type,
        price,
        timestamp
    )

    # Send Telegram notification
    if settings["telegram_enabled"] and settings["telegram_bot_token"] and settings["telegram_chat_id"]:
        try:
            telegram_result = await send_telegram_message(
                settings["telegram_bot_token"],
                settings["telegram_chat_id"],
                message
            )
            if telegram_result.get("ok"):
                result["notifications_sent"].append("telegram")
                log_notification(
                    strategy_name=strategy_name,
                    signal_type=signal_type,
                    price=price,
                    channel="telegram",
                    message=message,
                    signal_timestamp=timestamp,
                    success=True
                )
            else:
                error_msg = telegram_result.get('description', 'Unknown error')
                result["errors"].append(f"Telegram error: {error_msg}")
                log_notification(
                    strategy_name=strategy_name,
                    signal_type=signal_type,
                    price=price,
                    channel="telegram",
                    message=message,
                    signal_timestamp=timestamp,
                    success=False,
                    error_message=error_msg
                )
        except Exception as e:
            error_msg = str(e)
            result["errors"].append(f"Telegram exception: {error_msg}")
            log_notification(
                strategy_name=strategy_name,
                signal_type=signal_type,
                price=price,
                channel="telegram",
                message=message,
                signal_timestamp=timestamp,
                success=False,
                error_message=error_msg
            )

    # Desktop notifications are handled by the frontend via WebSocket
    if settings["desktop_enabled"]:
        result["notifications_sent"].append("desktop_pending")
        log_notification(
            strategy_name=strategy_name,
            signal_type=signal_type,
            price=price,
            channel="desktop",
            message=message,
            signal_timestamp=timestamp,
            success=True
        )

    return result


async def test_telegram_notification(
    bot_token: str,
    chat_id: str
) -> Dict[str, Any]:
    """Test Telegram notification configuration"""
    test_message = (
        "🔔 <b>TradyBull Test Notification</b>\n\n"
        "✅ Your Telegram notifications are configured correctly!"
    )

    try:
        result = await send_telegram_message(bot_token, chat_id, test_message)
        return {
            "success": result.get("ok", False),
            "message": "Test notification sent!" if result.get("ok") else result.get("description", "Unknown error")
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }
