# Published crypto strategies on BTCUSD (Atlas costs)

Protocol: `bot_audit/PROTOCOL_CRYPTO.md`. Code: `bot_audit/crypto.py`. Sep 2018 - Oct 2026, 1x notional, spread 0.07% + 15%/yr financing.
| Rule | Mean / day | t | Halves | 2x cost | Max DD (1x) | Verdict |
|---|---|---|---|---|---|---|
| R1 weekly TSMOM, long/flat (Liu & Tsyvinski) | +0.026% | +0.53 | +0.048 / +0.004 | -0.001% | -167% | FAIL |
| R1 long/short (info) | -0.098% | -1.49 | | | | FAIL |
| R2 intraday TSMOM 00:00-00:30 -> 23:30-24:00 UTC (Shen et al.) | -0.083%/trade | -9.3 | | | | FAIL (gross -0.013%) |
| R3 long while close > SMA50 | +0.138% | +3.08 | +0.190 / +0.086 | +0.113% (t 2.5) | -74% | PASS (statistically) |
| buy & hold (reference) | +0.108% | +1.64 | | | -136% | |

R3 passes the rule, but most of it is being long BTC during 2018-2026 (BTC ~6k -> ~82k): the filter's own value is roughly
halving the drawdown and adding ~0.03%/day over buy & hold. Rough Atlas evaluation (daily closes only, so breaches are UNDER-stated):
0.1x notional pass 13% in 30 days / 67% in a year / 0% breach; 0.2x 26% / 84% / 7%; 0.5x 46% / 79% / 21%.
Worse than NBRO + EMBER gold (46% in a month, 96% in a year, 4% breached), and it depends on BTC keeping its long-run rise.
