import time
from typing import Optional, Tuple
from iqoptionapi.stable_api import IQ_Option
import iqoptionapi.constants as OP_code
from app.config import config
from app.utils.logger import logger

class IQClient:
    def __init__(self):
        self.api: Optional[IQ_Option] = None
        self.is_connected: bool = False
        self.two_factor_required: bool = False
        self.current_mode: str = config.ACCOUNT_MODE

    def connect(self, email: str = None, password: str = None) -> Tuple[bool, str]:
        email = email or config.IQ_EMAIL
        password = password or config.IQ_PASSWORD

        if not email or not password:
            msg = "IQ Option email or password is missing in .env"
            logger.warning(f"[Client] {msg}")
            return False, msg

        try:
            logger.info(f"[Client] Connecting to IQ Option as {email}...")
            self.api = IQ_Option(email, password)
            check, reason = self.api.connect()

            if check:
                self.is_connected = True
                self.two_factor_required = False
                logger.info("[Client] Successfully connected to IQ Option WebSocket!")
                
                # Switch to desired mode (Default: PRACTICE)
                self.set_mode(self.current_mode)
                balance = self.get_balance()
                logger.info(f"[Client] Account Mode: {self.current_mode} | Balance: ${balance:,.2f}")
                
                # Dynamically sync all active symbols from IQ Option server
                self.sync_active_codes()
                return True, "Connected successfully"
            else:
                if reason == "2FA":
                    self.two_factor_required = True
                    logger.warning("[Client] 2-Factor Authentication (2FA) is required.")
                    return False, "2FA Required"
                else:
                    logger.error(f"[Client] Connection failed. Reason: {reason}")
                    return False, str(reason)
        except Exception as e:
            logger.error(f"[Client] Exception during connection: {e}")
            return False, str(e)

    def sync_active_codes(self):
        """
        Dynamically registers all active instruments from IQ Option server into OP_code.ACTIVES.
        Prevents KeyError and 'get_candles need reconnect' infinite loop.
        """
        if not self.api or not self.is_connected:
            return
        try:
            init_v2 = self.api.get_all_init_v2() or {}
            count_new = 0
            for category in ("turbo", "binary"):
                actives = init_v2.get(category, {}).get("actives", {})
                for act_id, act in actives.items():
                    raw_name = str(act.get("name", ""))
                    name = raw_name.replace("front.", "").strip()
                    if name:
                        OP_code.ACTIVES[name] = int(act_id)
                        count_new += 1
            logger.info(f"[Client] Synced {count_new} active instruments. Total OP_code.ACTIVES: {len(OP_code.ACTIVES)}")
        except Exception as e:
            logger.warning(f"[Client] Warning during active codes sync: {e}")

    def submit_2fa(self, code: str) -> Tuple[bool, str]:
        """Submit 2FA verification code if required."""
        if not self.api:
            return False, "API not initialized"
        try:
            logger.info(f"[Client] Submitting 2FA code...")
            res = self.api.connect_2fa(code)
            if res:
                self.is_connected = True
                self.two_factor_required = False
                self.set_mode(self.current_mode)
                self.sync_active_codes()
                return True, "2FA Verified successfully"
            return False, "Invalid 2FA code"
        except Exception as e:
            return False, str(e)

    def check_connection(self) -> bool:
        if not self.api:
            return False
        try:
            if not self.api.check_connect():
                logger.warning("[Client] Connection lost. Attempting auto-reconnect...")
                check, _ = self.api.connect()
                self.is_connected = check
                if check:
                    self.sync_active_codes()
                return check
            return True
        except Exception as e:
            logger.error(f"[Client] Error checking connection: {e}")
            self.is_connected = False
            return False

    def set_mode(self, mode: str):
        """Switch account balance between 'PRACTICE' and 'REAL'."""
        mode = mode.upper()
        if mode not in ("PRACTICE", "REAL"):
            mode = "PRACTICE"
        self.current_mode = mode
        if self.api and self.is_connected:
            self.api.change_balance(mode)
            logger.info(f"[Client] Switched balance mode to: {mode}")

    def get_balance(self) -> float:
        if not self.api or not self.is_connected:
            return 0.0
        try:
            return float(self.api.get_balance())
        except Exception as e:
            logger.error(f"[Client] Error getting balance: {e}")
            return 0.0

    def get_profile(self) -> dict:
        if not self.api or not self.is_connected:
            return {}
        try:
            return self.api.get_profile() or {}
        except Exception:
            return {}

iq_client = IQClient()
