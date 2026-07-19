"""
Liquidity Sweep Indicator
--------------------------
Detects stop-hunt / liquidity-grab candles:

Bullish sweep:
    low  < lowest_low(lookback)
    close > lowest_low(lookback)

Bearish sweep:
    high > highest_high(lookback)
    close < highest_high(lookback)

Weight: 30 points (largest single component of the confidence score).
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class SweepDirection(Enum):
    NONE = 0
    BULLISH = 1
    BEARISH = -1


@dataclass
class LiquiditySweepConfig:
    lookback: int = 20
    weight: float = 30.0


class LiquiditySweepIndicator:
    def __init__(self, config: LiquiditySweepConfig = LiquiditySweepConfig()):
        self.config = config

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        lb = self.config.lookback

        # Use prior N bars only (exclude current bar) to avoid lookahead.
        rolling_low = out["low"].shift(1).rolling(lb).min()
        rolling_high = out["high"].shift(1).rolling(lb).max()

        out["rolling_low"] = rolling_low
        out["rolling_high"] = rolling_high

        bullish_sweep = (out["low"] < rolling_low) & (out["close"] > rolling_low)
        bearish_sweep = (out["high"] > rolling_high) & (out["close"] < rolling_high)

        direction = np.select(
            [bullish_sweep, bearish_sweep],
            [SweepDirection.BULLISH.value, SweepDirection.BEARISH.value],
            default=SweepDirection.NONE.value,
        )
        out["sweep_direction"] = direction
        out["sweep_score"] = np.where(direction != 0, self.config.weight, 0.0)

        # Store the anchor candle index/price for downstream AVWAP anchoring.
        out["sweep_anchor_price"] = np.where(
            direction == SweepDirection.BULLISH.value,
            out["low"],
            np.where(direction == SweepDirection.BEARISH.value, out["high"], np.nan),
        )
        return out

    def last_sweep(self, df: pd.DataFrame) -> dict:
        """Return info about the most recent sweep bar, or None if none found."""
        computed = self.compute(df)
        sweeps = computed[computed["sweep_direction"] != 0]
        if sweeps.empty:
            return None
        last = sweeps.iloc[-1]
        return {
            "index": sweeps.index[-1],
            "direction": SweepDirection(int(last["sweep_direction"])),
            "anchor_price": last["sweep_anchor_price"],
            "score": last["sweep_score"],
        }
