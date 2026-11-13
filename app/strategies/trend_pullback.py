from typing import Optional, Tuple, Dict, List
import numpy as np
import pandas as pd
from app.config import config
from app.strategies.base import BaseStrategy

class MultiTimeframeTrendPullback(BaseStrategy):
    """
    High Win-Rate (>60%) Multi-Timeframe Price Action & Confluence Strategy:
    
    1. Market Condition Filter:
       - Trend Identification: EMA 20 & EMA 50 (Uptrend, Downtrend, or Sideway/Ranging).
       - Blacklist Filter: Skip Doji clusters (choppy) and extreme volatility spikes (news candles).
       
    2. Key Support & Resistance Zones:
       - Multi-Timeframe (M5) Pivot High/Low detection and clustering into major Key S/R Zones.
       - Dynamic S/R: M1 Bollinger Bands (20, 2) & EMA 20/50 pullbacks.
       
    3. Candlestick Confirmation & Price Rejection:
       - Rejection Wicks: Upper Wick (Bearish Rejection at Resistance) & Lower Wick (Bullish Rejection at Support).
       - Reversal Formations: Bullish/Bearish Engulfing, Pin Bars / Hammers.
       
    4. Indicator Confluence (Strict 4-Step Checklist):
       - EMA 20/50 trend alignment.
       - RSI (14) Overbought (>65-70) or Oversold (<30-35) with directional hook.
       - Safety rule: If any condition is missing, PASS and WAIT.
    """

    def __init__(
        self,
        ema_fast: int = 20,
        ema_slow: int = 50,
        bb_period: int = None,
        bb_std: float = None,
        rsi_period: int = None,
        rsi_oversold: float = None,
        rsi_overbought: float = None
    ):
        super().__init__(name="Multi-Timeframe Price Action & Confluence Strategy")
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self._bb_period = bb_period
        self._bb_std = bb_std
        self._rsi_period = rsi_period
        self._rsi_oversold = rsi_oversold
        self._rsi_overbought = rsi_overbought

    @property
    def bb_period(self) -> int:
        return self._bb_period or getattr(config, "BB_PERIOD", 20)

    @property
    def bb_std(self) -> float:
        return self._bb_std or getattr(config, "BB_STD_DEV", 2.0)

    @property
    def rsi_period(self) -> int:
        return self._rsi_period or getattr(config, "RSI_PERIOD", 14)

    @property
    def rsi_oversold(self) -> float:
        return self._rsi_oversold or getattr(config, "RSI_OVERSOLD", 30.0)

    @property
    def rsi_overbought(self) -> float:
        return self._rsi_overbought or getattr(config, "RSI_OVERBOUGHT", 70.0)

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
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    # ========================================================
    # 1. Market Condition Filter (Blacklist Doji & Spikes)
    # ========================================================
    def check_market_health(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Filters out choppy Doji clusters and extreme news spikes.
        Returns: (is_healthy: bool, reason: str)
        """
        if len(df) < 15:
            return False, "Insufficient candle history"

        # A. Check Doji cluster in the last 4 candles
        recent_candles = df.tail(4)
        doji_count = 0
        for _, row in recent_candles.iterrows():
            total_range = row["high"] - row["low"]
            body = abs(row["close"] - row["open"])
            if total_range > 0 and (body / total_range) < 0.20:
                doji_count += 1

        if doji_count >= 2:
            return False, "Market Filter: Doji Cluster detected (Choppy / Indecision market)"

        # B. Check for extreme spike / news candle (range > 2.8x Average Range)
        ranges = (df["high"] - df["low"]).tail(20)
        avg_range = ranges.mean()
        last_range = ranges.iloc[-1]
        prev_range = ranges.iloc[-2]

        if avg_range > 0 and (last_range > 3.0 * avg_range or prev_range > 3.0 * avg_range):
            return False, "Market Filter: Extreme news spike candle detected (High Volatility)"

        return True, "Healthy Market"

    # ========================================================
    # 2. Key Support & Resistance Level Detection (M5 Zones)
    # ========================================================
    def find_key_sr_levels(self, m5_df: pd.DataFrame, current_price: float) -> Dict[str, List[float]]:
        """
        Detects swing high and swing low pivot levels from M5 candles.
        Returns clustered major support and resistance zones near current price.
        """
        supports = []
        resistances = []

        if m5_df is None or len(m5_df) < 15:
            return {"supports": supports, "resistances": resistances}

        highs = m5_df["high"].values
        lows = m5_df["low"].values
        n = len(m5_df)

        for i in range(2, n - 2):
            # Pivot High (Resistance)
            if highs[i] >= highs[i-1] and highs[i] >= highs[i-2] and highs[i] >= highs[i+1] and highs[i] >= highs[i+2]:
                resistances.append(float(highs[i]))
            # Pivot Low (Support)
            if lows[i] <= lows[i-1] and lows[i] <= lows[i-2] and lows[i] <= lows[i+1] and lows[i] <= lows[i+2]:
                supports.append(float(lows[i]))

        # Filter levels close to current price (within 1.5%)
        filtered_supp = [s for s in supports if s <= current_price * 1.002 and s >= current_price * 0.985]
        filtered_res = [r for r in resistances if r >= current_price * 0.998 and r <= current_price * 1.015]

        return {"supports": filtered_supp, "resistances": filtered_res}

    # ========================================================
    # 3. Candlestick Confirmation & Price Rejection
    # ========================================================
    def analyze_candlestick_action(self, df: pd.DataFrame) -> Dict:
        """
        Reads price action: Rejection wicks (pin bars) and Engulfing patterns.
        """
        curr = df.iloc[-1]
        prev = df.iloc[-2]

        c_open, c_close, c_high, c_low = float(curr["open"]), float(curr["close"]), float(curr["high"]), float(curr["low"])
        p_open, p_close = float(prev["open"]), float(prev["close"])

        total_range = c_high - c_low
        body = abs(c_close - c_open)
        upper_wick = c_high - max(c_open, c_close)
        lower_wick = min(c_open, c_close) - c_low

        prev_body = abs(p_close - p_open)
        is_bullish = c_close > c_open
        is_bearish = c_close < c_open
        prev_is_bearish = p_close < p_open
        prev_is_bullish = p_close > p_open

        # A. Wick Rejection (Wick >= 35% of total candle & larger than body)
        lower_wick_ratio = lower_wick / total_range if total_range > 0 else 0
        upper_wick_ratio = upper_wick / total_range if total_range > 0 else 0

        bullish_rejection = lower_wick_ratio >= 0.35 and lower_wick >= (body * 0.8)
        bearish_rejection = upper_wick_ratio >= 0.35 and upper_wick >= (body * 0.8)

        # B. Engulfing Patterns
        bullish_engulfing = is_bullish and prev_is_bearish and (body > prev_body * 1.05) and (c_close >= p_open)
        bearish_engulfing = is_bearish and prev_is_bullish and (body > prev_body * 1.05) and (c_close <= p_open)

        # C. Pin Bar Formations
        bullish_pinbar = lower_wick_ratio >= 0.55 and upper_wick_ratio <= 0.20
        bearish_pinbar = upper_wick_ratio >= 0.55 and lower_wick_ratio <= 0.20

        return {
            "bullish_rejection": bullish_rejection,
            "bearish_rejection": bearish_rejection,
            "bullish_engulfing": bullish_engulfing,
            "bearish_engulfing": bearish_engulfing,
            "bullish_pinbar": bullish_pinbar,
            "bearish_pinbar": bearish_pinbar,
            "lower_wick_ratio": round(lower_wick_ratio, 2),
            "upper_wick_ratio": round(upper_wick_ratio, 2),
            "is_bullish_candle": is_bullish,
            "is_bearish_candle": is_bearish
        }

    # ========================================================
    # 4. Master Multi-Timeframe Analysis & Confluence Check
    # ========================================================
    def analyze(self, m1_df: pd.DataFrame, m5_df: Optional[pd.DataFrame] = None) -> Tuple[Optional[str], Dict]:
        min_candles = max(self.bb_period, self.rsi_period, self.ema_slow) + 5
        if m1_df is None or len(m1_df) < min_candles:
            return None, {"reason": "Insufficient M1 candles", "macro_trend": "NEUTRAL", "rsi": 50.0}

        # ----------------------------------------------------
        # Step 1: Market Condition & Health Check
        # ----------------------------------------------------
        is_healthy, health_msg = self.check_market_health(m1_df)
        if not is_healthy:
            return None, {
                "strategy": self.name,
                "reason": health_msg,
                "macro_trend": "CHOPPY_BLACKLIST",
                "rsi": 50.0
            }

        # ----------------------------------------------------
        # Step 2: Trend Determination (EMA 20 & EMA 50)
        # ----------------------------------------------------
        # Use M5 if available, otherwise M1 long timeframe
        trend_df = m5_df if (m5_df is not None and len(m5_df) >= self.ema_slow) else m1_df
        ema20_series = self.calculate_ema(trend_df["close"], self.ema_fast)
        ema50_series = self.calculate_ema(trend_df["close"], self.ema_slow)

        curr_ema20 = float(ema20_series.iloc[-1])
        curr_ema50 = float(ema50_series.iloc[-1])
        prev_ema20 = float(ema20_series.iloc[-2]) if len(ema20_series) > 1 else curr_ema20

        ema20_slope = curr_ema20 - prev_ema20
        trend_diff_pct = (curr_ema20 - curr_ema50) / curr_ema50 if curr_ema50 > 0 else 0

        if curr_ema20 > curr_ema50 and ema20_slope >= 0 and trend_diff_pct > 0.0002:
            macro_trend = "UP"
        elif curr_ema20 < curr_ema50 and ema20_slope <= 0 and trend_diff_pct < -0.0002:
            macro_trend = "DOWN"
        else:
            macro_trend = "NEUTRAL"  # Ranging / Sideway Market

        # ----------------------------------------------------
        # Step 3: Key Support / Resistance & Bollinger Bands
        # ----------------------------------------------------
        current_close = float(m1_df["close"].iloc[-1])
        current_low = float(m1_df["low"].iloc[-1])
        current_high = float(m1_df["high"].iloc[-1])

        upper_bb, mid_bb, lower_bb = self.calculate_bollinger_bands(m1_df["close"], self.bb_period, self.bb_std)
        curr_upper = float(upper_bb.iloc[-1])
        curr_lower = float(lower_bb.iloc[-1])
        curr_mid = float(mid_bb.iloc[-1])

        sr_levels = self.find_key_sr_levels(m5_df if m5_df is not None else m1_df, current_close)
        
        # S/R Proximity check (Buffer 0.08%)
        near_m5_support = any(abs(current_low - s) / s <= 0.0008 or (current_low <= s <= current_close) for s in sr_levels["supports"])
        near_m5_resistance = any(abs(current_high - r) / r <= 0.0008 or (current_close <= r <= current_high) for r in sr_levels["resistances"])

        # BB Boundaries
        bb_lower_threshold = curr_lower * 1.0005
        bb_upper_threshold = curr_upper * 0.9995
        near_lower_bb = current_low <= bb_lower_threshold or current_close <= bb_lower_threshold
        near_upper_bb = current_high >= bb_upper_threshold or current_close >= bb_upper_threshold

        # Pullback to EMA20 in trending market
        near_ema20_support = (macro_trend == "UP") and (current_low <= curr_mid * 1.0005 and current_close >= curr_mid * 0.9995)
        near_ema20_resistance = (macro_trend == "DOWN") and (current_high >= curr_mid * 0.9995 and current_close <= curr_mid * 1.0005)

        at_support_zone = near_lower_bb or near_m5_support or near_ema20_support
        at_resistance_zone = near_upper_bb or near_m5_resistance or near_ema20_resistance

        # ----------------------------------------------------
        # Step 4: Candlestick Confirmation
        # ----------------------------------------------------
        pa = self.analyze_candlestick_action(m1_df)
        bullish_pa = pa["bullish_rejection"] or pa["bullish_engulfing"] or pa["bullish_pinbar"]
        bearish_pa = pa["bearish_rejection"] or pa["bearish_engulfing"] or pa["bearish_pinbar"]

        # ----------------------------------------------------
        # Step 5: RSI Confluence & Directional Hook
        # ----------------------------------------------------
        rsi_series = self.calculate_rsi(m1_df["close"], self.rsi_period)
        curr_rsi = float(rsi_series.iloc[-1])
        prev_rsi = float(rsi_series.iloc[-2]) if len(rsi_series) > 1 else curr_rsi

        # RSI Oversold with upward hook
        rsi_oversold_hook = (curr_rsi <= (self.rsi_oversold + 5.0)) and (curr_rsi >= prev_rsi)
        # RSI Overbought with downward hook
        rsi_overbought_hook = (curr_rsi >= (self.rsi_overbought - 5.0)) and (curr_rsi <= prev_rsi)

        # Build analysis diagnostic info
        info = {
            "strategy": self.name,
            "macro_trend": macro_trend,
            "m1_close": round(current_close, 5),
            "bb_upper": round(curr_upper, 5),
            "bb_lower": round(curr_lower, 5),
            "bb_mid": round(curr_mid, 5),
            "rsi": round(curr_rsi, 2),
            "prev_rsi": round(prev_rsi, 2),
            "at_support": at_support_zone,
            "at_resistance": at_resistance_zone,
            "bullish_pa": bullish_pa,
            "bearish_pa": bearish_pa,
            "lower_wick": pa["lower_wick_ratio"],
            "upper_wick": pa["upper_wick_ratio"],
            "supports_found": len(sr_levels["supports"]),
            "resistances_found": len(sr_levels["resistances"])
        }

        # ----------------------------------------------------
        # Step 6: 4-Step Confluence Decision Engine
        # ----------------------------------------------------
        # CALL Signal Requirements:
        # 1. Market is healthy (checked)
        # 2. Trend is UP (pullback) OR NEUTRAL (sideway support bounce)
        # 3. Price is at Support Zone (M5 Support / Lower BB / EMA20 pullback)
        # 4. Candlestick confirms Bullish Rejection / Engulfing / Pinbar
        # 5. RSI is Oversold and hooking up
        if macro_trend in ("UP", "NEUTRAL") and at_support_zone and bullish_pa and rsi_oversold_hook:
            pa_name = "Bullish Pinbar" if pa["bullish_pinbar"] else ("Bullish Engulfing" if pa["bullish_engulfing"] else f"Lower Wick Rejection ({pa['lower_wick_ratio']:.0%})")
            info["reason"] = f"High-WinRate CALL: {macro_trend} + Support Zone + {pa_name} + RSI Oversold Hook ({curr_rsi:.1f})"
            return "CALL", info

        # PUT Signal Requirements:
        # 1. Market is healthy (checked)
        # 2. Trend is DOWN (pullback) OR NEUTRAL (sideway resistance rejection)
        # 3. Price is at Resistance Zone (M5 Resistance / Upper BB / EMA20 pullback)
        # 4. Candlestick confirms Bearish Rejection / Engulfing / Pinbar
        # 5. RSI is Overbought and hooking down
        if macro_trend in ("DOWN", "NEUTRAL") and at_resistance_zone and bearish_pa and rsi_overbought_hook:
            pa_name = "Bearish Pinbar" if pa["bearish_pinbar"] else ("Bearish Engulfing" if pa["bearish_engulfing"] else f"Upper Wick Rejection ({pa['upper_wick_ratio']:.0%})")
            info["reason"] = f"High-WinRate PUT: {macro_trend} + Resistance Zone + {pa_name} + RSI Overbought Hook ({curr_rsi:.1f})"
            return "PUT", info

        # Rule: If any of the 4 steps are not 100% satisfied -> PASS & WAIT
        wait_reasons = []
        if not at_support_zone and not at_resistance_zone:
            wait_reasons.append("Price between zones")
        if not bullish_pa and not bearish_pa:
            wait_reasons.append("No Price Action confirmation")
        if not rsi_oversold_hook and not rsi_overbought_hook:
            wait_reasons.append(f"RSI neutral ({curr_rsi:.1f})")

        reason_str = ", ".join(wait_reasons) if wait_reasons else "Awaiting complete 4-step confluence"
        info["reason"] = f"Waiting ({macro_trend} | {reason_str})"
        return None, info

trend_strategy = MultiTimeframeTrendPullback()
