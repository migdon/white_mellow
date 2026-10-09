# ChatGPT's "Multi-Timeframe Trend-Following + Breakout + News Filter" (XAUUSD) — FAIL

Protocol: `bot_audit/PROTOCOL_MTF_BREAKOUT.md`. Code: `bot_audit/mtf_breakout.py`. Sep 2018 - Oct 2026.
H4 + H1 trend (EMA50) -> M15 20-bar breakout stop order, stop at the 10-bar opposite extreme, 3R, no entries 08:00-09:30 NY
or on FOMC afternoons.
| Version | Trades/yr | Win % | Mean R | t | Halves |
|---|---|---|---|---|---|
| XAUUSD primary (3R) | 216 | 28.8 | +0.023 | +0.58 | -0.005 / +0.050 |
| XAUUSD 2x spread | 209 | 27.5 | -0.041 | -1.04 | |
| XAUUSD 2R / 1R | 258 / 357 | 34.7 / 47.4 | +0.007 / -0.051 | +0.24 / -2.74 | |
| XAUUSD without news filter | 228 | 28.2 | +0.009 | +0.23 | |
| XAUUSD H4 only (no H1 check) | 238 | 27.9 | +0.012 | +0.30 | |
| NAS100 primary | 207 | 28.3 | +0.008 | +0.19 | |
| EURUSD primary | 215 | 26.0 | -0.109 | -2.93 | |
About break-even before financing, nothing after doubled costs. The news filter and the H1 check each add ~0.01R: noise.
EMBER (gold, daily breakout) on the same data: +0.052R, z 2.8 — the simpler daily version is the one with an edge.
