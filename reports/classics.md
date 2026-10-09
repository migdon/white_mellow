# Classic strategies (pre-registered, bot_audit/classics.py), daily bars 2012–2026, tradable prices

| Strategy | Market | Trades | Win | Total (1x) | Sharpe | t | Max DD (1x) |
|---|---|---|---|---|---|---|---|
| RSI(2) long | SPX500 | 132 | 73% | +78.5% | 0.70 | 2.67 | −17.6% |
| RSI(2) long | NAS100 | 120 | 62% | +58.3% | 0.43 | 1.63 | −16.3% |
| **RSI(2) pooled** | | 252 | | | 0.61 | **2.37** | **PASS** |
| Turtle 20/10 | SPX, NAS, gold, BTC | 441 | 31–37% | mostly negative | −0.04 | −0.17 | **FAIL** (drawdowns 59–126%) |

RSI(2) trades about 9 times a year per index. It holds a few days and earns small per trade.
It is not yet combined with NBRO + EMBER in the Atlas replay.
