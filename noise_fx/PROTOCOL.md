# NBRO → FX: pre-registered protocol

Written **before** any FX intraday data was looked at (2026-10-09). Nothing below may be changed after the
first run; a change means a new protocol with a new family count.

## Hypothesis
The Noise-Area intraday momentum rule that NBRO trades on NAS100 and SPX500 also works on liquid FX pairs,
anchored to a session open.

## Rule: unchanged from `nbro_app.py`
14-session sigma, 30-minute checks from O+30 to O+360, X2 exit, close at O+385, re-entry at a later check allowed.
The only FX-specific setting is the emergency stop: **0.5% of entry**. NBRO uses 1.0% on indices, and FX
daily moves are about half as large.
`noise_fx/tests/test_equivalence_nbro.py` checks that the engine makes exactly the trades NBRO's own functions make.

## Family: 9 pairs × 2 anchors = 18 tests
- Pairs: EURUSD, GBPUSD, USDJPY, USDCAD, AUDUSD, USDCHF, NZDUSD, EURJPY, GBPJPY
- Anchors:
  - **NY 08:00** (America/New_York): the FX volume peak; US data at 08:30
  - **LDN 08:00** (Europe/London): the London open

## Costs
- Spread in pips, charged once per round trip (MT5 data are BID).
- Atlas spreads measured at the US open (from `orb_app.py`): EURUSD 0.4, GBPUSD 0.5, USDJPY 0.5, USDCAD 0.5.
- Not yet measured, so assumed: AUDUSD 0.6, USDCHF 0.8, NZDUSD 1.0, EURJPY 1.0, GBPJPY 1.5.
- Commission: $7 per 100k round trip (0.007%), unless `--commission` is given.

## Split
Each pair's history is cut at its midpoint date:
- **recent half** = discovery
- **older half** = confirmation

## Pass rule: all four must hold
1. Recent half: z ≥ 2.8. This is about a Bonferroni one-sided 5% for 18 tests (0.05/18 → z 2.77).
2. Older half: z ≥ 2.0, and the average trade is positive.
3. Full sample with doubled spread and commission: average trade > 0.
4. At least 300 trades in the full sample.

**WEAK** = recent-half z ≥ 2.0 but fails another rule. A weak result is not traded.

z is a Newey-West t-stat on daily P&L, with every trading day counted (days without a trade = 0).

## Already known before running
- Most pairs move together through the USD. Two passing USD pairs are closer to one bet than two.
- Earlier FX work in this project (ORB, London breakout, about 130 intraday rules) found no edge.
  The prior is low: the expected number of passes by luck is about 0.05.
