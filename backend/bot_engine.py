"""
Bot Engine for TradyBull.
Manages trading bots that automatically execute trades on eToro based on strategy signals.
"""

import time
import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import pytz

from etoro_client import (
    get_instrument_id,
    open_position_by_cash,
    close_position,
    get_portfolio,
    get_account_balance,
    get_position_pnl,
)

PARIS_TZ = pytz.timezone("Europe/Paris")

# eToro instrument symbol for Nasdaq 100 index
ETORO_NASDAQ_SYMBOL = "NSDQ100"


@dataclass
class BotTrade:
    bot_id: int
    position_id: Optional[int]
    signal_type: str  # 'buy' or 'sell'
    price: float
    amount: float
    status: str  # 'open', 'closed', 'error'
    opened_at: int
    closed_at: Optional[int] = None
    pnl: Optional[float] = None
    error_message: Optional[str] = None


class BotEngine:
    """Manages all trading bots. Runs as a singleton."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        # Cache of instrument IDs
        self._instrument_id: Optional[int] = None

    def _get_db(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _resolve_instrument(self) -> int:
        """Resolve and cache eToro instrument ID for NSDQ100."""
        if self._instrument_id is None:
            self._instrument_id = get_instrument_id(ETORO_NASDAQ_SYMBOL)
            print(f"[BotEngine] Resolved {ETORO_NASDAQ_SYMBOL} -> instrument_id={self._instrument_id}")
        return self._instrument_id

    # =========================================================================
    # Bot CRUD
    # =========================================================================

    def create_bot(
        self,
        name: str,
        strategy_name: str,
        amount: float,
        leverage: int = 1,
        account_type: str = "demo",
        signal_source: str = "yfinance",
    ) -> dict:
        """Create a new trading bot."""
        conn = self._get_db()
        try:
            # Check for duplicate name
            existing = conn.execute(
                "SELECT id FROM trading_bots WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                raise ValueError(f"A bot with the name '{name}' already exists")
            now = int(time.time())
            conn.execute(
                """INSERT INTO trading_bots
                   (name, strategy_name, etoro_instrument_id, amount, leverage, account_type, signal_source, enabled, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'stopped', ?, ?)""",
                (name, strategy_name, 0, amount, leverage, account_type, signal_source, now, now),
            )
            conn.commit()
            bot_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return self.get_bot(bot_id)
        finally:
            conn.close()

    def get_bot(self, bot_id: int) -> Optional[dict]:
        """Get a bot by ID."""
        conn = self._get_db()
        try:
            row = conn.execute("SELECT * FROM trading_bots WHERE id = ?", (bot_id,)).fetchone()
            if not row:
                return None
            return dict(row)
        finally:
            conn.close()

    def list_bots(self) -> list[dict]:
        """List all bots."""
        conn = self._get_db()
        try:
            rows = conn.execute("SELECT * FROM trading_bots ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_bot(self, bot_id: int, **kwargs) -> Optional[dict]:
        """Update bot fields."""
        conn = self._get_db()
        try:
            allowed = {"name", "amount", "leverage", "account_type", "signal_source", "enabled", "status"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return self.get_bot(bot_id)

            updates["updated_at"] = int(time.time())
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [bot_id]
            conn.execute(f"UPDATE trading_bots SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return self.get_bot(bot_id)
        finally:
            conn.close()

    def delete_bot(self, bot_id: int) -> bool:
        """Delete a bot and its trade history."""
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM bot_trades WHERE bot_id = ?", (bot_id,))
            result = conn.execute("DELETE FROM trading_bots WHERE id = ?", (bot_id,))
            conn.execute("COMMIT")
            return result.rowcount > 0
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def start_bot(self, bot_id: int) -> Optional[dict]:
        """Enable a bot (start trading)."""
        # Reset consecutive errors when starting
        conn = self._get_db()
        try:
            conn.execute(
                "UPDATE trading_bots SET consecutive_errors = 0 WHERE id = ?", (bot_id,)
            )
            conn.commit()
        finally:
            conn.close()
        return self.update_bot(bot_id, enabled=1, status="active")

    def stop_bot(self, bot_id: int) -> Optional[dict]:
        """Disable a bot (kill switch)."""
        return self.update_bot(bot_id, enabled=0, status="stopped")

    # =========================================================================
    # Trade history
    # =========================================================================

    def get_trades(self, bot_id: int, limit: int = 50) -> list[dict]:
        """Get trade history for a bot."""
        conn = self._get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM bot_trades WHERE bot_id = ? ORDER BY opened_at DESC LIMIT ?",
                (bot_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_all_trades(self, limit: int = 100) -> list[dict]:
        """Get recent trades across all bots."""
        conn = self._get_db()
        try:
            rows = conn.execute(
                """SELECT bt.*, tb.name as bot_name, tb.strategy_name
                   FROM bot_trades bt
                   JOIN trading_bots tb ON bt.bot_id = tb.id
                   ORDER BY bt.opened_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _record_trade(self, trade: BotTrade, conn) -> int:
        """Record a trade in the database."""
        conn.execute(
            """INSERT INTO bot_trades
               (bot_id, position_id, signal_type, price, amount, status, opened_at, closed_at, pnl, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade.bot_id, trade.position_id, trade.signal_type,
                trade.price, trade.amount, trade.status,
                trade.opened_at, trade.closed_at, trade.pnl, trade.error_message,
            ),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # =========================================================================
    # Signal processing
    # =========================================================================

    def process_new_signals(self, strategy_signals: dict, source: str = 'yfinance'):
        """
        Called by the background fetcher when new signals are detected.
        Checks each active bot and executes trades if their strategy has new signals.
        Only processes bots whose signal_source matches the given source.

        Args:
            strategy_signals: {strategy_name: [Signal, ...]}
            source: 'yfinance' or 'etoro' - only bots configured for this source will be processed
        """
        if not strategy_signals:
            return

        conn = self._get_db()
        try:
            # Get all active bots matching this signal source
            bots = conn.execute(
                "SELECT * FROM trading_bots WHERE enabled = 1 AND status = 'active' AND signal_source = ?",
                (source,)
            ).fetchall()

            for bot in bots:
                strategy_name = bot["strategy_name"]
                if strategy_name not in strategy_signals:
                    continue

                signals = strategy_signals[strategy_name]
                if not signals:
                    continue

                self._process_bot_signals(dict(bot), signals, conn)
        finally:
            conn.close()

    def _process_bot_signals(self, bot: dict, signals: list, conn):
        """Process signals for a specific bot."""
        bot_id = bot["id"]

        # Get the last trade for this bot to determine what signal type we need
        last_trade = conn.execute(
            "SELECT signal_type, status FROM bot_trades WHERE bot_id = ? ORDER BY opened_at DESC LIMIT 1",
            (bot_id,),
        ).fetchone()

        # Determine needed signal type (alternate buy/sell)
        if last_trade is None:
            needed_type = "buy"  # First trade is always a buy
        elif last_trade["status"] == "open" and last_trade["signal_type"] == "buy":
            needed_type = "sell"  # Have an open buy, need sell to close
        elif last_trade["status"] == "closed" or last_trade["signal_type"] == "sell":
            needed_type = "buy"  # Last trade closed, need new buy
        else:
            needed_type = "buy"

        # Find the last signal of the needed type
        target_signal = None
        for signal in reversed(signals):
            if signal.type == needed_type:
                target_signal = signal
                break

        if target_signal is None:
            return

        # Check if we already processed this signal
        existing = conn.execute(
            """SELECT id FROM bot_trades
               WHERE bot_id = ? AND signal_type = ? AND opened_at = ?""",
            (bot_id, target_signal.type, target_signal.signal_timestamp),
        ).fetchone()

        if existing:
            return  # Already processed

        # Execute the trade
        self._execute_trade(bot, target_signal, conn)

    def _get_strategy_stop_loss(self, strategy_name: str, conn) -> Optional[float]:
        """Get the stop loss percentage from a strategy config. Returns None if no SL."""
        # Try dynamic strategies first (most common for bots)
        row = conn.execute(
            "SELECT config FROM dynamic_strategies WHERE name = ?",
            (strategy_name,),
        ).fetchone()
        if row:
            config = json.loads(row[0])
            return config.get("stop_loss")  # e.g. 1.0 for -1%
        return None

    def _execute_trade(self, bot: dict, signal, conn):
        """Execute a trade on eToro for a bot signal."""
        bot_id = bot["id"]
        now = int(time.time())

        print(f"[BotEngine] Bot #{bot_id} ({bot['name']}) executing {signal.type} at {signal.price}")

        try:
            instrument_id = self._resolve_instrument()

            if signal.type == "buy":
                # Check available credit before opening position
                try:
                    balance = get_account_balance(bot["account_type"])
                    available = balance.get("available", 0)
                    if available < bot["amount"]:
                        print(f"[BotEngine] Bot #{bot_id} skipping buy: insufficient balance (${available:.2f} < ${bot['amount']:.2f})")
                        return  # Skip trade, don't count as error
                except Exception as bal_err:
                    print(f"[BotEngine] Bot #{bot_id} warning: could not check balance: {bal_err}")
                    # Continue with trade if balance check fails

                # Calculate stop loss price from strategy config
                sl_rate = None
                sl_pct = self._get_strategy_stop_loss(bot["strategy_name"], conn)
                if sl_pct:
                    sl_rate = round(signal.price * (1 - sl_pct / 100), 2)
                    print(f"[BotEngine] Bot #{bot_id} setting SL at {sl_rate} (-{sl_pct}% from {signal.price})")

                # Open a long position
                result = open_position_by_cash(
                    instrument_id=instrument_id,
                    amount=bot["amount"],
                    is_buy=True,
                    leverage=bot.get("leverage", 1),
                    account_type=bot["account_type"],
                    stop_loss_rate=sl_rate,
                )
                position_id = result.get("PositionId") or result.get("positionId") or result.get("OrderId") or result.get("orderId")

                trade = BotTrade(
                    bot_id=bot_id,
                    position_id=position_id,
                    signal_type="buy",
                    price=signal.price,
                    amount=bot["amount"],
                    status="open",
                    opened_at=signal.signal_timestamp,
                )
                self._record_trade(trade, conn)
                print(f"[BotEngine] Bot #{bot_id} OPENED position {position_id} (${bot['amount']})")

            elif signal.type == "sell":
                # Find the open position to close
                open_trade = conn.execute(
                    """SELECT * FROM bot_trades
                       WHERE bot_id = ? AND signal_type = 'buy' AND status = 'open'
                       ORDER BY opened_at DESC LIMIT 1""",
                    (bot_id,),
                ).fetchone()

                if open_trade and open_trade["position_id"]:
                    # Fetch real P&L from eToro before closing
                    etoro_pnl = get_position_pnl(
                        position_id=open_trade["position_id"],
                        account_type=bot["account_type"],
                    )

                    result = close_position(
                        position_id=open_trade["position_id"],
                        account_type=bot["account_type"],
                    )

                    # Use eToro P&L if available, otherwise fallback to manual calculation
                    if etoro_pnl is not None:
                        pnl = etoro_pnl
                    else:
                        pnl = ((signal.price - open_trade["price"]) / open_trade["price"]) * open_trade["amount"] * bot.get("leverage", 1)

                    # Update the buy trade as closed
                    conn.execute(
                        "UPDATE bot_trades SET status = 'closed', closed_at = ?, pnl = ? WHERE id = ?",
                        (signal.signal_timestamp, pnl, open_trade["id"]),
                    )
                    conn.commit()

                    # Record the sell trade
                    trade = BotTrade(
                        bot_id=bot_id,
                        position_id=open_trade["position_id"],
                        signal_type="sell",
                        price=signal.price,
                        amount=bot["amount"],
                        status="closed",
                        opened_at=signal.signal_timestamp,
                        pnl=pnl,
                    )
                    self._record_trade(trade, conn)
                    print(f"[BotEngine] Bot #{bot_id} CLOSED position {open_trade['position_id']} PnL={pnl:+.2f}")
                else:
                    print(f"[BotEngine] Bot #{bot_id} sell signal but no open position to close")

            # Reset consecutive error counter on success
            conn.execute(
                "UPDATE trading_bots SET consecutive_errors = 0, updated_at = ? WHERE id = ?",
                (now, bot_id),
            )
            conn.commit()

        except Exception as e:
            error_msg = str(e)
            print(f"[BotEngine] Bot #{bot_id} ERROR: {error_msg}")
            trade = BotTrade(
                bot_id=bot_id,
                position_id=None,
                signal_type=signal.type,
                price=signal.price,
                amount=bot["amount"],
                status="error",
                opened_at=now,
                error_message=error_msg,
            )
            self._record_trade(trade, conn)

            # Track consecutive errors and auto-stop after 3
            conn.execute(
                "UPDATE trading_bots SET consecutive_errors = consecutive_errors + 1, updated_at = ? WHERE id = ?",
                (now, bot_id),
            )
            conn.commit()
            error_count = conn.execute(
                "SELECT consecutive_errors FROM trading_bots WHERE id = ?", (bot_id,)
            ).fetchone()["consecutive_errors"]
            if error_count >= 3:
                print(f"[BotEngine] Bot #{bot_id} auto-stopped after {error_count} consecutive errors")
                conn.execute(
                    "UPDATE trading_bots SET status = 'error', enabled = 0, updated_at = ? WHERE id = ?",
                    (now, bot_id),
                )
                conn.commit()

    # =========================================================================
    # Position sync (detect eToro-side closures like SL/TP)
    # =========================================================================

    def sync_open_positions(self):
        """
        Check if positions marked 'open' in DB are still open on eToro.
        If eToro closed them (SL hit, TP hit, manual), update DB accordingly.
        Called periodically from the fetch loop.
        """
        conn = self._get_db()
        try:
            # Get all open trades with their bot info
            open_trades = conn.execute(
                """SELECT bt.id as trade_id, bt.bot_id, bt.position_id, bt.price, bt.amount,
                          tb.account_type, tb.leverage, tb.strategy_name
                   FROM bot_trades bt
                   JOIN trading_bots tb ON bt.bot_id = tb.id
                   WHERE bt.status = 'open' AND bt.position_id IS NOT NULL"""
            ).fetchall()

            if not open_trades:
                return

            # Group by account_type to minimize API calls
            by_account: dict[str, list] = {}
            for trade in open_trades:
                acct = trade["account_type"]
                by_account.setdefault(acct, []).append(trade)

            now = int(time.time())

            for account_type, trades in by_account.items():
                try:
                    portfolio = get_portfolio(account_type)
                except Exception as e:
                    print(f"[BotEngine] sync: could not fetch portfolio ({account_type}): {e}")
                    continue

                # Extract open position IDs from eToro portfolio
                client_portfolio = portfolio.get("clientPortfolio") or portfolio.get("ClientPortfolio") or {}
                positions = client_portfolio.get("positions") or client_portfolio.get("Positions") or []
                etoro_position_ids = set()
                etoro_positions_map = {}
                for pos in positions:
                    pid = pos.get("positionId") or pos.get("PositionId") or pos.get("positionID")
                    if pid:
                        etoro_position_ids.add(int(pid))
                        etoro_positions_map[int(pid)] = pos

                # Check each open trade
                for trade in trades:
                    pos_id = trade["position_id"]
                    if pos_id in etoro_position_ids:
                        continue  # Still open on eToro, nothing to do

                    # Position closed on eToro! Update DB.
                    bot_id = trade["bot_id"]
                    trade_id = trade["trade_id"]
                    buy_price = trade["price"]
                    amount = trade["amount"]
                    leverage = trade["leverage"] or 1

                    # Get P&L, close price and close time from eToro trading history
                    info = self._get_closed_position_info(pos_id, account_type)
                    pnl = info["pnl"]
                    close_price = info["close_price"]
                    close_time = info["close_time"] or now

                    if pnl is None:
                        # Fallback: estimate from last known price
                        last_price_row = conn.execute(
                            "SELECT close FROM backtest_candles WHERE source = 'yfinance' ORDER BY timestamp DESC LIMIT 1"
                        ).fetchone()
                        if last_price_row and buy_price:
                            pnl = round(((last_price_row[0] - buy_price) / buy_price) * amount * leverage, 2)
                            if close_price is None:
                                close_price = last_price_row[0]

                    # Close the buy trade
                    conn.execute(
                        "UPDATE bot_trades SET status = 'closed', closed_at = ?, pnl = ? WHERE id = ?",
                        (close_time, pnl, trade_id),
                    )

                    # Record a sell trade for the closure
                    sell_trade = BotTrade(
                        bot_id=bot_id,
                        position_id=pos_id,
                        signal_type="sell",
                        price=close_price or buy_price,
                        amount=amount,
                        status="closed",
                        opened_at=close_time,
                        pnl=pnl,
                    )
                    self._record_trade(sell_trade, conn)

                    print(f"[BotEngine] Bot #{bot_id} position {pos_id} closed by eToro (SL/TP/manual). "
                          f"Close price={close_price}, PnL={pnl}")

                    conn.execute(
                        "UPDATE trading_bots SET updated_at = ? WHERE id = ?",
                        (now, bot_id),
                    )
                    conn.commit()

        except Exception as e:
            print(f"[BotEngine] sync error: {e}")
        finally:
            conn.close()

    def _get_closed_position_info(self, position_id: int, account_type: str) -> dict:
        """Try to get P&L and close price for a closed position from eToro trading history.
        Returns {'pnl': float|None, 'close_price': float|None, 'close_time': int|None}."""
        result = {"pnl": None, "close_price": None, "close_time": None}
        try:
            from etoro_client import get_trading_history
            history = get_trading_history(account_type)
            trades = history.get("trades") or history.get("Trades") or history.get("history") or history.get("History") or []
            if isinstance(trades, list):
                for t in trades:
                    pid = t.get("positionId") or t.get("PositionId") or t.get("positionID")
                    if pid == position_id:
                        pnl = t.get("netProfit") or t.get("NetProfit") or t.get("profitLoss") or t.get("ProfitLoss")
                        if pnl is not None:
                            result["pnl"] = float(pnl)
                        close_rate = t.get("closeRate") or t.get("CloseRate") or t.get("closePrice") or t.get("ClosePrice")
                        if close_rate is not None:
                            result["close_price"] = float(close_rate)
                        close_date = t.get("closedDate") or t.get("ClosedDate") or t.get("closeDate") or t.get("CloseDate")
                        if close_date:
                            try:
                                from datetime import datetime as _dt
                                dt = _dt.fromisoformat(str(close_date).replace("Z", "+00:00"))
                                result["close_time"] = int(dt.timestamp())
                            except (ValueError, TypeError):
                                pass
                        break
        except Exception:
            pass
        return result

    # =========================================================================
    # Stats
    # =========================================================================

    def get_bot_stats(self, bot_id: int) -> dict:
        """Get aggregated stats for a bot."""
        conn = self._get_db()
        try:
            row = conn.execute(
                """SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(COALESCE(pnl, 0)) as total_pnl,
                    AVG(CASE WHEN pnl IS NOT NULL THEN pnl END) as avg_pnl,
                    MAX(pnl) as best_trade,
                    MIN(pnl) as worst_trade
                FROM bot_trades
                WHERE bot_id = ? AND signal_type = 'sell'""",
                (bot_id,),
            ).fetchone()

            open_count = conn.execute(
                "SELECT COUNT(*) FROM bot_trades WHERE bot_id = ? AND status = 'open'",
                (bot_id,),
            ).fetchone()[0]

            return {
                "total_trades": row["total_trades"] or 0,
                "winning_trades": row["winning_trades"] or 0,
                "losing_trades": row["losing_trades"] or 0,
                "total_pnl": round(row["total_pnl"] or 0, 2),
                "avg_pnl": round(row["avg_pnl"] or 0, 2),
                "best_trade": round(row["best_trade"] or 0, 2),
                "worst_trade": round(row["worst_trade"] or 0, 2),
                "open_positions": open_count,
            }
        finally:
            conn.close()
