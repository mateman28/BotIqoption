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
        self.assertEqual(len(ladder), config.MARTINGALE_STEPS)
        self.assertEqual(ladder[0], config.BASE_BET)
        self.assertTrue(ladder[-1] > ladder[0])

    def test_02_money_manager_martingale_and_cutloss(self):
        mm = MoneyManager()
        mm.mode = "MARTINGALE"
        mm.max_steps = 5
        mm.ladder = config.get_martingale_ladder()
        self.assertEqual(mm.current_step, 1)
        self.assertEqual(mm.get_current_bet(), mm.ladder[0])

        # Loss 1
        step, _ = mm.record_result("LOSS", mm.ladder[0], 0.0)
        self.assertEqual(step, 2)
        self.assertEqual(mm.get_current_bet(), mm.ladder[1])

        # Loss 2
        step, _ = mm.record_result("LOSS", mm.ladder[1], 0.0)
        self.assertEqual(step, 3)
        self.assertEqual(mm.get_current_bet(), mm.ladder[2])

        # Loss 3
        step, _ = mm.record_result("LOSS", mm.ladder[2], 0.0)
        self.assertEqual(step, 4)
        self.assertEqual(mm.get_current_bet(), mm.ladder[3])

        # Loss 4
        step, _ = mm.record_result("LOSS", mm.ladder[3], 0.0)
        self.assertEqual(step, 5)
        self.assertEqual(mm.get_current_bet(), mm.ladder[4])

        # Loss 5 -> Must trigger Cut-Loss and reset to step 1
        step, msg = mm.record_result("LOSS", mm.ladder[4], 0.0)
        self.assertEqual(step, 1)
        self.assertIn("Safety Cut-Loss", msg)
        self.assertEqual(mm.get_current_bet(), mm.ladder[0])

        # Win on step 1 -> Keeps step 1
        step, msg = mm.record_result("WIN", mm.ladder[0], mm.ladder[0] * 0.85)
        self.assertEqual(step, 1)

    def test_02b_money_manager_compound_masaniello(self):
        """Test Compound / Masaniello-lite (ทบกำไรแบบจำกัดขั้น)."""
        mm = MoneyManager()
        mm.mode = "COMPOUND"
        mm.max_steps = 2
        mm.base_bet = 2.0
        mm.current_bet = 2.0
        mm.current_step = 1

        # Win 1: Compound profit
        step, msg = mm.record_result("WIN", 2.0, 1.76)
        self.assertEqual(step, 2)
        self.assertEqual(mm.get_current_bet(), 3.76)
        self.assertIn("Compounding profit", msg)

        # Win 2: Completed 2-step compound target! Cycle Won & reset to base bet
        step, msg = mm.record_result("WIN", 3.76, 3.31)
        self.assertEqual(step, 1)
        self.assertEqual(mm.get_current_bet(), 2.0)
        self.assertIn("COMPLETED", msg)
        self.assertEqual(mm.cycles_won, 1)

        # Test Loss in Compound: Immediate reset to step 1 without increasing risk
        step, _ = mm.record_result("WIN", 2.0, 1.76)
        self.assertEqual(step, 2)
        step, msg = mm.record_result("LOSS", 3.76, 0.0)
        self.assertEqual(step, 1)
        self.assertEqual(mm.get_current_bet(), 2.0)
        self.assertIn("Capital Protected", msg)

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
