import time
from collections import deque
from datetime import datetime
from typing import Dict, Optional, Tuple
from app.config import config
from app.core.client import iq_client
from app.risk.money_manager import money_manager
from app.utils.logger import logger
from app.utils.telegram_bot import telegram

# In-memory history for Web UI
TRADE_HISTORY = deque(maxlen=100)

class OrderExecutor:
    def __init__(self):
        self.is_trading: bool = False

    def execute_trade(
        self,
        asset: str,
        direction: str,
        amount: float,
        payout: float,
        duration: int = None,
        reason: str = ""
    ) -> Optional[Dict]:
        """
        Executes a binary option trade, waits for expiration, and updates money management.
        """
        duration = duration or config.EXPIRY_MINUTES
        direction_lower = direction.lower()
        step = money_manager.current_step

        trade_record = {
            "id": None,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "asset": asset,
            "direction": direction.upper(),
            "amount": amount,
            "step": step,
            "payout": payout,
            "duration": duration,
            "reason": reason,
            "status": "OPEN",
            "result": "PENDING",
            "profit": 0.0,
            "balance_after": 0.0
        }

        # ----------------------------------------------------
        # Real Live / Practice API Execution
        # ----------------------------------------------------
        if iq_client.is_connected and iq_client.api:
            logger.info(f"[Executor] Placing {direction.upper()} order on {asset} (${amount}, step {step})...")
            try:
                # 1. Place Order
                status, order_id = iq_client.api.buy(amount, asset, direction_lower, duration)
                if not status:
                    logger.error(f"[Executor] Failed to place order on {asset}. Response: {order_id}")
                    return None

                trade_record["id"] = order_id
                TRADE_HISTORY.appendleft(trade_record)
                
                # Send Telegram notification
                telegram.notify_order_placed(asset, direction, amount, step, payout, reason)

                # 2. Wait for expiration and poll result
                logger.info(f"[Executor] Order #{order_id} placed. Waiting for expiration ({duration} min)...")
                # Wait for duration in seconds (minus small buffer)
                wait_seconds = duration * 60
                time.sleep(max(1, wait_seconds - 2))

                # Check result
                result_str, net_profit = self._poll_result(order_id, amount=amount)
                current_bal = iq_client.get_balance()

                # 3. Update Risk & Money Manager
                profit_for_stats = net_profit if result_str == "WIN" else 0.0
                next_step, _ = money_manager.record_result(result_str, amount, profit_for_stats)

                # Update Record
                trade_record["status"] = "CLOSED"
                trade_record["result"] = result_str
                trade_record["profit"] = round(net_profit, 2)
                trade_record["balance_after"] = round(current_bal, 2)

                # Send Telegram result
                telegram.notify_order_result(
                    asset=asset,
                    direction=direction,
                    amount=amount,
                    result=result_str,
                    profit=net_profit,
                    current_balance=current_bal,
                    next_step=next_step
                )

                # 4. Check Daily Stop-Loss / Take-Profit
                limit_hit, limit_type = money_manager.check_daily_limits()
                if limit_hit:
                    logger.warning(f"[Executor] Risk Limit Hit: {limit_type}!")
                    telegram.notify_daily_limit_reached(limit_type, money_manager.session_pnl, current_bal)

                return trade_record
            except Exception as e:
                logger.error(f"[Executor] Exception during order execution: {e}")
                return None

        # ----------------------------------------------------
        # Simulated Mock Execution (When offline or no credentials)
        # ----------------------------------------------------
        else:
            return self._execute_mock_trade(trade_record, asset, direction, amount, step, payout, reason)

    def _poll_result(self, order_id: int, amount: float = 1.0, timeout: int = 45) -> Tuple[str, float]:
        """
        Polls order result accurately from WebSocket order_async and portfolio history.
        Handles both Turbo and Binary options correctly.
        """
        start = time.time()
        while time.time() - start < timeout:
            # 1. Fast check: order_async event from websocket
            try:
                async_dict = iq_client.api.get_async_order(order_id)
                if async_dict and "option-closed" in async_dict and async_dict["option-closed"]:
                    msg = async_dict["option-closed"].get("msg", {})
                    profit_amount = float(msg.get("profit_amount", 0.0))
                    bet_amount = float(msg.get("amount", amount))
                    net_profit = profit_amount - bet_amount
                    if net_profit > 0:
                        return "WIN", net_profit
                    elif net_profit < 0:
                        return "LOSS", -bet_amount
                    else:
                        return "EQUAL", 0.0
            except Exception:
                pass

            # 2. Authoritative check: get_position_history_v2
            try:
                for inst_type in ["turbo-option", "binary-option"]:
                    success, history = iq_client.api.get_position_history_v2(inst_type, 10, 0, 0, 0)
                    if success and history:
                        for p in history.get("positions", []):
                            if p.get("external_id") == order_id:
                                close_reason = str(p.get("close_reason", "")).lower()
                                pnl = float(p.get("pnl_net", p.get("pnl_realized", 0.0)))
                                close_profit = float(p.get("close_profit", 0.0))
                                invest = float(p.get("invest", amount))
                                
                                if close_reason == "win" or pnl > 0 or close_profit > invest:
                                    net_win = pnl if pnl > 0 else (close_profit - invest)
                                    return "WIN", round(net_win, 2)
                                elif close_reason in ("loose", "loss") or pnl < 0 or (close_profit == 0 and invest > 0):
                                    return "LOSS", -invest
                                elif close_reason == "equal" or (close_profit == invest and invest > 0):
                                    return "EQUAL", 0.0
            except Exception:
                pass

            time.sleep(2)

        # Fallback if timeout: Loss safety default
        logger.warning(f"[Executor] Polling result timed out for order #{order_id}. Defaulting to LOSS.")
        return "LOSS", -amount

    def _execute_mock_trade(self, record: dict, asset: str, direction: str, amount: float, step: int, payout: float, reason: str) -> dict:
        """Simulates trade for testing UI and logic without live funds."""
        import random
        record["id"] = int(time.time() * 1000) % 1000000
        TRADE_HISTORY.appendleft(record)
        
        telegram.notify_order_placed(asset, direction, amount, step, payout, f"[MOCK] {reason}")
        
        # Simulate brief waiting
        time.sleep(3)
        
        # 60% win rate simulation
        is_win = random.random() < 0.60
        result_str = "WIN" if is_win else "LOSS"
        profit = (amount * payout) if is_win else 0.0
        
        next_step, _ = money_manager.record_result(result_str, amount, profit)
        fake_balance = 10000.0 + money_manager.session_pnl

        record["status"] = "CLOSED"
        record["result"] = result_str
        record["profit"] = round(profit if is_win else -amount, 2)
        record["balance_after"] = round(fake_balance, 2)

        telegram.notify_order_result(asset, direction, amount, result_str, profit, fake_balance, next_step)
        return record

def get_recent_trades() -> list[dict]:
    return list(TRADE_HISTORY)

executor = OrderExecutor()
