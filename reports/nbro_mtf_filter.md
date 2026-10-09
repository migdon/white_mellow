# NBRO + multi-timeframe trend filter — makes it WORSE

Screen on NBRO's own trades (Vantage 2018-2026): trend = last COMPLETED bar's close vs its EMA50 on H1 / H4 / D1, at entry time.
| Filter | NAS100: trades, win %, mean, total | SPX500: trades, win %, mean, total |
|---|---|---|
| none (current NBRO) | 1427, 44%, +0.069%, **+98%** | 1464, 44%, +0.036%, **+53%** |
| with H1 trend only | 1103, 45%, +0.069%, +76% | 1129, 44%, +0.030%, +34% |
| with H4 trend only | 851, 46%, +0.058%, +49% | 868, 45%, +0.025%, +22% |
| with D1 trend only | 734, 46%, +0.055%, +40% | 770, 45%, +0.021%, +16% |
| H1 + H4 + D1 all agree | 586, 46%, +0.046%, +27% | 600, 46%, +0.001%, +1% |
| AGAINST the D1 trend | 693, 41%, +0.083%, +57% | 694, 42%, +0.053%, +37% |
Aligned trades win slightly more often (45-46% vs 44%) but earn less; NBRO's trades against the higher-timeframe trend are
as good or better (turning days). Every filter cuts the total. No filter added.

## Same screen on EMBER gold and ORB (trend = last completed bar vs EMA50)
| | All | with H1 | with H4 | with D1 |
|---|---|---|---|---|
| EMBER gold | 579, +0.052R, z 2.77, +30R | 538, +0.047R, +25R | 395, +0.059R, +23R | 301, +0.071R, z 2.67, +21R |
| ORB EURUSD short (current exit) | 1990, -0.026R, -51R | -0.018R, -21R | -0.026R, -27R | -0.018R, -19R |
| ORB USDJPY long (current exit) | 2112, +0.011R, +24R | +0.033R, z 1.4, +43R | +0.039R, z 1.6, +47R | +0.025R, +31R |
EMBER: the filters raise the edge per trade a little but cut the total; on Atlas the D1 version did not pass faster (ember_expand.md).
ORB: EURUSD stays negative under every filter; USDJPY improves to z 1.4-1.6, still not significant across this many tries,
and it is the same long-USDJPY drift seen in orb_exits.md. No change to either bot.
