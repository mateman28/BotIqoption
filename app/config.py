import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

class Config:
    # IQ Option Credentials
    IQ_EMAIL: str = os.getenv("IQ_EMAIL", "")
    IQ_PASSWORD: str = os.getenv("IQ_PASSWORD", "")
    
    # Account Mode: 'PRACTICE' (Demo) or 'REAL'
    # For safety, default is always PRACTICE
    ACCOUNT_MODE: str = os.getenv("ACCOUNT_MODE", "PRACTICE").upper()
    
    # Payout filter (Default 88% = 0.88)
    MIN_PAYOUT: float = float(os.getenv("MIN_PAYOUT", "88")) / 100.0 if float(os.getenv("MIN_PAYOUT", "88")) > 1 else float(os.getenv("MIN_PAYOUT", "0.88"))
    
    # Top N pairs to monitor & trade (Default: Top 5)
    TOP_PAIRS_COUNT: int = int(os.getenv("TOP_PAIRS_COUNT", "5"))
    
    # Money Management / Martingale Settings
    BASE_BET: float = float(os.getenv("BASE_BET", "1.0"))
    MARTINGALE_STEPS: int = int(os.getenv("MARTINGALE_STEPS", "5"))
    # Pre-calculated 5-step bet amounts or multiplier
    MARTINGALE_MULTIPLIER: float = float(os.getenv("MARTINGALE_MULTIPLIER", "2.2"))
    # Custom custom step amounts if provided, e.g. "1.0,2.2,5.0,11.0,25.0"
    CUSTOM_STEPS_STR: str = os.getenv("CUSTOM_STEPS", "1.0,2.2,5.0,11.0,25.0")
    
    # Risk Management Limits (in USD)
    DAILY_STOP_LOSS: float = float(os.getenv("DAILY_STOP_LOSS", "50.0"))  # Max loss before stopping
    DAILY_TAKE_PROFIT: float = float(os.getenv("DAILY_TAKE_PROFIT", "30.0"))  # Target profit
    
    # Strategy Settings (Configured for 5M Options)
    EXPIRY_MINUTES: int = int(os.getenv("EXPIRY_MINUTES", "5"))  # 5 min expiration
    EMA_TREND_PERIOD: int = int(os.getenv("EMA_TREND_PERIOD", "50"))
    BB_PERIOD: int = int(os.getenv("BB_PERIOD", "20"))
    BB_STD_DEV: float = float(os.getenv("BB_STD_DEV", "2.0"))
    RSI_PERIOD: int = int(os.getenv("RSI_PERIOD", "7"))  # Fast RSI 7 for responsive signals
    RSI_OVERSOLD: float = float(os.getenv("RSI_OVERSOLD", "35.0"))
    RSI_OVERBOUGHT: float = float(os.getenv("RSI_OVERBOUGHT", "65.0"))
    
    # Telegram Notifications
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    TELEGRAM_ENABLED: bool = os.getenv("TELEGRAM_ENABLED", "true").lower() in ("true", "1", "yes")

    # Web Dashboard Settings
    WEB_HOST: str = os.getenv("WEB_HOST", "127.0.0.1")
    WEB_PORT: int = int(os.getenv("WEB_PORT", "8000"))

    def get_martingale_ladder(self) -> list[float]:
        """
        Returns the list of bet amounts for each step.
        If CUSTOM_STEPS matches the active BASE_BET, uses custom steps.
        Otherwise, dynamically generates the ladder from BASE_BET using MARTINGALE_MULTIPLIER.
        """
        try:
            steps = [float(x.strip()) for x in self.CUSTOM_STEPS_STR.split(",") if x.strip()]
            if steps and abs(steps[0] - self.BASE_BET) < 1e-4:
                if len(steps) >= self.MARTINGALE_STEPS:
                    return steps[:self.MARTINGALE_STEPS]
                ladder = list(steps)
                curr = ladder[-1]
                for _ in range(len(steps), self.MARTINGALE_STEPS):
                    curr = round(curr * self.MARTINGALE_MULTIPLIER, 2)
                    ladder.append(curr)
                return ladder
        except Exception:
            pass
        
        # Dynamically generate ladder based on BASE_BET and MARTINGALE_MULTIPLIER
        ladder = [self.BASE_BET]
        current = self.BASE_BET
        for _ in range(1, self.MARTINGALE_STEPS):
            current = round(current * self.MARTINGALE_MULTIPLIER, 2)
            ladder.append(current)
        return ladder

    @classmethod
    def save_setting(cls, key: str, value: str):
        """Persist a configuration setting into the .env file."""
        try:
            from dotenv import set_key
            set_key(str(ENV_PATH), key, str(value))
        except Exception:
            pass

config = Config()
