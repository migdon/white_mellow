# Month-end London 4pm fix: pre-registered protocol

Written **before** the FX data was opened (2026-10-09).

**Reference.** Melvin and Prins (2015), "Equity hedging and exchange rates at the London 4 p.m. fix". At month-end,
foreign holders of US equities re-hedge into the fix. When US stocks rose during the month they must sell USD, so the
USD weakens before the fix; when US stocks fell, the opposite.
The original signal is US minus foreign equity performance. Foreign index data are not in hand, so
**SPX month-to-date return alone** is used as the proxy.

## Rule
- **Day:** the last trading day of each month.
- **Signal:** SP500.r return from the previous month's last 16:00 London price to 14:00 London today.
  - Signal > 0 → sell USD: long EURUSD, long GBPUSD, short USDJPY.
  - Signal < 0 → buy USD.
- **Entry:** open of the 14:00 London bar.
- **Exit:** open of the 16:00 London bar (the fix).

## Costs
Each pair's own median `spread` column around 14:00–16:00 London, once per round trip.

## Test
- One test.
- Unit of observation: the average of the 3 pairs' net returns per month.
- **PASS needs all three:**
  1. average > 0,
  2. one-sided t ≥ 1.65,
  3. both halves of the sample positive.

## Reported for information only
- Each pair separately.
- The unconditional "USD into the fix" return.

**Prior: modest.** The effect is documented, but it is widely known and the proxy signal is weaker than the original.
