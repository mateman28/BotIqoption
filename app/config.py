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
    
    # Strategy Settings (Optimized for 1M Binary Options)
    EXPIRY_MINUTES: int = int(os.getenv("EXPIRY_MINUTES", "1"))  # 1 or 5
    EMA_TREND_PERIOD: int = int(os.getenv("EMA_TREND_PERIOD", "50"))
    BB_PERIOD: int = int(os.getenv("BB_PERIOD", "20"))
    BB_STD_DEV: float = float(os.getenv("BB_STD_DEV", "2.0"))
    RSI_PERIOD: int = int(os.getenv("RSI_PERIOD", "7"))
    RSI_OVERSOLD: float = float(os.getenv("RSI_OVERSOLD", "35.0"))
    RSI_OVERBOUGHT: float = float(os.getenv("RSI_OVERBOUGHT", "65.0"))
    
    # Telegram Notifications
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    TELEGRAM_ENABLED: bool = os.getenv("TELEGRAM_ENABLED", "true").lower() in ("true", "1", "yes")

    # Web Dashboard Settings
    WEB_HOST: str = os.getenv("WEB_HOST", "127.0.0.1")
    WEB_PORT: int = int(os.getenv("WEB_PORT", "8000"))

    @classmethod
    def get_martingale_ladder(cls) -> list[float]:
        """Returns the list of bet amounts for each step, auto-expanding if steps exceed defined custom values."""
        try:
            steps = [float(x.strip()) for x in cls.CUSTOM_STEPS_STR.split(",") if x.strip()]
            if len(steps) >= cls.MARTINGALE_STEPS:
                return steps[:cls.MARTINGALE_STEPS]
            elif len(steps) > 0:
                # Expand ladder using multiplier from the last defined custom step
                ladder = list(steps)
                curr = ladder[-1]
                for _ in range(len(steps), cls.MARTINGALE_STEPS):
                    curr = round(curr * cls.MARTINGALE_MULTIPLIER, 2)
                    ladder.append(curr)
                return ladder
        except Exception:
            pass
        
        # Fallback to calculated multiplier
        ladder = [cls.BASE_BET]
        current = cls.BASE_BET
        for _ in range(1, cls.MARTINGALE_STEPS):
            current = round(current * cls.MARTINGALE_MULTIPLIER, 2)
            ladder.append(current)
        return ladder

config = Config()
