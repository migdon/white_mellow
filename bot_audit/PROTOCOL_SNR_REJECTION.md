# Protocol — "simplified" S/R rejection strategy (30m, 1R against trend / 2R with trend)

Source: a Filipino trading-class video the user shared (gold, 30-minute chart). Written BEFORE running anything.

## Mechanical version of the rules (the video's discretionary parts made exact)
On 30-minute bars built from M5 (server time); M5 is used only to resolve fills, stops and targets.
1. **Rejection area (S/R zone)**: a confirmed swing low / high (fractal, 3 bars each side, known 3 bars later)
   from the last 5 days (240 bars). Zone = level ± 0.3 x ATR14(30m).
2. **Leg**: >= 3 consecutive "clean momentum" candles in one direction right before the reversal candle:
   body >= 50% of range, each close beyond the previous close (no pullback).
3. **Reversal candle**: the next 30m candle closes the other way (bullish after a down leg, bearish after an up leg),
   and the leg's extreme (incl. the reversal candle) is inside a zone confirmed before the leg started.
4. **Entry**: stop order at the reversal candle's high (buy) / low (sell), valid only during the next 30m candle.
5. **Stop**: the leg's extreme (wick). **Target**: 2R if the trade is with the trend (30m close vs EMA200), else 1R.
6. One position at a time, max 3 trades a day, **after a loss no more trades that day** (the video's rule).
   Same M5 bar touches stop and target -> counted as a loss. Unfinished after 24h -> closed at market.
Costs: bid data + spread on every round trip (gold 0.45, NAS100 1.7, EURUSD 0.00012).

## Pass rule (fixed now)
Primary: XAUUSD, Sep 2018 - 2026. PASS if mean net R per trade > 0 with t >= 2.0, BOTH halves > 0,
and mean still > 0 with doubled spread. Secondary markets NAS100, EURUSD: same, Bonferroni t >= 2.4.
Variants (leg >= 4, zone 0.2/0.5 ATR, always 1R, always 2R, no stop-after-loss) are reported for information only;
they cannot turn a FAIL into a PASS.

## Addendum (2026-10-09, before running): can a POI / entry filter rescue it?
Six filters on the gold setups, each a reading of "stronger S/R" or "surer entry":
F1 level touched >= 2 times (2+ swing points inside the zone) · F2 leg extreme within 0.3 ATR of the previous server day's high/low ·
F3 entry during London/NY (server 10:00-23:00) · F4 reversal candle is a pin/hammer (wick on the rejection side >= 50% of range) ·
F5 reversal candle tick volume > 1.5x its 20-bar average · F6 leg extreme within 0.3 ATR of a $10 round number.
Screen: each filter keeps the subset of the primary trades it allows (the day/position sequence is not re-run).
A filter PASSES only with mean R > 0, t >= 2.64 (Bonferroni over 6), both halves > 0. Otherwise no filter is added.
