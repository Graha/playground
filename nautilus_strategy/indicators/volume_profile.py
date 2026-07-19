"""
Volume Profile Indicator
--------------------------
Computed on a rolling window (default 96 bars ~ 1H bars covering 4 days,
tune to taste) and produces:

    POC  - Point of Control        (price level with max volume)
    VAH  - Value Area High         (70% value area upper bound)
    VAL  - Value Area Low          (70% value area lower bound)
    HVN  - High Volume Nodes       (local peaks in the volume histogram)
    LVN  - Low Volume Nodes        (local troughs in the volume histogram)

Weight: 15 points, awarded when price is near POC or inside an HVN.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class VolumeProfileConfig:
    rolling_bars: int = 96
    bins: int = 60
    value_area_pct: float = 0.70
    near_atr_mult: float = 0.25  # "near POC/HVN" distance threshold in ATR
    weight: float = 15.0


class VolumeProfileIndicator:
    def __init__(self, config: VolumeProfileConfig = VolumeProfileConfig()):
        self.config = config

    def compute(self, df: pd.DataFrame, atr_col: str = "atr") -> pd.DataFrame:
        out = df.copy()
        n = len(out)
        cfg = self.config

        poc = np.full(n, np.nan)
        vah = np.full(n, np.nan)
        val = np.full(n, np.nan)
        hvn_flags = [None] * n
        lvn_flags = [None] * n

        for i in range(cfg.rolling_bars, n):
            window = out.iloc[i - cfg.rolling_bars : i]
            profile = self._build_profile(window, cfg.bins)
            if profile is None:
                continue
            bin_centers, volumes = profile

            poc_idx = int(np.argmax(volumes))
            poc[i] = bin_centers[poc_idx]

            va_low_idx, va_high_idx = self._value_area(volumes, poc_idx, cfg.value_area_pct)
            val[i] = bin_centers[va_low_idx]
            vah[i] = bin_centers[va_high_idx]

            hvn_flags[i] = self._local_peaks(bin_centers, volumes)
            lvn_flags[i] = self._local_troughs(bin_centers, volumes)

        out["poc"] = poc
        out["vah"] = vah
        out["val"] = val
        out["hvn_levels"] = hvn_flags
        out["lvn_levels"] = lvn_flags

        out["near_poc"] = self._near_level(out["close"], out["poc"], out, atr_col)
        out["near_hvn"] = out.apply(
            lambda row: self._near_any_level(row["close"], row["hvn_levels"], row.get(atr_col)),
            axis=1,
        )
        out["volume_profile_score"] = np.where(
            out["near_poc"] | out["near_hvn"], cfg.weight, 0.0
        )
        return out

    # ------------------------------------------------------------------ #
    def _build_profile(self, window: pd.DataFrame, bins: int):
        if window["volume"].sum() == 0:
            return None
        low, high = window["low"].min(), window["high"].max()
        if high <= low:
            return None
        edges = np.linspace(low, high, bins + 1)
        centers = (edges[:-1] + edges[1:]) / 2
        volumes = np.zeros(bins)

        # Distribute each bar's volume across the price bins it spans
        # (typical-price weighted approximation for speed/simplicity).
        typical = (window["high"] + window["low"] + window["close"]) / 3.0
        bin_idx = np.clip(np.digitize(typical, edges) - 1, 0, bins - 1)
        for idx, vol in zip(bin_idx, window["volume"]):
            volumes[idx] += vol

        return centers, volumes

    def _value_area(self, volumes: np.ndarray, poc_idx: int, pct: float):
        total = volumes.sum()
        target = total * pct
        low_idx = high_idx = poc_idx
        acc = volumes[poc_idx]
        n = len(volumes)

        while acc < target and (low_idx > 0 or high_idx < n - 1):
            expand_down = volumes[low_idx - 1] if low_idx > 0 else -1
            expand_up = volumes[high_idx + 1] if high_idx < n - 1 else -1
            if expand_down >= expand_up:
                low_idx = max(low_idx - 1, 0)
                acc += volumes[low_idx]
            else:
                high_idx = min(high_idx + 1, n - 1)
                acc += volumes[high_idx]
        return low_idx, high_idx

    def _local_peaks(self, centers: np.ndarray, volumes: np.ndarray) -> list:
        peaks = []
        for i in range(1, len(volumes) - 1):
            if volumes[i] > volumes[i - 1] and volumes[i] > volumes[i + 1]:
                peaks.append(centers[i])
        return peaks

    def _local_troughs(self, centers: np.ndarray, volumes: np.ndarray) -> list:
        troughs = []
        for i in range(1, len(volumes) - 1):
            if volumes[i] < volumes[i - 1] and volumes[i] < volumes[i + 1]:
                troughs.append(centers[i])
        return troughs

    def _near_level(self, price: pd.Series, level: pd.Series, df: pd.DataFrame, atr_col: str):
        if atr_col not in df.columns:
            return pd.Series(False, index=price.index)
        distance = (price - level).abs()
        threshold = df[atr_col] * self.config.near_atr_mult
        return (distance <= threshold).fillna(False)

    def _near_any_level(self, price, levels, atr_value):
        if not levels or atr_value is None or pd.isna(atr_value):
            return False
        threshold = atr_value * self.config.near_atr_mult
        return any(abs(price - lvl) <= threshold for lvl in levels)
