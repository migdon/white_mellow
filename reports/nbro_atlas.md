# NBRO on Atlas 1-Step Access — replay of the real trades

**Data.** Vantage MT5 M5, NAS100.r and SP500.r, Sep 2018 → Oct 2026 (the files hold daily bars only before Sep 2018).
**Spreads.** Measured in the US session: NAS100 1.7 points, SPX500 0.6 points.
**Engine.** `noise_fx/noise_backtest.py`. On synthetic data it makes the same trades as `nbro_app.py`, trade for trade.
**Simulator.** `noise_fx/atlas_sim.py`, replayed from 359 start dates.

## NBRO trades

| | Trades | Avg/trade (net) | 2025 | 2026 YTD |
|---|---|---|---|---|
| NAS100 | 1,427 | +0.069% | +0.016% | +0.023% |
| SPX500 | 1,464 | +0.036% | +0.031% | −0.043% |

There is a trade on 68% of weekdays. The edge is weaker in 2025–2026 than in 2020–2023.

## Evaluation (+3%, 10% trailing, 5% daily)

| Risk per index | Pass | Breach | Median trading days |
|---|---|---|---|
| 0.5% | 0.90 | 0.01 | 55 |
| 0.75% | 0.91 | 0.02 | 34 |
| **1.0%** | **0.92** | **0.04** | **26** |
| 1.5% | 0.89 | 0.11 | 16 |

The 2023+ trades alone give 1.0% → pass 0.92, breach 0.04, median 29 days.

## Funded (6% trailing, 3% daily, Protector 2%, payout = 3 days ≥ +0.5% and best day ≤ 40%)

| Risk per index | Alive after 1 year | Payouts/yr | $ paid/yr ($50k), 2018+ | $ paid/yr, 2023+ only |
|---|---|---|---|---|
| 0.25% | 1.00 | 1.0 | 1,290 | 610 |
| **0.35%** | **0.85 (1.00 on 2023+)** | **1.5** | **1,960** | **850** |
| 0.5% | 0.45 | 1.5 | 2,420 | 1,200 (but 58% of accounts dead) |

- The Protector was never reached at these sizes. The worst open loss is about 2 × 1.03% × 0.35 = 0.7%.
- The bottleneck is the payout rule. A +0.5% day needs a large index move at 0.35% risk.

**Presets added to `bots/nbro_app.py`:**
- `--preset atlas-eval`: 1.0% per index
- `--preset atlas-funded`: 0.35% per index, Protector shield at 1.7%

Assumptions:
- Close-to-close days, with conservative intraday lows (both indices at their worst at the same moment).
- No slippage beyond the spread.
- Gaps through the 1% stop are not modelled.

## Tested improvement: volatility-targeted sizing (Zarattini et al. 2024)

- **Rule.** Weight = median σ / σ, where σ is the standard deviation of the last 14 session returns, known at the open.
  Capped at 4x.
- **Pass bar, set beforehand:** better Sharpe in BOTH halves of the data.

| Version | Full | 2018–22 | 2022–26 | 2023+ | Worst day (1x) |
|---|---|---|---|---|---|
| NBRO now | 1.14 | 1.49 | 0.75 | 0.69 | −6.1% |
| Vol-targeted | 1.15 | 1.61 | 0.70 | 0.67 | −4.8% |

**FAIL.** No better Sharpe, and worse in the recent half. It only makes the worst day smaller. Not adopted.
