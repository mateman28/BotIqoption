from typing import Tuple
from app.config import config
from app.utils.logger import logger

class MoneyManager:
    def __init__(self):
        self.ladder: list[float] = config.get_martingale_ladder()
        self.max_steps: int = config.MARTINGALE_STEPS
        self.current_step: int = 1
        
        # Session Statistics
        self.total_trades: int = 0
        self.wins: int = 0
        self.losses: int = 0
        self.ties: int = 0
        self.session_pnl: float = 0.0

    def reload_config(self):
        self.ladder = config.get_martingale_ladder()
        self.max_steps = config.MARTINGALE_STEPS

    def get_current_bet(self) -> float:
        """Returns the bet amount for the current martingale step."""
        idx = max(0, min(self.current_step - 1, len(self.ladder) - 1))
        return self.ladder[idx]

    def record_result(self, result: str, stake: float, profit: float) -> Tuple[int, str]:
        """
        Updates statistics and determines the next martingale step.
        result: 'WIN', 'LOSS', or 'EQUAL'
        Returns: (next_step, status_message)
        """
        self.total_trades += 1
        res = result.upper()

        if res == "WIN":
            self.wins += 1
            self.session_pnl += profit
            old_step = self.current_step
            self.current_step = 1  # Reset to step 1
            msg = f"Win! Reset Martingale from step {old_step} back to 1."
            logger.info(f"[MoneyManager] {msg}")
            return self.current_step, msg

        elif res in ("LOSS", "LOOSE"):
            self.losses += 1
            self.session_pnl -= stake
            if self.current_step >= self.max_steps:
                # Max steps reached! Cut Loss safety mechanism
                msg = f"Max Martingale steps ({self.max_steps}) reached! Safety Cut-Loss triggered. Resetting to step 1."
                self.current_step = 1
                logger.warning(f"[MoneyManager] {msg}")
                return self.current_step, msg
            else:
                self.current_step += 1
                next_bet = self.get_current_bet()
                msg = f"Loss on step {self.current_step - 1}. Advancing to step {self.current_step} (${next_bet})."
                logger.info(f"[MoneyManager] {msg}")
                return self.current_step, msg

        else:  # EQUAL / TIE
            self.ties += 1
            msg = f"Tie/Equal. Repeating current step {self.current_step}."
            logger.info(f"[MoneyManager] {msg}")
            return self.current_step, msg

    def check_daily_limits(self) -> Tuple[bool, str]:
        """
        Checks if Stop-Loss or Take-Profit threshold has been hit.
        Returns: (limit_hit: bool, limit_type: str)
        """
        if config.DAILY_STOP_LOSS > 0 and self.session_pnl <= -abs(config.DAILY_STOP_LOSS):
            return True, "STOP_LOSS"
        
        if config.DAILY_TAKE_PROFIT > 0 and self.session_pnl >= abs(config.DAILY_TAKE_PROFIT):
            return True, "TAKE_PROFIT"

        return False, "NONE"

    def get_summary(self) -> dict:
        total = self.total_trades
        win_rate = (self.wins / total * 100) if total > 0 else 0.0
        return {
            "total_trades": total,
            "wins": self.wins,
            "losses": self.losses,
            "ties": self.ties,
            "win_rate": round(win_rate, 1),
            "session_pnl": round(self.session_pnl, 2),
            "current_step": self.current_step,
            "current_bet": self.get_current_bet(),
            "max_steps": self.max_steps,
            "ladder": self.ladder
        }

    def reset_session(self):
        self.current_step = 1
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.session_pnl = 0.0

money_manager = MoneyManager()
