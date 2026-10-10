# EMBER gold as a pure set-and-forget trade (SL/TP only, no next-day exit) — FAIL

Code: `bot_audit/ember_setforget.py`. Same levels and 2 ATR stop as EMBER; exit only at TP or SL (15-day cap); Atlas swap included.
| Exit | Trades/yr | Win % | Mean R | z | Halves | Max DD | Nights held |
|---|---|---|---|---|---|---|---|
| TP 1 ATR (0.5R) | 39 | 67 | +0.018 | 0.47 | -0.024 / +0.060 | -10.1R | 6.0 |
| TP 2 ATR (1R) | 27 | 50 | -0.015 | -0.25 | | -16.4R | 10.2 |
| TP 3 ATR (1.5R) | 23 | 42 | -0.054 | -0.68 | | -21.8R | 12.1 |
| TP 4 ATR (2R) | 21 | 43 | +0.019 | 0.20 | | -14.4R | 14.1 |
| SL only | 19 | 38 | -0.048 | -0.45 | | -18.6R | 15.7 |
EMBER with its next-day exit: 72 trades/yr, +0.046R (z 2.4 after swap), max DD -6R. The short hold IS the edge: left alone, trades
sit for 1-2 weeks, pay swap, block new entries, and the first half (2018-2022) loses in every version.
