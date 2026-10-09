# Protocol — "Multi-Timeframe Trend-Following + Breakout + News Filter" on XAUUSD (from a ChatGPT write-up), BEFORE running

Bars from M5, server time = NY + 7. Trend: last COMPLETED bar close vs EMA50 on that timeframe.
1. H4 trend gives the direction; H1 trend must agree. Otherwise no trade.
2. M15 entry, breakout: buy stop at the highest high of the last 20 completed M15 bars (sell stop at the lowest low),
   re-placed every M15 bar while the trend holds; it fills when an M5 bar trades through it.
3. Stop: lowest low (buy) / highest high (sell) of the last 10 completed M15 bars. Target 3R (the write-up's 1:3).
4. News filter: no entries 08:00-09:30 New York (US 08:30 releases) and none after 12:00 New York on FOMC statement days.
5. One trade at a time, max 2 entries a day; a trade still open after 3 days is closed. Same bar stop+target -> loss.
Costs: spread $0.45 per round trip; financing not counted (noted). Data Sep 2018 - Oct 2026.
PASS: mean net R > 0 with t >= 2.0, both halves > 0, > 0 at 2x spread.
Information only: 2R / 1R target, no news filter, H4 only (no H1 check), the same rule on NAS100 / EURUSD.
