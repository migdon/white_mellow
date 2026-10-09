# Trap / inducement (liquidity sweep reversal) — FAIL, strongly

Protocol: `bot_audit/PROTOCOL_TRAP.md`. Code: `bot_audit/trap.py`. M5, Sep 2018 - 2026, 2R target.
| Market | Asian-range sweep: win % / mean R (t) | Previous-day H/L sweep: win % / mean R (t) |
|---|---|---|
| NAS100 | 28% / -0.16 (-6.4) | 31% / -0.09 (-2.6) |
| XAUUSD | 24% / -0.30 (-12.0) | 29% / -0.18 (-5.1) |
| EURUSD | 27% / -0.21 (-8.6) | 27% / -0.23 (-6.9) |
| GBPUSD | 27% / -0.22 (-8.8) | 27% / -0.22 (-6.7) |
| USDJPY | 28% / -0.18 (-6.7) | 28% / -0.18 (-5.0) |
1R and 3R targets and M15 bars (previous-day level) lose too. (M15 with the Asian range made no trades: the code asks for
30 bars in the range and M15 has 28 — not fixed, the M5 result already decides it.)
A 2R target needs ~34% winners after costs; the sweeps won 24-31%. Price that runs a level and closes back inside more often
goes on to break it again than reverses — the same direction as the breakout edges in NBRO / EMBER.
