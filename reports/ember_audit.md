# EMBER: independent re-test and Atlas Access replay

**Data.** Vantage MT5 M5:
- XAUUSD from 2018-09
- USDJPY from 2012

**Costs.** Atlas-level spreads: gold $0.45, USDJPY 0.5 pip. USDJPY exits at 01:05 server time, as the bot does.
**Engine.** `bot_audit/ember_bt.py`, written independently of ember_app.py.

## Edge

| Market | Trades | Win | Avg/trade | z | Halves (z) |
|---|---|---|---|---|---|
| XAUUSD 2018–2026 | 579 | 54% | +0.052R | 2.77 | 2.17 / 1.75 |
| USDJPY 2012–2026 | 1,063 | 50% | +0.017R to +0.021R | 1.1–1.3 | 1.23 / 0.38 |

- **Gold** is positive in 8 of 9 years. 2019 and 2020, which predate the data EMBER was built on, are +0.10R and +0.07R.
- **USDJPY** does not reach the +0.048R (z 3.1) in EMBER's own notes.
- **Not included:** swap. It is about −0.01R per trade for gold longs and USDJPY shorts.

## Atlas Access (gold + USDJPY, 2018–2026, `bot_audit/ember_atlas.py`)

| Evaluation risk per trade | Pass | Breach | Median trading days |
|---|---|---|---|
| 1.0% | 0.82 | 0.00 | 74 |
| **1.5%** | **0.88** | **0.05** | **52** |
| 2.0% | 0.82 | 0.18 | 32 |

| Funded risk per trade | Alive after 1 year | Payouts/yr | $/yr on $50k |
|---|---|---|---|
| 0.5% | 1.00 | 0.6 | ~660 |
| **0.75%** | **1.00** | **0.7** | **~1,000** |
| 1.0% | 0.30 | 1.0 | ~1,870 (most accounts die) |

Gold alone gives evaluation 1.5% → pass 0.82, breach 0.04, 69 days, and funded 0.75% → ~$950/yr.

## Changes in `bots/ember_app.py` (EMBER-23)
- JPN225 removed.
- `--preset evaluation` = 1.5%.
- `--preset funded` = 0.75% (open-risk cap 1.5%, shield 1.7%).

**Caveat.** A position is open or closes on 88% of weekdays, but a trade closes on only ~0.3 days per market per day.
"Profit every day" is not something this, or any real edge, delivers.
