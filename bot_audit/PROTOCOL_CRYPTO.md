# Protocol — published crypto strategies on BTCUSD, written BEFORE running

Data: Vantage BTCUSD M5 2018-2026 (server time = NY + 7). Costs: Atlas BTC spread ~$67 at ~$95k -> 0.07% of price per
round trip; financing 0.041% per night held (~15%/yr), long or short.
R1 Weekly time-series momentum (Liu & Tsyvinski 2021, "Risks and Returns of Cryptocurrency"): every 7 days, long for the next
   7 days if the past 7-day return > 0, else flat. Variant (info): short instead of flat.
R2 Intraday time-series momentum (Shen, Urquhart & Wang 2022): sign of the 00:00-00:30 UTC return -> same-direction position
   from 23:30 to 24:00 UTC that day.
R3 Trend filter: long while the daily close > SMA(50) (decided on completed server days, traded next open), else flat.
PASS: mean daily (R1, R3) or per-trade (R2) net return > 0 with t >= 2.5 (Bonferroni over 3), both halves > 0, > 0 at 2x cost.
