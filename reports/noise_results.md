# NBRO rule — out-of-US tests (data: Vantage MT5 M5, run 2026-10-09)

## Engine check (NBRO's own markets, 09:30 New York)

| Market | Period | Trades | Avg/trade | Sharpe (1x) | z |
|---|---|---|---|---|---|
| NAS100.r | 2012-10 → 2026-10 | 1,427 | +0.074% | 0.96 | 4.33 |
| SP500.r | 2012-01 → 2026-10 | 1,464 | +0.039% | 0.66 | 2.99 |

NBRO's edge is confirmed on independent broker data with an independently written engine.
The engine reproduces nbro_app.py trade-for-trade on synthetic data.

## FX — PROTOCOL.md, family of 18

0 of 18 pass. Before costs every pair is ≈ 0 (−0.015% to +0.013% per trade); after 0.010–0.022% costs all are negative.

## Other indices — PROTOCOL_INDICES.md, family of 5

| Market | From | Trades | Avg/trade | z full | z recent | z older | Verdict |
|---|---|---|---|---|---|---|---|
| JPN225ft | 2022-12 | 627 | −0.034% | −1.66 | −0.99 | −1.42 | FAIL |
| SPI200.r (AUS200) | 2022-03 | 762 | −0.022% | −1.97 | −1.82 | −1.07 | FAIL |
| GER40.r | 2012-01 | 1,449 | −0.001% | −0.10 | −0.17 | 0.27 | FAIL |
| UK100.r | 2012-01 | 1,424 | −0.015% | −1.43 | −1.28 | −0.74 | FAIL |
| HK50.r | 2015-05 | — | — | — | — | — | NO DATA |

HK50 has no data under the unchanged rule: the lunch break removes the 12:00 and 12:30 HKT check bars, so no session
ever counts as complete.

**Verdict:** the rule works only on the US cash session. NBRO stays NAS100 + SPX500.
