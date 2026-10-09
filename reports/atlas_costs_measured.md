# Atlas costs measured on the user's account (measure_spread.py, 7 days of ticks, Oct 2026)

| Symbol | Median spread | Swap long / short | Used in the tests |
|---|---|---|---|
| BTCUSD | $66.86 (flat all day, 0.079% of price) | -15% / -15% a year (% of open price), triple on day 7 | $67, 15%/yr — matches |
| XAUUSD | $0.43 (0.40-0.48) | -66.3 / +29.92 points (= -$0.66 / +$0.30 per oz a night at $4,192), triple Wednesday | $0.45 spread, no swap |
| NAS100 | 1.87 | -3% / -1.5% a year | 1.7 (NBRO is flat every night, no swap) |
| SPX500 | 0.9 all day, 0.6-0.8 in NBRO's hours | — | 0.6 |

EMBER gold with the real swap (scaled to each trade's price; 2.8 rollovers a trade on average incl. the Wednesday triple):
+0.052R -> +0.046R a trade (z 2.77 -> 2.42), both halves still positive (+0.051 / +0.040). Longs pay ~0.018R, shorts earn ~0.007R.
Atlas evaluation, NBRO 1% + gold 1%: 46% in 1 month, 75% in 2, 83% in 3 (84% before), 96% in a year, 4% breached — unchanged.
BTC: cost exactly as assumed, so the earlier BTC verdicts stand (EMBER BTC +0.037R z 1.4 before its 15%/yr swap; not used).
