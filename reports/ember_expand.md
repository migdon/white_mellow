# EMBER on more markets + a trend filter

Protocol: `bot_audit/PROTOCOL_EMBER_EXPAND.md` (written before the run).

A. Unchanged EMBER on more FX (no swap counted):
| Pair | 2012-2026 | 2018-2026 | 2018-2026, 2x spread |
|---|---|---|---|
| EURUSD | -0.018R (z -1.4) | -0.001R (z -0.05) | -0.010R |
| GBPUSD | -0.030R (z -1.2) | -0.007R (z -0.4) | -0.015R |
FAIL: no edge on EURUSD or GBPUSD.

B. Only trades in the direction of the daily trend (prior close vs SMA50), 2018-2026:
| Market | All EMBER trades | With-trend only |
|---|---|---|
| XAUUSD | 579, +0.052R, z 2.77 | 295, +0.086R, z 3.18 (PASS the screen) |
| USDJPY | +0.017R, z 1.1 | +0.029R, z 1.2 |
| BTCUSD | +0.037R, z 1.4 | +0.070R, z 1.8 |
| EURUSD | -0.001R | -0.020R |
| GBPUSD | -0.007R | +0.022R, z 0.8 |
The filter raises gold's edge per trade but halves the number of trades. Atlas evaluation, NBRO 1% + gold:
all trades at 1% -> 46% in 1 month, 75% in 2, 96% in a year, 4% breached (current);
with-trend at 1.0% / 1.5% / 2.0% -> 45/71/95% 3%, 47/71/95% 4%, 49/72/93% 7%.
No gain for passing, so EMBER stays unchanged. (Screen on the existing trade list; a live filter would also free some days
for other trades — not modelled.)
"Top 5 crypto": only BTCUSD data here; other coins need an MT5 export to test.
