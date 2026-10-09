# Protocol — FVG -> IFVG (inversion fair value gap), written BEFORE running

Rules (ICT-style, made exact), M5 bars, server time = NY + 7:
1. FVG: bullish if low[i] > high[i-2] (zone high[i-2]..low[i]); bearish if high[i] < low[i-2]. Size >= 0.25 x ATR14(M5).
   An FVG stays "live" for 24 bars (2 hours) after it forms.
2. Inversion: a bar CLOSES beyond the far side of a live FVG, against it (bullish FVG closed below its bottom -> SELL;
   bearish FVG closed above its top -> BUY). Each FVG can trigger once.
3. Entry: next bar's open. Stop: the extreme (highest high for a sell / lowest low for a buy) from the FVG's first candle
   to the inversion bar. Target 2R.
4. Only entries 08:00-12:00 New York (London close / NY morning kill zone). One trade at a time, max 2 a day,
   anything open closed at 16:00 New York. Same bar touches stop and target -> loss.
Costs: bid data + spread (NAS100 1.7, XAUUSD 0.45, EURUSD 0.00012). Data Sep 2018 - 2026.

PASS (per market): mean net R > 0 with t >= 2.4 (Bonferroni over 3 markets), both halves > 0, still > 0 at 2x spread.
Information only, cannot rescue a FAIL: target 1R / 3R, all hours, entry on a retest of the IFVG zone (limit, 6 bars), M15 bars.
