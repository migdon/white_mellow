# Pre-FOMC drift on SP500.r: result

**Data.** Vantage M5, Sep 2018 → Sep 2026, 64 scheduled meetings.
**Window.** 14:00 New York the day before → 13:55 New York on announcement day.
**Costs.** 0.6 points spread and one night of financing.

| | n | Avg net | t | Win |
|---|---|---|---|---|
| FOMC window | 64 | +0.178% | +2.05 | 59% |
| Control (every other day) | 1,933 | +0.019% | | |
| NAS100 FOMC window (information only) | 64 | +0.314% | +2.49 | 59% |

**Pre-registered verdict: PASS, but narrowly.**

## Robustness checks, done after the verdict
- **Without 2022:** +0.081%, t 0.95. 2022 alone averaged +0.86%.
- **2023 onward:** +0.077%, t 0.73 (n 30). 2026 so far: −0.30%.
- **Placebo, same window one day earlier:** +0.151%, t 1.31. Almost as large, so the "FOMC-specific" part is small.
- **Median:** +0.105%. Worst −1.76%, best +2.13%, standard deviation 0.70% per event.

**Reading.** The result passes on paper, but it leans on one year and has faded the way the literature reports.
At most a small add-on, not a bot of its own.
