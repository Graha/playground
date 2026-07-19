"""
Fair Value Gap (FVG) Indicator
-------------------------------
Bullish FVG:  high[t-2] < low[t]      (gap up, imbalance left below)
Bearish FVG:  low[t-2]  > high[t]     (gap down, imbalance left above)

A valid retrace requires price to come back into the gap and sit between
30% and 70% of the gap's range (the "equilibrium" zone).

Weight: 20 points.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class FVGDirection(Enum):
    NONE = 0
    BULLISH = 1
    BEARISH = -1


@dataclass
class FVGConfig:
    min_size_atr_mult: float = 0.25  # gap must be >= this * ATR to count
    retrace_low: float = 0.30
    retrace_high: float = 0.70
    weight: float = 20.0


class FairValueGapIndicator:
    def __init__(self, config: FVGConfig = FVGConfig()):
        self.config = config

    def compute(self, df: pd.DataFrame, atr_col: str = "atr") -> pd.DataFrame:
        """
        df must contain ['high', 'low', 'close'] and, if min_size filtering
        is desired, an ATR column (see indicators/atr_filter.py).
        """
        out = df.copy()

        high_2 = out["high"].shift(2)
        low_2 = out["low"].shift(2)

        bullish_gap = out["low"] > high_2  # gap between high[t-2] and low[t]
        bearish_gap = out["high"] < low_2

        gap_top = np.where(bullish_gap, out["low"], np.where(bearish_gap, low_2, np.nan))
        gap_bottom = np.where(bullish_gap, high_2, np.where(bearish_gap, out["high"], np.nan))
        gap_size = gap_top - gap_bottom

        if atr_col in out.columns:
            min_size = out[atr_col] * self.config.min_size_atr_mult
            size_ok = gap_size >= min_size
        else:
            size_ok = np.ones(len(out), dtype=bool)

        direction = np.select(
            [bullish_gap & size_ok, bearish_gap & size_ok],
            [FVGDirection.BULLISH.value, FVGDirection.BEARISH.value],
            default=FVGDirection.NONE.value,
        )

        out["fvg_direction"] = direction
        out["fvg_top"] = gap_top
        out["fvg_bottom"] = gap_bottom
        out["fvg_size"] = gap_size

        # Forward-fill the most recent *unmitigated* gap so later bars can
        # check whether price has retraced into it.
        out["active_fvg_top"] = np.where(direction != 0, gap_top, np.nan)
        out["active_fvg_bottom"] = np.where(direction != 0, gap_bottom, np.nan)
        out["active_fvg_direction"] = np.where(direction != 0, direction, np.nan)
        out[["active_fvg_top", "active_fvg_bottom", "active_fvg_direction"]] = out[
            ["active_fvg_top", "active_fvg_bottom", "active_fvg_direction"]
        ].ffill()

        out["in_retrace_zone"] = self._in_retrace_zone(out)
        out["fvg_score"] = np.where(
            (direction != 0) | out["in_retrace_zone"], self.config.weight, 0.0
        )
        return out

    def _in_retrace_zone(self, df: pd.DataFrame) -> pd.Series:
        top = df["active_fvg_top"]
        bottom = df["active_fvg_bottom"]
        rng = (top - bottom).replace(0, np.nan)
        pct_into_gap = (top - df["close"]) / rng
        in_zone = (pct_into_gap >= self.config.retrace_low) & (
            pct_into_gap <= self.config.retrace_high
        )
        return in_zone.fillna(False)
