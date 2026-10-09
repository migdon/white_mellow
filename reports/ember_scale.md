# EMBER gold: scale in / hold winners longer (screen on EMBER's own trades, bot_audit/ember_scale.py)

| Version | Mean R | z | Total R | Halves | Worst drawdown |
|---|---|---|---|---|---|
| EMBER now | +0.052 | 2.77 | +30 | +0.058 / +0.047 | -6.1R |
| add a 2nd unit at +0.5 ATR (stop = 1st entry) | +0.070 | 2.66 | +41 | +0.071 / +0.069 | -7.6R |
| add at +1.0 ATR | +0.056 | 2.38 | +33 | | -7.0R |
| add at +1.5 ATR | +0.050 | 2.31 | +29 | | -6.6R |
| hold winners, 1.5 ATR trailing stop (max 10 days) | +0.084 | 2.66 | +48 | +0.050 / +0.117 | -10.0R |
| hold winners, 2.0 ATR trailing | +0.106 | 2.87 | +61 | +0.052 / +0.160 | -12.6R |
| hold winners, 3.0 ATR trailing | +0.089 | 2.24 | +52 | +0.040 / +0.138 | -10.0R |
Adding a unit = more exposure at the same quality (z unchanged, bigger drawdown). Holding winners gains only in the second half
(2022-2026, gold ~1,800 -> ~4,200); the first half is unchanged. The screen also flatters it: a held trade would block EMBER's next
trades (one position at a time) or overlap them, swap on longer holds is not counted (longs pay ~$0.66/oz a night at Atlas), and the
drawdown doubles — risky under Atlas's 10% / 6% trailing limits. Not adopted; a full re-run (no overlap, swap, Atlas replay) would be next.
