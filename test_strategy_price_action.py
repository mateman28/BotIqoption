import unittest
import pandas as pd
import numpy as np
from app.strategies.trend_pullback import MultiTimeframeTrendPullback

class TestPriceActionConfluenceStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = MultiTimeframeTrendPullback(
            ema_fast=20,
            ema_slow=50,
            bb_period=20,
            bb_std=2.0,
            rsi_period=14,
            rsi_oversold=30.0,
            rsi_overbought=70.0
        )

    def _create_synthetic_candles(self, n=60, base_price=1.1000, trend="FLAT") -> pd.DataFrame:
        data = []
        p = base_price
        for i in range(n):
            if trend == "UP":
                p += 0.0003
            elif trend == "DOWN":
                p -= 0.0003
            else:
                p += 0.00005 * (1 if i % 2 == 0 else -1)
            
            o = p
            c = p + 0.0001
            h = max(o, c) + 0.0002
            l = min(o, c) - 0.0002
            data.append({"open": o, "high": h, "low": l, "close": c, "volume": 100})
        return pd.DataFrame(data)

    def test_01_market_condition_filter_doji_cluster(self):
        """Step 1: Test Doji cluster blacklist."""
        df = self._create_synthetic_candles(n=60)
        # Force the last 3 candles to be Doji (tiny body, wide wicks)
        for i in [-1, -2, -3]:
            df.at[df.index[i], "open"] = 1.1000
            df.at[df.index[i], "close"] = 1.10001
            df.at[df.index[i], "high"] = 1.1010
            df.at[df.index[i], "low"] = 1.0990

        is_healthy, reason = self.strategy.check_market_health(df)
        self.assertFalse(is_healthy)
        self.assertIn("Doji Cluster", reason)

        signal, info = self.strategy.analyze(df)
        self.assertIsNone(signal)
        self.assertEqual(info.get("macro_trend"), "CHOPPY_BLACKLIST")

    def test_02_market_condition_filter_news_spike(self):
        """Step 1: Test news spike volatility blacklist."""
        df = self._create_synthetic_candles(n=60)
        # Normal average range is ~0.0004
        # Inject an extreme spike candle (e.g. 0.0040 = 10x normal)
        df.at[df.index[-1], "open"] = 1.1000
        df.at[df.index[-1], "close"] = 1.1040
        df.at[df.index[-1], "high"] = 1.1045
        df.at[df.index[-1], "low"] = 1.0995

        is_healthy, reason = self.strategy.check_market_health(df)
        self.assertFalse(is_healthy)
        self.assertIn("Extreme news spike", reason)

    def test_03_key_sr_levels_detection(self):
        """Step 2: Test Pivot High and Pivot Low detection on M5."""
        df = self._create_synthetic_candles(n=40)
        # Create a swing high at index 15 and swing low at index 25
        df.at[df.index[15], "high"] = 1.1200
        df.at[df.index[25], "low"] = 1.0800

        sr = self.strategy.find_key_sr_levels(df, current_price=1.1000)
        self.assertIn("supports", sr)
        self.assertIn("resistances", sr)

    def test_04_candlestick_rejection_wicks(self):
        """Step 3: Test Upper Wick and Lower Wick price rejection detection."""
        df = self._create_synthetic_candles(n=10)
        
        # Upper wick rejection (Bearish Pinbar at resistance)
        df.at[df.index[-1], "open"] = 1.1000
        df.at[df.index[-1], "close"] = 1.0995
        df.at[df.index[-1], "high"] = 1.1030  # Long upper wick
        df.at[df.index[-1], "low"] = 1.0994
        
        pa = self.strategy.analyze_candlestick_action(df)
        self.assertTrue(pa["bearish_rejection"])
        self.assertTrue(pa["upper_wick_ratio"] >= 0.40)

        # Lower wick rejection (Bullish Pinbar at support)
        df.at[df.index[-1], "open"] = 1.1000
        df.at[df.index[-1], "close"] = 1.1005
        df.at[df.index[-1], "high"] = 1.1006
        df.at[df.index[-1], "low"] = 1.0970  # Long lower wick
        
        pa_bull = self.strategy.analyze_candlestick_action(df)
        self.assertTrue(pa_bull["bullish_rejection"])
        self.assertTrue(pa_bull["lower_wick_ratio"] >= 0.40)

    def test_05_strict_checklist_pass_when_uncertain(self):
        """Step 5: When not 100% confluence, bot must PASS & WAIT."""
        df_m1 = self._create_synthetic_candles(n=60, trend="FLAT")
        df_m5 = self._create_synthetic_candles(n=60, trend="FLAT")
        
        signal, info = self.strategy.analyze(df_m1, df_m5)
        self.assertIsNone(signal)
        self.assertIn("Waiting", info.get("reason", ""))

if __name__ == "__main__":
    unittest.main()
