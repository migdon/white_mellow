# S/R rejection strategy (video, 30m, 1R/2R) — FAIL

Protocol: `bot_audit/PROTOCOL_SNR_REJECTION.md` (written before the run). Code: `bot_audit/snr_rejection.py`. Data Sep 2018 - 2026, M5 -> 30m.

| Market | Trades/yr | Win % | Mean R / trade | t | Halves | R per year |
|---|---|---|---|---|---|---|
| XAUUSD (primary) | 29 | 33.8 | -0.24 | -3.32 | -0.29 / -0.19 | -6.9 |
| XAUUSD, 2x spread | 29 | 30.3 | -0.33 | -4.69 | | -9.3 |
| XAUUSD, no spread at all | 29 | 40.8 | -0.07 | -0.89 | | -1.9 |
| NAS100 | 33 | 33.8 | -0.24 | -3.54 | -0.17 / -0.30 | -7.9 |
| EURUSD | 38 | 32.1 | -0.29 | -4.73 | -0.27 / -0.31 | -11.0 |

Gold variants (information only): with-trend 2R trades -0.23R, against-trend 1R trades -0.25R; leg >= 4 -0.38R;
zone 0.2 / 0.5 ATR -0.20 / -0.22R; always 1R -0.25R (win 38%); always 2R -0.16R; without "stop after a loss" -0.25R.
Every version loses. It loses even with zero spread, so the costs are not the cause.

Caveat: the video's zones and "clean candles" are judged by eye; this is one exact reading of them. A 1R target needs more than 50% winners
(more than ~55% after spread) to make money; the mechanical version wins 34-38%.
