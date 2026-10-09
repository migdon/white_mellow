# HACVD audit: the bot's own process_bar(), re-priced at tradable prices

**Data.** Vantage XAUUSD M5, Sep 2018 → Oct 2026. Each year is replayed separately, with the default settings.
**Script.** `bot_audit/hacvd_replay.py` drives hacvd_app.py's own `process_bar()` bar by bar.

| | Trades | As designed (HA close) | Real: next-bar open, $0.18 spread | Real: $0.45 spread (Atlas) |
|---|---|---|---|---|
| All | 12,288 | +0.312R (z +29) | **−0.088R (z −10.7)** | −0.06R to −0.39R per year, every year negative |
| Breakout | 4,009 | +0.377R | −0.057R | |
| Absorption | 8,279 | +0.280R | −0.103R | |

**Every year is negative at real prices,** 2018 through 2026 (−0.025R to −0.168R at $0.18).

## Decomposition (2026, 1,181 trades)

| Pricing | Avg/trade | z |
|---|---|---|
| HA close in and out (the bot's own bookkeeping) | +0.264R | +8.65 |
| HA close entry, real close exit | +0.153R | +4.60 |
| Real close, zero delay, zero spread | −0.030R | −0.96 |

On entry bars the Heikin-Ashi close, (O+H+L+C)/4, is on average 0.19R better than the real close. That gap is the
whole backtest edge. No live order can be filled at that price.

**Verdict:** no edge. Do not run it.
