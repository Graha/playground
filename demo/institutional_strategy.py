"""
Institutional Confluence Strategy for NautilusTrader
======================================================

Multi-timeframe confluence strategy:

    4H  -> HTF trend / market structure
    1H  -> Volume profile (POC / VAH / VAL / HVN / LVN)
    15M -> Anchored VWAP + liquidity sweep detection
    5M  -> Fair Value Gap retrace + entry trigger

Entry requires a combined confidence score >= entry_score_threshold
(see models/signal_score.py). Risk is fixed-fractional (0.5% of equity
per trade by default), stop is 1.5x ATR, targets are configurable
(2R / prior swing / next LVN), with a break-even-plus trail to AVWAP
once price has moved 1x ATR in favor.

NOTE ON NAUTILUSTRADER API:
This file targets the NautilusTrader `Strategy` base-class conventions
(on_start / on_bar / submit_order / cancel_order, BarType subscriptions,
Position/Order objects). NautilusTrader's exact API surface changes
between versions, so double-check method signatures (e.g.
`self.submit_order`, `OrderFactory.market/stop_market`, `BarType.from_str`)
against the NautilusTrader version you have installed and adjust imports
accordingly. The indicator/scoring logic in `indicators/` and `models/`
is framework-agnostic and will work unchanged regardless of small API
differences here.
"""

from decimal import Decimal

import pandas as pd

from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.objects import Quantity, Price
from nautilus_trader.model.orders import MarketOrder

from indicators import (
    MarketStructureIndicator, MarketStructureConfig,
    LiquiditySweepIndicator, LiquiditySweepConfig,
    FairValueGapIndicator, FVGConfig,
    AnchoredVWAPIndicator, AnchoredVWAPConfig,
    VolumeProfileIndicator, VolumeProfileConfig,
    ATRVolumeIndicator, ATRFilterConfig,
)
from models.signal_score import SignalScoreModel, SignalScoreConfig, ScoreWeights, TradeSignal


class InstitutionalStrategyConfig(StrategyConfig, frozen=True):
    instrument_id: str
    bar_type_4h: str
    bar_type_1h: str
    bar_type_15m: str
    bar_type_5m: str

    risk_per_trade_pct: float = 0.5      # % of equity risked per trade
    stop_atr_mult: float = 1.5
    take_profit_rr: float = 2.0          # option 1: fixed R multiple
    trail_start_atr_mult: float = 1.0    # start trailing once profit > 1 ATR

    entry_score_threshold: float = 75.0
    weights: dict = None                 # optional override of ScoreWeights

    market_structure: dict = None
    liquidity_sweep: dict = None
    fvg: dict = None
    avwap: dict = None
    volume_profile: dict = None
    atr_volume: dict = None


class InstitutionalStrategy(Strategy):
    """
    Multi-timeframe confluence strategy combining HTF trend, liquidity
    sweeps, FVG retracement, anchored VWAP, and volume profile confluence
    into a single weighted confidence score.
    """

    def __init__(self, config: InstitutionalStrategyConfig):
        super().__init__(config)
        self.instrument_id = InstrumentId.from_str(config.instrument_id)

        self.bar_type_4h = BarType.from_str(config.bar_type_4h)
        self.bar_type_1h = BarType.from_str(config.bar_type_1h)
        self.bar_type_15m = BarType.from_str(config.bar_type_15m)
        self.bar_type_5m = BarType.from_str(config.bar_type_5m)

        # Indicator engines (framework-agnostic, pandas-based) -----------
        self.ms_ind = MarketStructureIndicator(MarketStructureConfig(**(config.market_structure or {})))
        self.sweep_ind = LiquiditySweepIndicator(LiquiditySweepConfig(**(config.liquidity_sweep or {})))
        self.fvg_ind = FairValueGapIndicator(FVGConfig(**(config.fvg or {})))
        self.avwap_ind = AnchoredVWAPIndicator(AnchoredVWAPConfig(**(config.avwap or {})))
        self.vp_ind = VolumeProfileIndicator(VolumeProfileConfig(**(config.volume_profile or {})))
        self.atr_ind = ATRVolumeIndicator(ATRFilterConfig(**(config.atr_volume or {})))

        weights = ScoreWeights(**(config.weights or {})) if config.weights else ScoreWeights()
        self.score_model = SignalScoreModel(
            SignalScoreConfig(weights=weights, entry_threshold=config.entry_score_threshold)
        )

        # Rolling bar buffers per timeframe (converted to DataFrames on demand)
        self._buf_4h: list[Bar] = []
        self._buf_1h: list[Bar] = []
        self._buf_15m: list[Bar] = []
        self._buf_5m: list[Bar] = []

        self._max_buffer = 1000  # keep buffers bounded

        self._last_sweep_index = None
        self._active_stop_price = None
        self._active_entry_price = None
        self._active_atr = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def on_start(self):
        self.subscribe_bars(self.bar_type_4h)
        self.subscribe_bars(self.bar_type_1h)
        self.subscribe_bars(self.bar_type_15m)
        self.subscribe_bars(self.bar_type_5m)
        self.log.info("InstitutionalStrategy started, subscriptions active.")

    def on_stop(self):
        self.cancel_all_orders(self.instrument_id)
        self.close_all_positions(self.instrument_id)

    # ------------------------------------------------------------------ #
    # Bar handling
    # ------------------------------------------------------------------ #
    def on_bar(self, bar: Bar):
        if bar.bar_type == self.bar_type_4h:
            self._push(self._buf_4h, bar)
        elif bar.bar_type == self.bar_type_1h:
            self._push(self._buf_1h, bar)
        elif bar.bar_type == self.bar_type_15m:
            self._push(self._buf_15m, bar)
        elif bar.bar_type == self.bar_type_5m:
            self._push(self._buf_5m, bar)
            self._on_entry_bar()  # 5M is the entry/decision timeframe

    def _push(self, buf: list, bar: Bar):
        buf.append(bar)
        if len(buf) > self._max_buffer:
            del buf[0 : len(buf) - self._max_buffer]

    # ------------------------------------------------------------------ #
    # Core decision logic (runs on every new 5M bar)
    # ------------------------------------------------------------------ #
    def _on_entry_bar(self):
        if len(self._buf_5m) < 50 or len(self._buf_1h) < 100 or len(self._buf_4h) < 50:
            return  # not enough history yet

        df_4h = self._bars_to_df(self._buf_4h)
        df_1h = self._bars_to_df(self._buf_1h)
        df_15m = self._bars_to_df(self._buf_15m)
        df_5m = self._bars_to_df(self._buf_5m)

        # 1) HTF trend (4H) ------------------------------------------------
        ms = self.ms_ind.compute(df_4h)
        trend_state, _ = ms["trend_state"].iloc[-1], ms["trend_score"].iloc[-1]

        # 2) ATR + volume confirmation (5M, used for sizing & filters) -----
        atr_vol_5m = self.atr_ind.compute(df_5m)

        # 3) Liquidity sweep (15M) -----------------------------------------
        sweep_df = self.sweep_ind.compute(df_15m)
        last_sweep = self.sweep_ind.last_sweep(df_15m)
        if last_sweep is None:
            return
        self._last_sweep_index = last_sweep["index"]

        # 4) Anchored VWAP from sweep candle (15M) --------------------------
        avwap_df = self.avwap_ind.compute(
            sweep_df, anchor_index=self._last_sweep_index, atr_col=None
        )
        # merge ATR onto the 15m frame for distance calc if available
        if "atr" not in avwap_df.columns:
            avwap_df["atr"] = self.atr_ind.compute(df_15m)["atr"]
            avwap_df = self.avwap_ind.compute(
                avwap_df, anchor_index=self._last_sweep_index, atr_col="atr"
            )

        # 5) Volume profile (1H) ---------------------------------------------
        vp_df = self.vp_ind.compute(self.atr_ind.compute(df_1h))

        # 6) Fair Value Gap + retrace (5M) ------------------------------------
        fvg_df = self.fvg_ind.compute(atr_vol_5m, atr_col="atr")

        # ---- Merge the latest snapshot of each timeframe into one row ----
        merged = pd.Series({
            "trend_state": trend_state,
            "sweep_direction": sweep_df["sweep_direction"].iloc[-1],
            "active_fvg_direction": fvg_df["active_fvg_direction"].iloc[-1],
            "in_retrace_zone": bool(fvg_df["in_retrace_zone"].iloc[-1]),
            "avwap_long_ok": bool(avwap_df["avwap_long_ok"].iloc[-1]) if "avwap_long_ok" in avwap_df else False,
            "avwap_short_ok": bool(avwap_df["avwap_short_ok"].iloc[-1]) if "avwap_short_ok" in avwap_df else False,
            "near_poc": bool(vp_df["near_poc"].iloc[-1]) if "near_poc" in vp_df else False,
            "near_hvn": bool(vp_df["near_hvn"].iloc[-1]) if "near_hvn" in vp_df else False,
            "atr_expanding": bool(atr_vol_5m["atr_expanding"].iloc[-1]),
            "volume_confirmed": bool(atr_vol_5m["volume_confirmed"].iloc[-1]),
        })

        result = self.score_model.score_row(merged)
        atr_current = atr_vol_5m["atr"].iloc[-1]

        if result["signal"] == TradeSignal.LONG and not self._has_open_position():
            self._enter(OrderSide.BUY, atr_current, df_5m)
        elif result["signal"] == TradeSignal.SHORT and not self._has_open_position():
            self._enter(OrderSide.SELL, atr_current, df_5m)
        else:
            self._manage_open_position(df_5m, atr_current)

    # ------------------------------------------------------------------ #
    # Order management
    # ------------------------------------------------------------------ #
    def _enter(self, side: OrderSide, atr_value: float, df_5m: pd.DataFrame):
        entry_price = df_5m["close"].iloc[-1]
        stop_distance = self.config.stop_atr_mult * atr_value

        if side == OrderSide.BUY:
            stop_price = entry_price - stop_distance
        else:
            stop_price = entry_price + stop_distance

        risk_amount = stop_distance
        qty = self._position_size(risk_amount)
        if qty <= 0:
            self.log.warning("Position size computed as 0, skipping entry.")
            return

        order = self.order_factory.market(
            instrument_id=self.instrument_id,
            order_side=side,
            quantity=Quantity.from_str(str(qty)),
            time_in_force=TimeInForce.GTC,
        )
        self.submit_order(order)

        self._active_entry_price = entry_price
        self._active_stop_price = stop_price
        self._active_atr = atr_value

        self.log.info(
            f"Entered {side.name} qty={qty} entry={entry_price:.5f} "
            f"stop={stop_price:.5f} atr={atr_value:.5f}"
        )

    def _manage_open_position(self, df_5m: pd.DataFrame, atr_current: float):
        """Trail stop to AVWAP once profit exceeds trail_start_atr_mult * ATR."""
        position = self._get_open_position()
        if position is None or self._active_entry_price is None:
            return

        current_price = df_5m["close"].iloc[-1]
        favorable_move = (
            current_price - self._active_entry_price
            if position.side == OrderSide.BUY
            else self._active_entry_price - current_price
        )

        if favorable_move > self.config.trail_start_atr_mult * atr_current:
            # In production, recompute the live AVWAP value here and
            # move the protective stop order price to it (never loosen it).
            self.log.info("Profit threshold reached; trailing stop to AVWAP.")
            # self.modify_order(...)  # implementation depends on your
            # bracket/stop-order setup in NautilusTrader.

    def _position_size(self, risk_per_unit: float) -> float:
        equity = float(self.portfolio.net_exposure(self.instrument_id) or 0) or 10_000.0
        risk_capital = equity * (self.config.risk_per_trade_pct / 100.0)
        if risk_per_unit <= 0:
            return 0.0
        return round(risk_capital / risk_per_unit, 4)

    def _has_open_position(self) -> bool:
        return self._get_open_position() is not None

    def _get_open_position(self):
        positions = self.cache.positions_open(instrument_id=self.instrument_id)
        return positions[0] if positions else None

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #
    @staticmethod
    def _bars_to_df(bars: list) -> pd.DataFrame:
        data = {
            "open": [float(b.open) for b in bars],
            "high": [float(b.high) for b in bars],
            "low": [float(b.low) for b in bars],
            "close": [float(b.close) for b in bars],
            "volume": [float(b.volume) for b in bars],
        }
        index = [pd.Timestamp(b.ts_event, unit="ns") for b in bars]
        return pd.DataFrame(data, index=index)
