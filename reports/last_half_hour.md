# Market intraday momentum (last half hour) on NAS100 / SPX500 — FAIL

Protocol: `bot_audit/PROTOCOL_LAST_HALF_HOUR.md`. Code: `bot_audit/last_half_hour.py`. Vantage M5, Sep 2018 - Oct 2026, 2,008 days.
| Rule | NAS100 no cost | NAS100 net (spread 1.87) | SPX500 no cost | SPX500 net (spread 0.8) |
|---|---|---|---|---|
| R1 first 30 min -> last 30 min (Gao et al. 2018) | +0.9%/yr, t 0.5 | -2.7%/yr, t -1.5 | +1.3%/yr, t 0.8 | -3.5%/yr, t -2.2 |
| R2 rest of day -> last 30 min (Baltussen et al. 2021) | +3.3%/yr, t 1.9 | -0.3%/yr, t -0.2 | +3.0%/yr, t 1.9 | -1.9%/yr, t -1.2 |
R2 is positive before costs but only in 2018-2022 (second half negative even before costs); on the biggest-signal days NAS100 R2 is
+7.5%/yr net but t 1.2 and only in the first half. The effect the papers found up to 2013/2020 has faded, and a 25-minute hold
cannot pay a CFD spread. NBRO (the same authors' line of research, with entries across the whole day) remains the one that works.
