"""
ATR Filter + Volume Confirmation
----------------------------------
ATR filter:      ATR > SMA(ATR)                 -> weight 5
Volume filter:   Volume > SMA(volume, 20)        -> weight 10

Also exposes the raw ATR series for use by other indicators (FVG sizing,
AVWAP distance, stop-loss placement).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ATRFilterConfig:
    atr_period: int = 14
    atr_sma_period: int = 14
    volume_sma_period: int = 20
    atr_weight: float = 5.0
    volume_weight: float = 10.0


class ATRVolumeIndicator:
    def __init__(self, config: ATRFilterConfig = ATRFilterConfig()):
        self.config = config

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        cfg = self.config

        out["atr"] = self._atr(out, cfg.atr_period)
        out["atr_sma"] = out["atr"].rolling(cfg.atr_sma_period).mean()
        out["atr_expanding"] = out["atr"] > out["atr_sma"]

        out["volume_sma"] = out["volume"].rolling(cfg.volume_sma_period).mean()
        out["volume_confirmed"] = out["volume"] > out["volume_sma"]

        out["atr_score"] = np.where(out["atr_expanding"], cfg.atr_weight, 0.0)
        out["volume_score"] = np.where(out["volume_confirmed"], cfg.volume_weight, 0.0)
        return out

    @staticmethod
    def _atr(df: pd.DataFrame, period: int) -> pd.Series:
        high, low, close = df["high"], df["low"], df["close"]
        tr1 = (high - low).abs()
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False).mean()
