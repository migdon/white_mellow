# One Atlas Access account: NBRO (NAS100 + SPX500) + EMBER (gold)

**Data.** Real trades of both bots on Vantage M5, Sep 2018 → Oct 2026.
**Script.** `bot_audit/combo_atlas.py`.
**Conservative assumption.** Each bot's worst intraday moment happens at the same time.

## Evaluation (+3%, 10% trailing, 5% daily)

| NBRO/index | EMBER gold | Pass ≤ 21 trading days | Pass ≤ 1 year | Breach | Median days |
|---|---|---|---|---|---|
| 0.5% | 0.5% | 0.17 | 0.97 | 0.01 | 53 |
| 0.75% | 0.75% | 0.35 | 0.96 | 0.02 | 31 |
| **1.0%** | **1.0%** | **0.46** | **0.96** | **0.04** | **22** |

Adding USDJPY (EMBER) as a 4th market at 1%/1%: 0.49 / 0.95 / 0.05 / 20 days. It adds little.

## Funded (6% trailing, 3% daily, Protector, payout rule), after passing at 1%/1%

| NBRO/index | EMBER gold | Alive after 1 year | Payouts/yr | $/yr on $50k |
|---|---|---|---|---|
| **0.25%** | **0.5%** | **1.00** | **1.8** | **~2,000** |
| 0.35% | 0.5% | 0.83 | 2.6 | ~3,260 |
| 0.5% | 0.75% | 0.52 | 2.8 | ~4,650 (half the accounts die) |

The Protector was never reached. Running both bots together roughly doubles the payouts each bot gets alone, because
more days close with ≥ +0.5%.
