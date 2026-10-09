# EMBER rule on intraday periods (gold): pre-registered protocol

Written **before** running (2026-10-09). Goal: more trades per day on XAUUSD alone, without changing EMBER's rule.

## Rule: EMBER unchanged, with "day" replaced by a period P
- Periods are aligned to the broker's server midnight.
- **Levels:** the period's first-bar open ± 0.8 × ATR(10) of the 10 previous complete periods.
- **Entry:** the first level touched, as a stop order.
- **Stop:** 2 × ATR from the level.
- **Exit:** at the start of the second period after entry (EMBER's "close of the day after entry").
- One position at a time.

## Family: 2 tests
- **P = 8h** (3 periods a day)
- **P = 4h** (6 periods a day)

## Costs
- Gold spread $0.45, the top of the range measured at Atlas.
- Doubled-cost check at $0.90.
- Swap ignored. Most trades are shorter than a day, so overnight charges are rarer than in daily EMBER.

## Data
Vantage XAUUSD M5, Sep 2018 → Oct 2026.

## Pass rule: all must hold
1. Full sample z ≥ 2.33.
2. Both halves positive.
3. Average trade > 0 at $0.90 spread.
4. At least 300 trades.

## Prior
**Modest to low.** Intraday breakouts on FX failed earlier in this project, and the cost is a larger share of a smaller ATR.
