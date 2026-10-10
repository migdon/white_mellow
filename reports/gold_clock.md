# Gold "around the clock" (Copenhagen Business School thesis) — FAIL

Protocol: `bot_audit/PROTOCOL_GOLD_CLOCK.md`. Code: `bot_audit/gold_clock.py`. Vantage XAUUSD M5, Sep 2018 - Oct 2026, 2,014 days.
| Rule | No cost | With Atlas spread $0.43 | 2x spread | Halves (net) |
|---|---|---|---|---|
| G1 long Asia session (01:05-10:00 server) | +0.029%/day, t 2.42 (+7.3%/yr) | +0.007%/day, t 0.61 (+1.8%/yr) | -0.014%/day | -0.017 / +0.031 |
| G2 short London + NY (10:00-23:50) | -0.007%/day, t -0.32 | -0.028%/day, t -1.38 | -0.050%/day | -0.024 / -0.033 |
The Asia-session rise is real before costs (t 2.4) but the daily spread eats ~75% of it, and it is all in 2024-2026 (gold +44% in 2025);
2018-2022 lose. The "falls the rest of the day" half does not exist in 2018-2026 (shorting it loses). Not usable at Atlas.
