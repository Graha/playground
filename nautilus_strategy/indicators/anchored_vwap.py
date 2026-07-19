"""
Anchored VWAP (AVWAP) Indicator
--------------------------------
Anchored at the most recent liquidity-sweep candle.

Long confirmation:  price > AVWAP AND distance(price, AVWAP) < 0.5 * ATR
Short confirmation: price < AVWAP AND distance(price, AVWAP) < 0.5 * ATR

Weight: 20 points.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class AnchoredVWAPConfig:
    max_distance_atr_mult: float = 0.5
    weight: float = 20.0


class AnchoredVWAPIndicator:
    def __init__(self, config: AnchoredVWAPConfig = AnchoredVWAPConfig()):
        self.config = config

    def compute(
        self,
        df: pd.DataFrame,
        anchor_index,
        atr_col: str = "atr",
        price_col: str = "close",
        volume_col: str = "volume",
    ) -> pd.DataFrame:
        """
        anchor_index: index label (e.g. timestamp) of the sweep candle to
        anchor the VWAP calculation from. Bars before the anchor get NaN.
        """
        out = df.copy()
        if anchor_index not in out.index:
            out["avwap"] = np.nan
            out["avwap_distance_atr"] = np.nan
            out["avwap_score"] = 0.0
            return out

        anchor_loc = out.index.get_loc(anchor_index)
        typical_price = (out["high"] + out["low"] + out["close"]) / 3.0

        pv = typical_price * out[volume_col]
        cum_pv = pv.iloc[anchor_loc:].cumsum()
        cum_vol = out[volume_col].iloc[anchor_loc:].cumsum().replace(0, np.nan)

        avwap = pd.Series(np.nan, index=out.index)
        avwap.iloc[anchor_loc:] = cum_pv / cum_vol
        out["avwap"] = avwap

        distance = (out[price_col] - out["avwap"]).abs()
        if atr_col in out.columns:
            distance_atr = distance / out[atr_col].replace(0, np.nan)
        else:
            distance_atr = pd.Series(np.nan, index=out.index)
        out["avwap_distance_atr"] = distance_atr

        long_ok = (out[price_col] > out["avwap"]) & (
            distance_atr < self.config.max_distance_atr_mult
        )
        short_ok = (out[price_col] < out["avwap"]) & (
            distance_atr < self.config.max_distance_atr_mult
        )
        out["avwap_long_ok"] = long_ok.fillna(False)
        out["avwap_short_ok"] = short_ok.fillna(False)
        out["avwap_score"] = np.where(
            out["avwap_long_ok"] | out["avwap_short_ok"], self.config.weight, 0.0
        )
        return out
