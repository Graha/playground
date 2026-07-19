# Institutional Confluence Strategy (NautilusTrader)

Multi-timeframe confluence strategy: HTF trend (4H) → liquidity sweep (15M)
→ Fair Value Gap retrace (5M) → anchored VWAP (15M) → volume profile (1H),
combined into a single 0–100 weighted confidence score. Entries only fire
when the score clears `entry_score_threshold` (default 75).

## Structure

```
strategies/institutional_strategy.py   NautilusTrader Strategy implementation
indicators/                             Framework-agnostic pandas indicators
    market_structure.py                  HTF trend / swing structure / ADX
    liquidity_sweep.py                    Stop-hunt / liquidity-grab detector
    fair_value_gap.py                     FVG detection + 30-70% retrace zone
    anchored_vwap.py                      VWAP anchored at sweep candle
    volume_profile.py                     Rolling POC / VAH / VAL / HVN / LVN
    atr_filter.py                         ATR expansion + volume confirmation
models/signal_score.py                  Weighted confidence score + signal
backtests/run_backtest.py               Standalone pandas backtest/feature builder
config/strategy.yaml                    All indicator + risk parameters
data/                                   Put your OHLCV parquet files here
```

## Quick start (indicator/signal logic only, no NautilusTrader required)

```bash
pip install pandas numpy pyarrow
cd backtests
python run_backtest.py --data-dir ../data --symbol EURUSD
```

Expects `EURUSD_5m.parquet`, `EURUSD_15m.parquet`, `EURUSD_1h.parquet`,
`EURUSD_4h.parquet` in `data/`, each with an OHLCV DataFrame indexed by
timestamp.

## Wiring into NautilusTrader

`strategies/institutional_strategy.py` targets NautilusTrader's `Strategy`
base class conventions. Install NautilusTrader (`pip install nautilus_trader`)
and check the exact API for your installed version — method names like
`submit_order`, `order_factory.market`, and stop-order/trailing mechanics
can shift between releases, so verify against your version's docs before
running a live/backtest engine. The indicator and scoring modules are
pure pandas/numpy and require no NautilusTrader-specific types, so they can
be unit-tested, reused in a Jupyter notebook, or fed into an ML pipeline
independent of the strategy wrapper.

## Confidence score weights

| Component        | Weight |
|-------------------|-------|
| Liquidity Sweep    | 30    |
| Fair Value Gap     | 20    |
| Anchored VWAP      | 20    |
| Volume Profile     | 15    |
| HTF Trend          | 10    |
| Volume Confirmation| 5     |
| **Total**          | **100** |

Enter only if score ≥ `entry_score_threshold` (default 75) **and** every
component agrees on direction (see `SignalScoreModel.score_row`).

## Risk management

- Position size: fixed-fractional, `risk_per_trade_pct` (default 0.5%) of equity
- Stop loss: entry − 1.5×ATR (long) / entry + 1.5×ATR (short)
- Take profit: 2R by default (also supports prior-swing / next-LVN targets —
  wire these into `_manage_open_position` using your own swing/LVN lookup)
- Trailing: once profit > 1×ATR, move stop to the live AVWAP value

## Next steps for the ML comparison (per the original design notes)

1. Use `backtests/run_backtest.py`'s `build_features()` output as your
   feature matrix — it already contains every raw indicator value, not just
   the binary confluence signal.
2. Label bars with forward returns (e.g. return over next N bars, or
   triple-barrier labeling) to train XGBoost/LightGBM/CatBoost or a small
   transformer.
3. Compare the ML model's precision/recall and equity curve against the
   rule-based `SignalScoreModel` baseline on the same walk-forward folds.
4. Run walk-forward optimization + Monte Carlo resampling of trade order
   and realistic spread/slippage in NautilusTrader's `BacktestEngine`
   before considering this live-ready.

## Optimization grid

See `config/strategy.yaml -> optimization_grid` for the parameter ranges
called out in the original design (EMA periods, ATR period, FVG min size,
sweep lookback, volume-profile bin count, HVN distance, entry score
threshold, and risk/reward multiple). This grid is not consumed directly by
NautilusTrader — pair it with your own walk-forward optimizer harness
(e.g. `optuna`, or NautilusTrader's parameter search tooling).
