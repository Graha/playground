"""
Signal Confidence Score
-------------------------
Combines all indicator sub-scores into a single 0-100 confidence score
and derives a directional trade signal.

Weights (sum to 100):
    Liquidity Sweep     30
    Fair Value Gap       20
    Anchored VWAP        20
    Volume Profile       15
    Trend                10
    Volume                5
"""

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from indicators.market_structure import TrendState
from indicators.liquidity_sweep import SweepDirection
from indicators.fair_value_gap import FVGDirection


class TradeSignal(Enum):
    NONE = 0
    LONG = 1
    SHORT = -1


@dataclass
class ScoreWeights:
    sweep: float = 30.0
    fvg: float = 20.0
    avwap: float = 20.0
    volume_profile: float = 15.0
    trend: float = 10.0
    volume: float = 5.0

    @property
    def total(self) -> float:
        return (
            self.sweep + self.fvg + self.avwap
            + self.volume_profile + self.trend + self.volume
        )


@dataclass
class SignalScoreConfig:
    weights: ScoreWeights = None
    entry_threshold: float = 75.0

    def __post_init__(self):
        if self.weights is None:
            self.weights = ScoreWeights()


class SignalScoreModel:
    """
    Consumes a single merged row (pd.Series) containing the outputs of every
    indicator (already resampled/aligned onto the entry timeframe) and
    produces a confidence score plus a directional trade signal.

    Expected fields on the row:
        trend_state            (TrendState)
        sweep_direction         (int, SweepDirection value)
        active_fvg_direction    (float/int, FVGDirection value)
        in_retrace_zone         (bool)
        avwap_long_ok           (bool)
        avwap_short_ok          (bool)
        near_poc / near_hvn     (bool)
        atr_expanding           (bool)
        volume_confirmed        (bool)
    """

    def __init__(self, config: SignalScoreConfig = None):
        self.config = config or SignalScoreConfig()

    def score_row(self, row: pd.Series) -> dict:
        w = self.config.weights

        sweep_dir = SweepDirection(int(row.get("sweep_direction", 0)))
        fvg_dir_raw = row.get("active_fvg_direction", 0)
        fvg_dir = FVGDirection(int(fvg_dir_raw)) if pd.notna(fvg_dir_raw) else FVGDirection.NONE
        trend_state = row.get("trend_state", TrendState.NEUTRAL)

        # Directional agreement checks --------------------------------
        long_bias = (
            trend_state == TrendState.BULLISH
            and sweep_dir == SweepDirection.BULLISH
            and fvg_dir == FVGDirection.BULLISH
            and bool(row.get("in_retrace_zone", False))
            and bool(row.get("avwap_long_ok", False))
        )
        short_bias = (
            trend_state == TrendState.BEARISH
            and sweep_dir == SweepDirection.BEARISH
            and fvg_dir == FVGDirection.BEARISH
            and bool(row.get("in_retrace_zone", False))
            and bool(row.get("avwap_short_ok", False))
        )

        # Score accumulation --------------------------------------------
        score = 0.0
        score += w.sweep if sweep_dir != SweepDirection.NONE else 0.0
        score += w.fvg if fvg_dir != FVGDirection.NONE and row.get("in_retrace_zone", False) else 0.0
        score += w.avwap if (row.get("avwap_long_ok", False) or row.get("avwap_short_ok", False)) else 0.0
        score += w.volume_profile if (row.get("near_poc", False) or row.get("near_hvn", False)) else 0.0
        score += w.trend if trend_state != TrendState.NEUTRAL else 0.0
        score += w.volume if row.get("volume_confirmed", False) else 0.0

        signal = TradeSignal.NONE
        if score >= self.config.entry_threshold:
            if long_bias:
                signal = TradeSignal.LONG
            elif short_bias:
                signal = TradeSignal.SHORT

        return {
            "score": score,
            "signal": signal,
            "long_bias": long_bias,
            "short_bias": short_bias,
        }

    def score_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        results = df.apply(self.score_row, axis=1, result_type="expand")
        out = df.copy()
        out["confidence_score"] = results["score"]
        out["trade_signal"] = results["signal"]
        out["long_bias"] = results["long_bias"]
        out["short_bias"] = results["short_bias"]
        return out
