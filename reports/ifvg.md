# FVG -> IFVG strategy — FAIL

Protocol: `bot_audit/PROTOCOL_IFVG.md` (written before the run). Code: `bot_audit/ifvg.py`. M5, Sep 2018 - 2026.
Primary: inversion close through a live FVG, enter next open, stop at the move's extreme, 2R, 08:00-12:00 New York.

| Market | Trades/yr | Win % | Mean R | t | Halves | 2x spread |
|---|---|---|---|---|---|---|
| NAS100 | 430 | 35.6 | -0.021 | -0.95 | -0.031 / -0.012 | -0.074 |
| XAUUSD | 405 | 35.5 | -0.079 | -3.72 | -0.088 / -0.070 | -0.160 |
| EURUSD | 400 | 34.6 | -0.118 | -5.59 | -0.127 / -0.108 | -0.190 |

Variants (information only), mean R: 1R target NAS -0.045 / gold -0.097 / EUR -0.115; 3R -0.020 / -0.090 / -0.104;
all hours -0.078 / -0.165 / -0.293; retest (limit) entry -0.050 / -0.078 / -0.135; M15 -0.069 / -0.048 / -0.089.
Without any spread: NAS100 +0.035R (t 1.5), gold +0.017R (t 0.8) — a small gross tendency that the spread more than eats,
because the stops are tight (a few points on M5) and the spread is a large share of 1R.
The NY morning kill zone is clearly better than trading all hours, but no version is positive after costs.

## More FX, London kill zone, higher timeframes (addendum) — still FAIL
Mean R per trade (t), M5 NY morning = primary:
| Market | M5 NY (primary) | M5 London 02-05 NY | M15 NY | M15 London | H1 London+NY |
|---|---|---|---|---|---|
| GBPUSD | -0.122 (-5.7) | -0.135 | -0.060 | -0.040 | +0.010 (t 0.3, 91/yr) |
| USDJPY | -0.066 (-3.1) | -0.046 | -0.026 | -0.007 | +0.012 (t 0.3, 70/yr) |
| EURUSD | -0.118 (-5.6) | -0.155 | -0.089 | -0.091 | +0.005 (t 0.1, 87/yr) |
| XAUUSD | -0.079 (-3.7) | -0.140 | -0.048 | -0.126 | -0.134 (-3.5) |
Bigger timeframes shrink the loss (the spread is a smaller part of the stop) but only reach zero, never a usable edge.
