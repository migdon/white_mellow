# Protocol — trap / inducement (liquidity sweep reversal), written BEFORE running

Idea: price runs the stops above a known high (or below a known low), the breakout traders are "trapped",
price closes back inside -> trade the other way. M5 bars, server time = NY + 7.
Two liquidity levels, tested separately:
  T1 Asian range: high/low of server 02:00-09:00 (NY 19:00-02:00). Sweeps traded 02:00-12:00 NY (server 09-19).
  T2 Previous day's high/low (server day). Sweeps traded 02:00-12:00 NY.
Trap: a bar trades beyond the level, and within 3 bars of that first breach a bar CLOSES back inside the level.
Entry: next bar's open, the other way. Stop: the sweep's extreme (wick). Target 2R. Max 1 trade per level side,
2 a day, one at a time, closed at 16:00 NY. Same bar touches stop and target -> loss.
Markets: NAS100 (1.7), XAUUSD (0.45), EURUSD (0.00012), GBPUSD (0.00015), USDJPY (0.008). Sep 2018 - 2026.
PASS: mean net R > 0 with t >= 2.8 (Bonferroni over 10 market x level tests), both halves > 0, > 0 at 2x spread.
Information only: 1R / 3R target, M15 bars.
