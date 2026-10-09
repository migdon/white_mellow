# NBRO rule → XAUUSD: pre-registered protocol

Written **before** the gold intraday data was run (2026-10-09).

## Rule: unchanged from `nbro_app.py`
14-session sigma, 30-minute checks from O+30 to O+360, X2 exit, close at O+385, emergency stop 1.0%.

## Family: 2 anchors
- **COMEX 08:20 New York**: gold futures open.
- **NYSE 09:30 New York**: same anchor as NBRO.

## Costs
- Spread: median of the file's own `spread` column during 08:00–16:00 New York, once per round trip.
- No commission.

## Split
The history is cut at its midpoint date:
- **recent half** = discovery
- **older half** = confirmation

## Pass rule: all four must hold
1. Recent half: z ≥ 2.33.
2. Older half: z ≥ 2.0, and the average trade is positive.
3. Full sample with doubled spread: average trade > 0.
4. At least 300 trades in the full sample.

## Already known before running
EMBER's Crabel breakout on gold was weak at Atlas (+0.025R, z 1.2).
**Prior: about 1 in 4.**
