# Pre-FOMC drift: pre-registered protocol

Written **before** running (2026-10-09).

**Reference.** Lucca and Moench (2015), "The Pre-FOMC Announcement Drift": US stocks rise in the 24 hours before a
scheduled FOMC announcement. Later work reports the drift weakened after 2015. **Prior: modest.**

## Rule
- Buy SP500.r at the open of the 14:00 New York bar on the trading day before each SCHEDULED announcement.
- Sell at the open of the 13:55 New York bar on announcement day, five minutes before the 14:00 release.
- Unscheduled moves (3 and 15 Mar 2020) are excluded.

## Costs
- Spread: 0.6 points, once per round trip (Vantage median).
- Overnight financing: 0.02% of notional for the one night held.

## Sample and control
- **Sample:** every scheduled meeting from Sep 2018 to Sep 2026 (the extent of the M5 data), about 64 events.
- **Control:** the same 14:00 → 13:55 window on every other day.

## Pass rule: both must hold
1. The FOMC-window average net return is > 0, with one-sided t ≥ 1.65.
2. It is larger than the control-window average.

NAS100 is reported for information only; it is not part of the pass rule.
