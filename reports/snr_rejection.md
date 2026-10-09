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

## POI / entry filters (gold, protocol addendum; pass needs t >= 2.64 and both halves > 0)
| Filter | Trades kept | Win % | Mean R | t |
|---|---|---|---|---|
| none | 228 | 34 | -0.24 | -3.3 |
| F1 level touched 2+ times | 109 | 36 | -0.21 | -2.0 |
| F2 at previous day's high/low | 23 | 30 | -0.35 | -1.6 |
| F3 London/NY hours only | 132 | 40 | -0.10 | -1.0 |
| F4 pin bar / hammer reversal | 41 | 32 | -0.24 | -1.4 |
| F5 volume spike on reversal | 54 | 30 | -0.35 | -2.5 |
| F6 near a $10 round number | 58 | 33 | -0.26 | -1.8 |
No filter passes; none turns the mean positive. London/NY hours cut the loss the most (the Asian-session setups lose -0.44R),
so snr_app.py got an optional --london-ny switch. Stronger-looking zones (more touches, previous-day levels, round numbers,
hammers, volume) did NOT win more often.

## The video's Fibonacci rule (addendum 2): FAIL, and it makes it worse
"Take it only if 1R fits inside the leg's 0.5 retracement":
| Gold version | Trades/yr | Win % | Mean R | t |
|---|---|---|---|---|
| strict leg + Fib 0.5 (new primary) | 5 | 26 | -0.46 | -2.85 |
| strict leg + Fib 0.618 | 9 | 34 | -0.25 | -1.90 |
| strict leg + Fib 0.5 + London/NY | 3 | 36 | -0.23 | -1.00 |
| loose leg (3 of 4 candles, >= 1.5 ATR), zone 0.5 | 234 | 38 | -0.14 | -5.48 |
| loose leg + Fib 0.5 | 38 | 32 | -0.30 | -5.02 |
| loose leg + Fib 0.5 + London/NY | 23 | 36 | -0.22 | -2.78 |
NAS100 strict + Fib 0.5: -0.25R (t -2.1); EURUSD: -0.49R (t -4.1).
The Fib rule keeps the trades whose stop is small next to the leg, and small stops are hit by ordinary noise more often.
