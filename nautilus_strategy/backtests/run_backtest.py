"""
Lightweight pandas backtest for the confluence strategy's indicator +
scoring logic, independent of NautilusTrader. Useful for quickly validating
signal quality, parameter sweeps, and generating the ML feature set
before wiring the strategy into NautilusTrader's BacktestEngine.

Usage:
    python run_backtest.py --data-dir ../data --symbol EURUSD

Expects parquet files in data_dir named:
    {symbol}_5m.parquet, {symbol}_15m.parquet,
    {symbol}_1h.parquet,  {symbol}_4h.parquet
each with columns: ['open','high','low','close','volume'] and a
DatetimeIndex.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from indicators import (
    MarketStructureIndicator, MarketStructureConfig,
    LiquiditySweepIndicator, LiquiditySweepConfig,
    FairValueGapIndicator, FVGConfig,
    AnchoredVWAPIndicator, AnchoredVWAPConfig,
    VolumeProfileIndicator, VolumeProfileConfig,
    ATRVolumeIndicator, ATRFilterConfig,
)
from models.signal_score import SignalScoreModel, SignalScoreConfig, TradeSignal


def load_data(data_dir: Path, symbol: str) -> dict:
    frames = {}
    for tf, suffix in [("4h", "4h"), ("1h", "1h"), ("15m", "15m"), ("5m", "5m")]:
        path = data_dir / f"{symbol}_{suffix}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Missing data file: {path}")
        df = pd.read_parquet(path)
        df = df.sort_index()
        frames[tf] = df
    return frames


def build_features(frames: dict) -> pd.DataFrame:
    """
    Merge all timeframes onto the 5M index via as-of (forward-fill) joins,
    producing one row per 5M bar with every indicator's latest known value.
    This is the same feature set usable for the rule-based strategy or as
    ML training features (see the "Additional improvements" section).
    """
    ms_ind = MarketStructureIndicator(MarketStructureConfig())
    sweep_ind = LiquiditySweepIndicator(LiquiditySweepConfig())
    fvg_ind = FairValueGapIndicator(FVGConfig())
    avwap_ind = AnchoredVWAPIndicator(AnchoredVWAPConfig())
    vp_ind = VolumeProfileIndicator(VolumeProfileConfig())
    atr_ind = ATRVolumeIndicator(ATRFilterConfig())

    df_4h = ms_ind.compute(frames["4h"])
    df_1h = vp_ind.compute(atr_ind.compute(frames["1h"]))
    df_15h_atr = atr_ind.compute(frames["15m"])
    df_15m = sweep_ind.compute(df_15h_atr)

    # Anchor AVWAP at each sweep occurrence by forward-filling the anchor
    # price/time and recomputing cumulative VWAP from the last sweep index.
    df_15m = _rolling_anchored_vwap(df_15m, avwap_ind)

    df_5m_atr = atr_ind.compute(frames["5m"])
    df_5m = fvg_ind.compute(df_5m_atr, atr_col="atr")

    # As-of merge everything onto the 5M timestamps.
    merged = df_5m.copy()
    merged = pd.merge_asof(
        merged.sort_index(), df_4h[["trend_state"]].sort_index(),
        left_index=True, right_index=True,
    )
    merged = pd.merge_asof(
        merged, df_1h[["near_poc", "near_hvn"]].sort_index(),
        left_index=True, right_index=True,
    )
    merged = pd.merge_asof(
        merged,
        df_15m[["sweep_direction", "avwap_long_ok", "avwap_short_ok"]].sort_index(),
        left_index=True, right_index=True,
    )
    return merged


def _rolling_anchored_vwap(df_15m: pd.DataFrame, avwap_ind: AnchoredVWAPIndicator) -> pd.DataFrame:
    """
    Recompute AVWAP anchored at each new sweep event as it occurs, carrying
    forward the same anchor until the next sweep. This avoids recomputing
    from scratch on every single bar in a tight loop for large datasets;
    for very large histories, prefer a vectorized approach.
    """
    sweep_indices = df_15m.index[df_15m["sweep_direction"] != 0]
    if len(sweep_indices) == 0:
        df_15m["avwap"] = np.nan
        df_15m["avwap_long_ok"] = False
        df_15m["avwap_short_ok"] = False
        return df_15m

    result_frames = []
    for i, anchor in enumerate(sweep_indices):
        end = sweep_indices[i + 1] if i + 1 < len(sweep_indices) else df_15m.index[-1]
        segment = df_15m.loc[anchor:end]
        computed = avwap_ind.compute(segment, anchor_index=anchor, atr_col="atr")
        result_frames.append(computed)

    out = pd.concat(result_frames)
    out = out[~out.index.duplicated(keep="last")]
    return out.reindex(df_15m.index).ffill()


def run(data_dir: str, symbol: str, entry_score_threshold: float = 75.0):
    frames = load_data(Path(data_dir), symbol)
    features = build_features(frames)

    score_model = SignalScoreModel(SignalScoreConfig(entry_threshold=entry_score_threshold))
    scored = score_model.score_frame(features)

    trades = scored[scored["trade_signal"] != TradeSignal.NONE]
    print(f"Total bars: {len(scored)}")
    print(f"Signals generated: {len(trades)}")
    print(trades[["close", "confidence_score", "trade_signal"]].tail(20))

    out_path = Path(data_dir) / f"{symbol}_features_scored.parquet"
    scored.to_parquet(out_path)
    print(f"Saved scored feature set to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run confluence-strategy feature/signal backtest.")
    parser.add_argument("--data-dir", default="../data")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--entry-score-threshold", type=float, default=75.0)
    args = parser.parse_args()

    run(args.data_dir, args.symbol, args.entry_score_threshold)
