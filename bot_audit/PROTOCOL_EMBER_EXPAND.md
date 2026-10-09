# Protocol — EMBER on more markets + a trend filter, written BEFORE running

A. Unchanged EMBER rule (bot_audit/ember_bt.py) on EURUSD (spread 0.00012) and GBPUSD (0.00015), Sep 2018 - 2026 and 2012 - 2026.
   PASS per pair: mean R > 0, z >= 2.24 (Bonferroni over 2), both halves > 0, > 0 at 2x spread.
B. "Trending" version: keep only trades in the direction of the daily trend (prior day's close vs SMA50 of prior closes),
   screened on the EMBER trade lists of XAUUSD, USDJPY, BTCUSD, EURUSD, GBPUSD (the position sequence is not re-run).
   PASS per market: z >= 2.6 (Bonferroni over 5) and better than unfiltered EMBER on the same market.
Swaps are not counted for FX (EMBER holds ~1 night); noted as a limitation.
"Top 5 crypto": no data here except BTCUSD — needs the user's MT5 export (ETH, SOL, XRP, ...), not tested.
