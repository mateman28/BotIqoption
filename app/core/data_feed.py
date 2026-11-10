import time
from typing import Optional
import numpy as np
import pandas as pd
import iqoptionapi.constants as OP_code
from app.core.client import iq_client
from app.utils.logger import logger

class DataFeed:
    @staticmethod
    def get_candles(asset: str, timeframe_sec: int = 60, count: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetches candles from IQ Option API.
        timeframe_sec: 60 for 1M, 300 for 5M
        """
        if not iq_client.is_connected or not iq_client.api:
            # Generate synthetic candles for offline / local testing
            return DataFeed._generate_mock_candles(count, timeframe_sec)

        # Safety check: Ensure asset is registered in OP_code.ACTIVES
        if asset not in OP_code.ACTIVES:
            iq_client.sync_active_codes()
            if asset not in OP_code.ACTIVES:
                logger.warning(f"[DataFeed] Asset '{asset}' not found in OP_code.ACTIVES. Skipping to prevent reconnect loop.")
                return None

        try:
            end_time = int(time.time())
            raw_candles = iq_client.api.get_candles(asset, timeframe_sec, count, end_time)
            if not raw_candles:
                logger.warning(f"[DataFeed] No candle data received for {asset}")
                return None

            df = pd.DataFrame(raw_candles)
            # Standardize column names
            rename_map = {"min": "low", "max": "high"}
            df = df.rename(columns=rename_map)

            # Ensure numeric types
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.sort_values(by="from").reset_index(drop=True)
            return df
        except Exception as e:
            logger.error(f"[DataFeed] Error fetching candles for {asset}: {e}")
            return None

    @staticmethod
    def _generate_mock_candles(count: int = 100, interval: int = 60) -> pd.DataFrame:
        """Generates realistic synthetic OHLCV candles for testing without live connection."""
        now = int(time.time())
        timestamps = [now - (count - i) * interval for i in range(count)]
        
        # Random walk around 1.0850 (EURUSD level)
        np.random.seed(42)
        returns = np.random.normal(loc=0.00002, scale=0.0003, size=count)
        prices = 1.0850 * np.cumprod(1 + returns)
        
        data = []
        for i in range(count):
            close_p = prices[i]
            spread = abs(np.random.normal(0, 0.00015))
            high_p = close_p + spread
            low_p = close_p - spread
            open_p = prices[i - 1] if i > 0 else close_p
            data.append({
                "from": timestamps[i],
                "open": round(open_p, 5),
                "high": round(high_p, 5),
                "low": round(low_p, 5),
                "close": round(close_p, 5),
                "volume": int(np.random.uniform(50, 500))
            })
        return pd.DataFrame(data)

data_feed = DataFeed()
