# Classic strategies (pre-registered, bot_audit/classics.py), daily bars 2012–2026, tradable prices

| Strategy | Market | Trades | Win | Total (1x) | Sharpe | t | Max DD (1x) |
|---|---|---|---|---|---|---|---|
| RSI(2) long | SPX500 | 132 | 73% | +78.5% | 0.70 | 2.67 | −17.6% |
| RSI(2) long | NAS100 | 120 | 62% | +58.3% | 0.43 | 1.63 | −16.3% |
| **RSI(2) pooled** | | 252 | | | 0.61 | **2.37** | **PASS** |
| Turtle 20/10 | SPX, NAS, gold, BTC | 441 | 31–37% | mostly negative | −0.04 | −0.17 | **FAIL** (drawdowns 59–126%) |

RSI(2) trades about 9 times a year per index. It holds a few days and earns small per trade.
It is not yet combined with NBRO + EMBER in the Atlas replay.

## RSI(2) < 20 on FX, gold, BTC (pre-registered; A = long only, B = long + short at 80; PASS t >= 2.7, family of 10)

| Market | A: t | A: total | B: t | B: total |
|---|---|---|---|---|
| EURUSD | −0.71 | −8.4% | +0.20 | +4.1% |
| GBPUSD | −0.64 | −8.6% | −1.24 | −25.9% |
| USDJPY | +0.36 | +7.9% | +0.69 | +19.5% |
| XAUUSD | +0.49 | +16.5% | −0.92 | −38.5% |
| BTCUSD | +0.45 | +38.7% | −0.58 | −65.8% |

**0 of 10 pass.** RSI(2) works on US stock indices only (SPX500, NAS100), as the literature reports.
