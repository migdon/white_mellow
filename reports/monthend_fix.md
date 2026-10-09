# Month-end London 4pm fix: result

**Data.** Vantage M5, Sep 2018 → Sep 2026, 95 month-ends (limited by the SP500 M5 history).
**Signal.** SPX month-to-date at 14:00 London. Positive → sell USD into the fix; negative → buy USD.
**Costs.** Each pair's own median spread at 14–16 London: about 1.2–1.3 pips.

| | n | Avg net | t | Win |
|---|---|---|---|---|
| **Pooled, 3 pairs (the test)** | 95 | −1.65 bp | −0.81 | 49% |
| First half | 47 | −4.33 bp | −1.36 | 40% |
| Second half | 48 | +0.96 bp | +0.38 | 58% |
| EURUSD (information only) | 95 | −2.48 bp | −0.98 | 49% |
| GBPUSD (information only) | 95 | +4.02 bp | +1.30 | 60% |
| USDJPY (information only) | 95 | −6.51 bp | −2.63 | 40% |
| Unconditional USD long into the fix (information only) | 95 | −4.00 bp | −1.99 | 43% |

**Verdict: FAIL.** The hedging-flow signal shows nothing in 2018–2026. Even before the spread, the average is near zero.
