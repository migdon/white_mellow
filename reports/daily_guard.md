# Account daily-loss guard for NBRO + EMBER gold (Atlas evaluation replay)

Code: `bot_audit/daily_guard_test.py`. After the day's closed loss of both bots reaches the guard, later entries that day are skipped.
| Guard | Risk | Trades skipped (8 yrs) | 1 mo | 2 mo | 3 mo | 1 yr | Breach | Worst day (intraday, conservative) |
|---|---|---|---|---|---|---|---|---|
| none | 1% | 0 | 46% | 75% | 83% | 96% | 4% | -6.14% |
| **3% (current)** | 1% | 9 | 46% | 75% | 84% | 96% | **3%** | **-4.09%** |
| 2% | 1% | 38 | 45% | 74% | 82% | 94% | 5% | -3.70% |
| 1.5% | 1% | 67 | 45% | 73% | 82% | 94% | 6% | -3.28% |
| 3% | 0.75% | 4 | 34% | 60% | 75% | 96% | 2% | -3.98% |
The current 3% guard keeps the worst day under Atlas's 5% daily limit at no cost in speed. Tighter guards cut the worst day a little
but skip the trades that win back a bad morning, so MORE accounts end up breached (by the 10% trailing limit). Lower risk is the
way to fewer breaches, at the cost of speed. No change made.
