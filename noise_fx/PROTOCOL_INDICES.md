# NBRO → other stock indices: pre-registered protocol

Written **before** any of these indices' intraday data was looked at (2026-10-09). Goal: more trading days and
sessions outside the US (morning in the Philippines), without changing NBRO's rule.

## Rule: unchanged from `nbro_app.py`
- 14-session sigma, 30-minute checks from O+30 to O+360, X2 exit, close at O+385.
- Emergency stop 1.0%, the same as NBRO on NAS100 and SPX500.
- O = the cash-session open of each index, in its own timezone (DST handled):

| Index | Anchor (local) | Philippine time |
|---|---|---|
| JPN225 | 09:00 Asia/Tokyo | 08:00 |
| HK50 | 09:30 Asia/Hong_Kong | 09:30 |
| AUS200 | 10:00 Australia/Sydney | 07:00–08:00 |
| GER40 | 09:00 Europe/Berlin | 15:00–16:00 |
| UK100 | 08:00 Europe/London | 15:00–16:00 |

**Family = 5 tests.** NAS100 and SPX500 are NOT in the family; they are the engine check, run with NBRO's own
09:30 New York anchor.

## Costs
Spread in index points, once per round trip. No commission on index CFDs unless `--commission` is given.
- JPN225: 9 points, measured at Atlas (from `ember_app.py`).
- Assumed, to be replaced with measured values: HK50 8, AUS200 2, GER40 1.5, UK100 1.5.

## Split
Each market's history is cut at its midpoint date:
- **recent half** = discovery
- **older half** = confirmation

## Pass rule: all four must hold
1. Recent half: z ≥ 2.33 (Bonferroni one-sided 5% for 5 tests).
2. Older half: z ≥ 2.0, and the average trade is positive.
3. Full sample with doubled costs: average trade > 0.
4. At least 300 trades in the full sample.

**WEAK** = recent-half z ≥ 2.0 but fails another rule. A weak result is not traded.

## Already known before running
- Zarattini, Aziz and Barbon (2024) tested the idea on SPY only. Intraday momentum has been reported on several
  international indices, but weaker than in the US.
- NBRO's own result: confirmed on NAS100; SPX500 z 2.5; US30 failed.
- **Prior: modest.** Expect 0–2 passes.
