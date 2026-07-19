"""
Market Structure / HTF Trend Filter
-----------------------------------
Determines higher-timeframe (4H) trend bias using swing structure
(Higher-High/Higher-Low or Lower-High/Lower-Low), EMA alignment and ADX.

Bullish:
    Higher High AND Higher Low
    EMA_FAST > EMA_SLOW
    ADX > adx_threshold

Bearish:
    Lower High AND Lower Low
    EMA_FAST < EMA_SLOW
    ADX > adx_threshold

Output is a numeric score in [-1, 1] (not just a binary flag) so it can be
fed into both the rule-based strategy and an ML feature set.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class TrendState(Enum):
    BULLISH = 1
    BEARISH = -1
    NEUTRAL = 0


@dataclass
class MarketStructureConfig:
    ema_fast: int = 50
    ema_slow: int = 200
    adx_period: int = 14
    adx_threshold: float = 20.0
    swing_lookback: int = 5  # bars on each side to confirm a swing pivot


class MarketStructureIndicator:
    """
    Computes HTF trend state + a continuous trend "strength" feature.

    Usage:
        ms = MarketStructureIndicator(MarketStructureConfig())
        df = ms.compute(df_4h)
        # df now has columns: ema_fast, ema_slow, adx, swing_high, swing_low,
        # trend_state (Enum), trend_score (float in [-1, 1])
    """

    def __init__(self, config: MarketStructureConfig = MarketStructureConfig()):
        self.config = config

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        df must contain columns: ['open', 'high', 'low', 'close']
        Returns a copy of df with indicator columns appended.
        """
        out = df.copy()
        out["ema_fast"] = out["close"].ewm(span=self.config.ema_fast, adjust=False).mean()
        out["ema_slow"] = out["close"].ewm(span=self.config.ema_slow, adjust=False).mean()
        out["adx"] = self._adx(out, self.config.adx_period)

        swing_high, swing_low = self._swings(out, self.config.swing_lookback)
        out["swing_high"] = swing_high
        out["swing_low"] = swing_low

        out["hh_hl"] = self._is_higher_high_higher_low(out)
        out["lh_ll"] = self._is_lower_high_lower_low(out)

        out["trend_state"] = out.apply(self._classify_row, axis=1)
        out["trend_score"] = self._trend_score(out)
        return out

    def latest(self, df: pd.DataFrame) -> tuple[TrendState, float]:
        """Convenience: compute and return the most recent (state, score)."""
        computed = self.compute(df)
        last = computed.iloc[-1]
        return last["trend_state"], last["trend_score"]

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _adx(df: pd.DataFrame, period: int) -> pd.Series:
        high, low, close = df["high"], df["low"], df["close"]

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr1 = (high - low).abs()
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1 / period, adjust=False).mean()
        plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr
        minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr

        dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
        adx = dx.ewm(alpha=1 / period, adjust=False).mean()
        return adx.fillna(0)

    @staticmethod
    def _swings(df: pd.DataFrame, lookback: int) -> tuple[pd.Series, pd.Series]:
        """Identify pivot highs/lows using a centered rolling window."""
        window = 2 * lookback + 1
        swing_high = df["high"].where(
            df["high"] == df["high"].rolling(window, center=True).max()
        )
        swing_low = df["low"].where(
            df["low"] == df["low"].rolling(window, center=True).min()
        )
        return swing_high.ffill(), swing_low.ffill()

    @staticmethod
    def _is_higher_high_higher_low(df: pd.DataFrame) -> pd.Series:
        hh = df["swing_high"] > df["swing_high"].shift(1)
        hl = df["swing_low"] > df["swing_low"].shift(1)
        return hh & hl

    @staticmethod
    def _is_lower_high_lower_low(df: pd.DataFrame) -> pd.Series:
        lh = df["swing_high"] < df["swing_high"].shift(1)
        ll = df["swing_low"] < df["swing_low"].shift(1)
        return lh & ll

    def _classify_row(self, row) -> TrendState:
        adx_ok = row["adx"] > self.config.adx_threshold
        if row["hh_hl"] and row["ema_fast"] > row["ema_slow"] and adx_ok:
            return TrendState.BULLISH
        if row["lh_ll"] and row["ema_fast"] < row["ema_slow"] and adx_ok:
            return TrendState.BEARISH
        return TrendState.NEUTRAL

    def _trend_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Continuous feature in [-1, 1]:
            sign from EMA spread direction,
            magnitude scaled by normalized EMA distance and ADX strength.
        """
        ema_spread = (df["ema_fast"] - df["ema_slow"]) / df["close"]
        adx_norm = (df["adx"] / 50.0).clip(0, 1)  # 50 ADX ~ very strong trend
        score = np.tanh(ema_spread * 10) * adx_norm
        return score.clip(-1, 1)
