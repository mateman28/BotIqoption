import sys
import unittest
import pandas as pd
import numpy as np

from app.config import config
from app.risk.money_manager import MoneyManager
from app.core.scanner import AssetScanner
from app.core.data_feed import DataFeed
from app.strategies.trend_pullback import MultiTimeframeTrendPullback
from app.utils.telegram_bot import TelegramNotifier

class TestIQOptionBot(unittest.TestCase):
    def test_01_config_and_martingale_ladder(self):
        ladder = config.get_martingale_ladder()
        print(f"[TEST 1] Martingale Ladder: {ladder}")
        self.assertEqual(len(ladder), 5)
        self.assertEqual(ladder[0], 1.0)
        self.assertEqual(ladder[-1], 25.0)

    def test_02_money_manager_martingale_and_cutloss(self):
        mm = MoneyManager()
        self.assertEqual(mm.current_step, 1)
        self.assertEqual(mm.get_current_bet(), 1.0)

        # Loss 1
        step, _ = mm.record_result("LOSS", 1.0, 0.0)
        self.assertEqual(step, 2)
        self.assertEqual(mm.get_current_bet(), 2.2)

        # Loss 2
        step, _ = mm.record_result("LOSS", 2.2, 0.0)
        self.assertEqual(step, 3)
        self.assertEqual(mm.get_current_bet(), 5.0)

        # Loss 3
        step, _ = mm.record_result("LOSS", 5.0, 0.0)
        self.assertEqual(step, 4)
        self.assertEqual(mm.get_current_bet(), 11.0)

        # Loss 4
        step, _ = mm.record_result("LOSS", 11.0, 0.0)
        self.assertEqual(step, 5)
        self.assertEqual(mm.get_current_bet(), 25.0)

        # Loss 5 -> Must trigger Cut-Loss and reset to step 1
        step, msg = mm.record_result("LOSS", 25.0, 0.0)
        self.assertEqual(step, 1)
        self.assertIn("Safety Cut-Loss", msg)
        self.assertEqual(mm.get_current_bet(), 1.0)

        # Win on step 1 -> Keeps step 1
        step, msg = mm.record_result("WIN", 1.0, 0.85)
        self.assertEqual(step, 1)

    def test_03_scanner_high_payout_filter(self):
        sc = AssetScanner(min_payout=0.88)
        pairs = sc.get_top_pairs(limit=5)
        print(f"[TEST 3] Found Top {len(pairs)} Pairs with Payout >= 88%: {[p['pair'] for p in pairs]}")
        self.assertLessEqual(len(pairs), 5)
        for p in pairs:
            self.assertGreaterEqual(p["payout"], 0.88)

    def test_04_strategy_calculations(self):
        strategy = MultiTimeframeTrendPullback()
        m1_df = DataFeed._generate_mock_candles(count=80, interval=60)
        m5_df = DataFeed._generate_mock_candles(count=80, interval=300)

        self.assertIsNotNone(m1_df)
        self.assertEqual(len(m1_df), 80)
        
        signal, info = strategy.analyze(m1_df, m5_df)
        print(f"[TEST 4] Strategy Info: Trend={info.get('macro_trend')} | RSI={info.get('rsi')} | Signal={signal}")
        self.assertIn("macro_trend", info)
        self.assertIn("rsi", info)
        self.assertIn(signal, ("CALL", "PUT", None))

    def test_05_telegram_graceful_handling(self):
        # Even with empty token, should not raise an error or crash
        tg = TelegramNotifier(token="", chat_id="", enabled=False)
        self.assertFalse(tg.is_configured())
        tg.send_async("Test message")

if __name__ == "__main__":
    unittest.main()
