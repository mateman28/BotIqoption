from typing import Tuple, List, Dict
from app.config import config
from app.utils.logger import logger

class MoneyManager:
    """
    Advanced Money Management System supporting:
    1. Compound / Masaniello-lite (ทบกำไรแบบจำกัดขั้น):
       - Capital risk capped at Base Bet.
       - Reinvests/compounds profit for a limited number of steps (e.g. 2 or 3 steps).
       - When target steps are won: Takes profit and resets to Step 1.
       - When any loss occurs: Immediately resets to Step 1 without escalating risk.
    2. Traditional Martingale (ทบเมื่อแพ้):
       - Multiplies bet on loss to recover drawdown up to MAX steps.
    """
    def __init__(self):
        self.mode: str = getattr(config, "MM_MODE", "COMPOUND").upper()
        self.base_bet: float = config.BASE_BET
        self.compound_steps: int = getattr(config, "COMPOUND_STEPS", 2)
        self.martingale_steps: int = config.MARTINGALE_STEPS
        self.reinvest_ratio: float = getattr(config, "COMPOUND_REINVEST_RATIO", 1.0)
        
        self.max_steps: int = config.get_max_steps()
        self.current_step: int = 1
        self.current_bet: float = self.base_bet
        self.cycle_accumulated_profit: float = 0.0

        # Ladder representation
        self.ladder: List[float] = config.get_ladder()

        # Session & Cycle Statistics
        self.total_trades: int = 0
        self.wins: int = 0
        self.losses: int = 0
        self.ties: int = 0
        self.session_pnl: float = 0.0
        self.cycles_won: int = 0
        self.cycles_lost: int = 0

    def reload_config(self):
        self.mode = getattr(config, "MM_MODE", "COMPOUND").upper()
        self.base_bet = config.BASE_BET
        self.compound_steps = getattr(config, "COMPOUND_STEPS", 2)
        self.martingale_steps = config.MARTINGALE_STEPS
        self.reinvest_ratio = getattr(config, "COMPOUND_REINVEST_RATIO", 1.0)
        self.max_steps = config.get_max_steps()
        self.ladder = config.get_ladder()
        if self.current_step == 1:
            self.current_bet = self.base_bet

    def get_current_bet(self) -> float:
        """Returns the bet amount for the active trade step."""
        if self.mode == "COMPOUND":
            return round(self.current_bet, 2)
        else:
            idx = max(0, min(self.current_step - 1, len(self.ladder) - 1))
            return self.ladder[idx]

    def record_result(self, result: str, stake: float, profit: float) -> Tuple[int, str]:
        """
        Updates statistics and calculates next bet & step according to active MM mode.
        result: 'WIN', 'LOSS', or 'EQUAL'
        Returns: (next_step: int, status_message: str)
        """
        self.total_trades += 1
        res = result.upper()

        if self.mode == "COMPOUND":
            return self._record_compound(res, stake, profit)
        else:
            return self._record_martingale(res, stake, profit)

    def _record_compound(self, res: str, stake: float, profit: float) -> Tuple[int, str]:
        """ทบกำไรแบบจำกัดขั้น (Compound / Masaniello-lite)"""
        if res == "WIN":
            self.wins += 1
            self.session_pnl += profit
            self.cycle_accumulated_profit += profit

            if self.current_step < self.max_steps:
                # Advance to next compound step (reinvest principal + profit)
                next_bet = round(stake + (profit * self.reinvest_ratio), 2)
                self.current_step += 1
                self.current_bet = next_bet
                msg = (
                    f"🏆 [Compound] WIN on Step {self.current_step - 1}! "
                    f"Compounding profit into Step {self.current_step}/{self.max_steps} (${next_bet:.2f})."
                )
                logger.info(f"[MoneyManager] {msg}")
                return self.current_step, msg
            else:
                # Completed target compound steps! Bank profit & reset cycle!
                self.cycles_won += 1
                cycle_profit = self.cycle_accumulated_profit
                self.current_step = 1
                self.current_bet = self.base_bet
                self.cycle_accumulated_profit = 0.0
                msg = (
                    f"🎉 [Compound / Masaniello-lite] Target {self.max_steps} Steps COMPLETED! "
                    f"Cycle Won (+${cycle_profit:.2f})! Resetting to Base Bet (${self.base_bet:.2f})."
                )
                logger.info(f"[MoneyManager] {msg}")
                return 1, msg

        elif res in ("LOSS", "LOOSE"):
            self.losses += 1
            self.session_pnl -= stake
            self.cycles_lost += 1
            old_step = self.current_step
            self.current_step = 1
            self.current_bet = self.base_bet
            self.cycle_accumulated_profit = 0.0
            msg = (
                f"❌ [Compound] Loss on Step {old_step}. "
                f"Capital Protected: Resetting cycle to Base Bet (${self.base_bet:.2f})."
            )
            logger.info(f"[MoneyManager] {msg}")
            return 1, msg

        else:  # EQUAL / TIE
            self.ties += 1
            msg = f"⚖️ [Compound] Tie/Equal on Step {self.current_step}. Repeating step with bet ${self.current_bet:.2f}."
            logger.info(f"[MoneyManager] {msg}")
            return self.current_step, msg

    def _record_martingale(self, res: str, stake: float, profit: float) -> Tuple[int, str]:
        """Traditional Martingale (ทบเมื่อแพ้)"""
        if res == "WIN":
            self.wins += 1
            self.session_pnl += profit
            old_step = self.current_step
            self.current_step = 1
            msg = f"Win! Reset Martingale from step {old_step} back to 1."
            logger.info(f"[MoneyManager] {msg}")
            return self.current_step, msg

        elif res in ("LOSS", "LOOSE"):
            self.losses += 1
            self.session_pnl -= stake
            if self.current_step >= self.max_steps:
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

        else:
            self.ties += 1
            msg = f"Tie/Equal. Repeating current step {self.current_step}."
            logger.info(f"[MoneyManager] {msg}")
            return self.current_step, msg

    def check_daily_limits(self) -> Tuple[bool, str]:
        if config.DAILY_STOP_LOSS > 0 and self.session_pnl <= -abs(config.DAILY_STOP_LOSS):
            return True, "STOP_LOSS"
        if config.DAILY_TAKE_PROFIT > 0 and self.session_pnl >= abs(config.DAILY_TAKE_PROFIT):
            return True, "TAKE_PROFIT"
        return False, "NONE"

    def get_summary(self) -> dict:
        total = self.total_trades
        win_rate = (self.wins / total * 100) if total > 0 else 0.0
        return {
            "mode": self.mode,
            "total_trades": total,
            "wins": self.wins,
            "losses": self.losses,
            "ties": self.ties,
            "win_rate": round(win_rate, 1),
            "session_pnl": round(self.session_pnl, 2),
            "current_step": self.current_step,
            "current_bet": self.get_current_bet(),
            "max_steps": self.max_steps,
            "ladder": self.ladder,
            "cycles_won": self.cycles_won,
            "cycles_lost": self.cycles_lost
        }

    def reset_session(self):
        self.current_step = 1
        self.current_bet = self.base_bet
        self.cycle_accumulated_profit = 0.0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.cycles_won = 0
        self.cycles_lost = 0
        self.session_pnl = 0.0

money_manager = MoneyManager()
