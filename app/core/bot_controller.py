import threading
import time
from typing import Optional
from app.config import config
from app.core.client import iq_client
from app.core.data_feed import data_feed
from app.core.executor import executor
from app.core.scanner import scanner
from app.risk.money_manager import money_manager
from app.strategies.trend_pullback import trend_strategy
from app.utils.logger import logger
from app.utils.telegram_bot import telegram

class BotController:
    def __init__(self):
        self.is_running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.selected_pair: Optional[str] = None
        self.top_pairs: list = []
        self.last_signal: Optional[str] = None
        self.last_analysis_info: dict = {}

    def start(self) -> dict:
        if self.is_running:
            return {"status": "error", "message": "Bot is already running"}

        # Attempt to connect to IQ Option if credentials provided
        if config.IQ_EMAIL and config.IQ_PASSWORD and not iq_client.is_connected:
            connected, reason = iq_client.connect()
            if not connected and reason != "2FA Required":
                logger.warning(f"[Bot] Could not connect to IQ Option: {reason}. Running in DEMO/SIMULATION mode.")

        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        balance = iq_client.get_balance() if iq_client.is_connected else 10000.0
        mode = iq_client.current_mode if iq_client.is_connected else "SIMULATION"
        logger.info(f"[Bot] Started! Mode: {mode} | Balance: ${balance:,.2f}")
        telegram.notify_bot_status(is_running=True, mode=mode, balance=balance)

        return {"status": "success", "message": "Bot started successfully", "mode": mode}

    def stop(self) -> dict:
        if not self.is_running:
            return {"status": "error", "message": "Bot is not running"}

        self.is_running = False
        self._stop_event.set()
        logger.info("[Bot] Stopping bot...")

        balance = iq_client.get_balance() if iq_client.is_connected else 10000.0
        mode = iq_client.current_mode if iq_client.is_connected else "SIMULATION"
        telegram.notify_bot_status(is_running=False, mode=mode, balance=balance)

        return {"status": "success", "message": "Bot stopped successfully"}

    def _run_loop(self):
        logger.info("[Bot] Main trading loop active.")
        last_log_time = 0.0

        while self.is_running and not self._stop_event.is_set():
            try:
                # 1. Check Daily Risk Limits (Stop Loss / Take Profit)
                limit_hit, limit_type = money_manager.check_daily_limits()
                if limit_hit:
                    logger.warning(f"[Bot] Session halted: {limit_type} hit! (PnL: ${money_manager.session_pnl:,.2f})")
                    self.stop()
                    break

                # 2. Scan for high-payout pairs (>= 88%, Top 5)
                top_pairs = scanner.get_top_pairs(limit=config.TOP_PAIRS_COUNT)
                if not top_pairs:
                    logger.warning(f"[Bot] No pairs available with payout >= {config.MIN_PAYOUT:.0%}. Waiting 15s...")
                    self._stop_event.wait(15)
                    continue

                self.top_pairs = top_pairs
                trade_executed = False
                cycle_summary = []

                # 3. Evaluate each of the Top 5 pairs for high-probability signals
                for pair_info in top_pairs:
                    if not self.is_running or self._stop_event.is_set():
                        break

                    active_pair = pair_info["pair"]
                    payout = pair_info["payout"]
                    self.selected_pair = active_pair

                    # Fetch Candles according to strategy timeframe:
                    # For 5M Options: M1 for Entry, M5 for Macro Trend (fast and accurate pullback entries)
                    # For 15M Options: M5 for Entry, M15 for Macro Trend
                    if config.EXPIRY_MINUTES >= 15:
                        entry_tf = 300   # 5M
                        macro_tf = 900   # 15M
                    elif config.EXPIRY_MINUTES >= 5:
                        entry_tf = 60    # 1M
                        macro_tf = 300   # 5M
                    else:
                        entry_tf = 60    # 1M
                        macro_tf = 300   # 5M

                    macro_candles = data_feed.get_candles(active_pair, timeframe_sec=macro_tf, count=60)
                    entry_candles = data_feed.get_candles(active_pair, timeframe_sec=entry_tf, count=60)

                    if entry_candles is None or entry_candles.empty:
                        continue

                    # Analyze Technical Signals
                    signal, info = trend_strategy.analyze(entry_candles, macro_candles)
                    self.last_signal = signal
                    self.last_analysis_info = info
                    rsi_val = info.get("rsi", "-")
                    trend_val = info.get("macro_trend", "NEUTRAL")
                    cycle_summary.append(f"{active_pair}: {trend_val} RSI:{rsi_val}")

                    # Execute Trade if Signal Triggered
                    if signal in ("CALL", "PUT"):
                        bet_amount = money_manager.get_current_bet()
                        current_step = money_manager.current_step
                        reason = info.get("reason", "Technical Confluence")
                        logger.info(f"[Bot] 🎯 Signal TRIGGERED: {signal} on {active_pair} ({payout:.0%})! Reason: {reason} | Placing order ${bet_amount} (Step {current_step})...")

                        trade = executor.execute_trade(
                            asset=active_pair,
                            direction=signal,
                            amount=bet_amount,
                            payout=payout,
                            duration=config.EXPIRY_MINUTES,
                            reason=reason
                        )
                        
                        if trade:
                            logger.info(f"[Bot] Trade finished: {trade.get('result')} | PnL: ${trade.get('profit')} | Balance: ${trade.get('balance_after')}")
                        
                        trade_executed = True
                        break

                # Periodic status log for user visibility
                now = time.time()
                if not trade_executed and (now - last_log_time >= 15):
                    logger.info(f"[Bot] Monitoring Top {len(cycle_summary)}: [{', '.join(cycle_summary)}] - Waiting for pullback setup...")
                    last_log_time = now

                # Sleep interval between cycle checks (5 seconds)
                self._stop_event.wait(5)

            except Exception as e:
                logger.error(f"[Bot] Error in trading loop: {e}")
                self._stop_event.wait(10)

        self.is_running = False
        logger.info("[Bot] Trading loop exited.")

    def get_status(self) -> dict:
        balance = iq_client.get_balance() if iq_client.is_connected else 10000.0 + money_manager.session_pnl
        mode = iq_client.current_mode if iq_client.is_connected else "SIMULATION (MOCK)"
        return {
            "is_running": self.is_running,
            "connected": iq_client.is_connected,
            "two_factor_required": iq_client.two_factor_required,
            "mode": mode,
            "balance": round(balance, 2),
            "selected_pair": self.selected_pair or "Scanning Top 5...",
            "top_pairs": self.top_pairs,
            "last_signal": self.last_signal or "SCANNING",
            "analysis_info": self.last_analysis_info,
            "risk_summary": money_manager.get_summary()
        }

bot_controller = BotController()
