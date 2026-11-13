import threading
import requests
from app.config import config
from app.utils.logger import logger

class TelegramNotifier:
    def __init__(self, token: str = None, chat_id: str = None, enabled: bool = None):
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.enabled = enabled if enabled is not None else config.TELEGRAM_ENABLED

    def is_configured(self) -> bool:
        return bool(self.enabled and self.token and self.chat_id)

    def _send_request(self, message: str):
        if not self.is_configured():
            return
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        try:
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code != 200:
                logger.warning(f"[Telegram] Failed to send message: {resp.text}")
        except Exception as e:
            logger.warning(f"[Telegram] Error sending message: {e}")

    def send_async(self, message: str):
        """Send message asynchronously in a separate thread to prevent blocking trading engine."""
        if not self.is_configured():
            return
        threading.Thread(target=self._send_request, args=(message,), daemon=True).start()

    def notify_bot_status(self, is_running: bool, mode: str, balance: float):
        status_text = "🟢 *BOT STARTED*" if is_running else "🛑 *BOT STOPPED*"
        mm_title = "Compound (ทบกำไร)" if config.MM_MODE == "COMPOUND" else "Martingale (ทบเมื่อแพ้)"
        max_s = config.get_max_steps()
        msg = (
            f"{status_text}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💼 *Account Mode:* `{mode}`\n"
            f"💰 *Current Balance:* `${balance:,.2f}`\n"
            f"🎯 *Base Bet:* `${config.BASE_BET}`\n"
            f"📈 *Strategy:* `Multi-Timeframe Price Action`\n"
            f"🛡️ *Money Mgmt:* `{mm_title}` ({max_s} Steps)\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        self.send_async(msg)

    def notify_order_placed(self, asset: str, direction: str, amount: float, step: int, payout: float, reason: str = ""):
        emoji_dir = "🟢 CALL (UP)" if direction.upper() == "CALL" else "🔴 PUT (DOWN)"
        step_label = "Compound Step" if config.MM_MODE == "COMPOUND" else "Martingale Step"
        max_s = config.get_max_steps()
        msg = (
            f"⚡ *NEW ORDER PLACED*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Asset:* `{asset}`\n"
            f"📈 *Direction:* {emoji_dir}\n"
            f"💵 *Amount:* `${amount:,.2f}` ({step_label} {step}/{max_s})\n"
            f"💎 *Payout:* `{payout:.0%}`\n"
            f"⏱️ *Expiry:* `{config.EXPIRY_MINUTES} min`\n"
            f"💡 *Signal:* {reason or 'Technical Confluence'}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        self.send_async(msg)

    def notify_order_result(self, asset: str, direction: str, amount: float, result: str, profit: float, current_balance: float, next_step: int):
        if result.upper() == "WIN":
            header = "🏆 *TRADE RESULT: WIN!* 🟢"
            profit_str = f"+${profit:,.2f}"
        elif result.upper() == "LOOSE" or result.upper() == "LOSS":
            header = "❌ *TRADE RESULT: LOSS* 🔴"
            profit_str = f"-${amount:,.2f}"
        else:
            header = "⚖️ *TRADE RESULT: EQUAL* ⚪"
            profit_str = "$0.00"

        step_label = "Compound Step" if config.MM_MODE == "COMPOUND" else "Martingale Step"
        max_s = config.get_max_steps()
        msg = (
            f"{header}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Asset:* `{asset}` ({direction.upper()})\n"
            f"💵 *Stake:* `${amount:,.2f}`\n"
            f"💰 *Net PnL:* `{profit_str}`\n"
            f"💼 *Current Balance:* `${current_balance:,.2f}`\n"
            f"🔄 *Next Step:* `{step_label} {next_step}/{max_s}`\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        self.send_async(msg)

    def notify_daily_limit_reached(self, limit_type: str, total_pnl: float, balance: float):
        emoji = "🎉" if limit_type == "TAKE_PROFIT" else "🛑"
        title = "TAKE PROFIT TARGET REACHED!" if limit_type == "TAKE_PROFIT" else "STOP LOSS LIMIT HIT!"
        msg = (
            f"{emoji} *{title}* {emoji}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Session Total PnL:* `${total_pnl:,.2f}`\n"
            f"💰 *Current Balance:* `${balance:,.2f}`\n"
            f"⚠️ *Action:* Trading paused for risk protection.\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        self.send_async(msg)

telegram = TelegramNotifier()
