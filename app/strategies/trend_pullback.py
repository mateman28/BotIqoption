from typing import Optional, Tuple, Dict
import pandas as pd
from app.config import config
from app.strategies.base import BaseStrategy

class MultiTimeframeTrendPullback(BaseStrategy):
    """
    High Win-Rate Multi-Timeframe Trend + Pullback Strategy:
    1. 5-Minute (M5): EMA 50 Trend Filter (UP, DOWN, or NEUTRAL).
    2. 1-Minute (M1): Bollinger Bands (20, 2) + Fast RSI (7) Pullback confirmation.
    """
    def __init__(
        self,
        ema_period: int = None,
        bb_period: int = None,
        bb_std: float = None,
        rsi_period: int = None,
        rsi_oversold: float = None,
        rsi_overbought: float = None
    ):
        super().__init__(name="Multi-Timeframe Trend-Pullback")
        self._ema_period = ema_period
        self._bb_period = bb_period
        self._bb_std = bb_std
        self._rsi_period = rsi_period
        self._rsi_oversold = rsi_oversold
        self._rsi_overbought = rsi_overbought

    @property
    def ema_period(self) -> int:
        return self._ema_period or config.EMA_TREND_PERIOD

    @property
    def bb_period(self) -> int:
        return self._bb_period or config.BB_PERIOD

    @property
    def bb_std(self) -> float:
        return self._bb_std or config.BB_STD_DEV

    @property
    def rsi_period(self) -> int:
        return self._rsi_period or config.RSI_PERIOD

    @property
    def rsi_oversold(self) -> float:
        return self._rsi_oversold or config.RSI_OVERSOLD

    @property
    def rsi_overbought(self) -> float:
        return self._rsi_overbought or config.RSI_OVERBOUGHT

    @staticmethod
    def calculate_ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0):
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = sma + (std * num_std)
        lower = sma - (std * num_std)
        return upper, sma, lower

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 7) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def analyze(self, m1_df: pd.DataFrame, m5_df: Optional[pd.DataFrame] = None) -> Tuple[Optional[str], Dict]:
        if m1_df is None or len(m1_df) < max(self.bb_period, self.rsi_period) + 5:
            return None, {"reason": "Insufficient M1 candles"}

        # ----------------------------------------------------
        # 1. Macro Trend Filter (M5 EMA 50)
        # ----------------------------------------------------
        macro_trend = "NEUTRAL"
        m5_ema_val = 0.0
        m5_close_val = 0.0

        if m5_df is not None and len(m5_df) >= self.ema_period:
            m5_ema = self.calculate_ema(m5_df["close"], self.ema_period)
            m5_ema_val = float(m5_ema.iloc[-1])
            m5_close_val = float(m5_df["close"].iloc[-1])
            diff_pct = (m5_close_val - m5_ema_val) / m5_ema_val if m5_ema_val > 0 else 0
            if diff_pct > 0.0001:
                macro_trend = "UP"
            elif diff_pct < -0.0001:
                macro_trend = "DOWN"
            else:
                macro_trend = "NEUTRAL"
        else:
            # Fallback to M1 long-term EMA
            m1_ema100 = self.calculate_ema(m1_df["close"], 60)
            if len(m1_ema100) > 0:
                m5_ema_val = float(m1_ema100.iloc[-1])
                m5_close_val = float(m1_df["close"].iloc[-1])
                macro_trend = "UP" if m5_close_val > m5_ema_val else "DOWN"

        # ----------------------------------------------------
        # 2. Micro Entry Pullback (M1 BB + RSI)
        # ----------------------------------------------------
        close_series = m1_df["close"]
        low_series = m1_df["low"]
        high_series = m1_df["high"]

        upper_bb, mid_bb, lower_bb = self.calculate_bollinger_bands(close_series, self.bb_period, self.bb_std)
        rsi_series = self.calculate_rsi(close_series, self.rsi_period)

        current_close = float(close_series.iloc[-1])
        current_low = float(low_series.iloc[-1])
        current_high = float(high_series.iloc[-1])
        current_upper = float(upper_bb.iloc[-1])
        current_lower = float(lower_bb.iloc[-1])
        current_rsi = float(rsi_series.iloc[-1])
        prev_rsi = float(rsi_series.iloc[-2]) if len(rsi_series) > 1 else current_rsi

        info = {
            "strategy": self.name,
            "macro_trend": macro_trend,
            "m5_close": round(m5_close_val, 5),
            "m5_ema50": round(m5_ema_val, 5),
            "m1_close": round(current_close, 5),
            "bb_upper": round(current_upper, 5),
            "bb_lower": round(current_lower, 5),
            "rsi": round(current_rsi, 2),
            "prev_rsi": round(prev_rsi, 2),
            "rsi_period": self.rsi_period,
            "rsi_oversold": self.rsi_oversold,
            "rsi_overbought": self.rsi_overbought
        }

        # Dynamic sensitivity buffer (0.04% around BB boundary)
        bb_lower_threshold = current_lower * 1.0004
        bb_upper_threshold = current_upper * 0.9996

        is_near_lower = (current_low <= bb_lower_threshold or current_close <= bb_lower_threshold)
        is_near_upper = (current_high >= bb_upper_threshold or current_close >= bb_upper_threshold)
        is_rsi_oversold = (current_rsi <= self.rsi_oversold or (prev_rsi <= self.rsi_oversold and current_rsi > prev_rsi))
        is_rsi_overbought = (current_rsi >= self.rsi_overbought or (prev_rsi >= self.rsi_overbought and current_rsi < prev_rsi))

        # CALL Signal:
        # Case A: Uptrend Pullback (Macro UP + Low hits Lower BB + RSI Oversold)
        # Case B: Range Support Reversal (Macro NEUTRAL + Low hits Lower BB + RSI Oversold)
        if (macro_trend in ("UP", "NEUTRAL")) and is_near_lower and is_rsi_oversold:
            info["reason"] = f"{macro_trend} + Lower BB Touch + RSI Oversold ({current_rsi:.1f})"
            return "CALL", info

        # PUT Signal:
        # Case A: Downtrend Pullback (Macro DOWN + High hits Upper BB + RSI Overbought)
        # Case B: Range Resistance Reversal (Macro NEUTRAL + High hits Upper BB + RSI Overbought)
        if (macro_trend in ("DOWN", "NEUTRAL")) and is_near_upper and is_rsi_overbought:
            info["reason"] = f"{macro_trend} + Upper BB Touch + RSI Overbought ({current_rsi:.1f})"
            return "PUT", info

        info["reason"] = f"Waiting ({macro_trend} | RSI:{current_rsi:.1f} | BB Dist: {round(current_close - current_lower, 4)})"
        return None, info

trend_strategy = MultiTimeframeTrendPullback()
