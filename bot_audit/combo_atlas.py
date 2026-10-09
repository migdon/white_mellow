"""
One Atlas Access account running NBRO (NAS100 + SPX500, intraday) AND EMBER (gold, optionally USDJPY; held overnight).

Daily book in % of the account, built per bot and added with each bot's worst moments assumed simultaneous:
  NBRO: from noise_fx.atlas_sim.daily_book (fraction of notional; notional = risk% / 1% stop)
  EMBER: from bot_audit.ember_atlas.daily_marks (R; % of account = R x risk%)
Dates: NBRO uses the UTC day, EMBER the broker server day (they differ by 2-3 hours; same calendar date used).
"""

import numpy as np
import pandas as pd

from bot_audit import ember_atlas as E
from bot_audit.ember_bt import load_server_m5
from noise_fx import atlas_sim as A


def nbro_book(trades_csv):
    tr = pd.read_csv(trades_csv, parse_dates=["utc_day"])
    tr["utc_day"] = tr["utc_day"].dt.date
    b = A.daily_book(tr)
    b.index = pd.to_datetime(b.index)
    return b                                    # ret, open, low, high per 1x notional


def ember_marks(m5_csv, trades_csv, spread):
    m5 = load_server_m5(m5_csv)
    t = pd.read_csv(trades_csv, parse_dates=["entry_time", "exit_time"])
    mk = E.daily_marks(m5, t, spread)
    mk.index = pd.to_datetime(mk.index)
    return mk                                   # realized, unreal_eod, low, high, open_min in R


def combine(nb, nbro_risk, embers):
    """embers: list of (marks, risk%). Returns the ember_atlas-style book in % of the account."""
    idx = nb.index
    for m, _ in embers:
        idx = idx.union(m.index)
    start = max([nb.index.min()] + [m.index.min() for m, _ in embers])
    idx = pd.bdate_range(start, idx.max())
    out = pd.DataFrame(0.0, index=idx, columns=["realized", "unreal_eod", "low", "high", "open_min"])
    n = nb.reindex(idx).fillna(0.0) * nbro_risk * 100        # notional = risk (1.0% -> 1x)
    out["realized"] += n["ret"]
    out["low"] += n["low"]
    out["high"] += n["high"]
    out["open_min"] += n["open"]
    for m, r in embers:
        e = m.reindex(idx).fillna(0.0) * r
        for c in out.columns:
            out[c] += e[c]
    return out


def run_grid(nb, emb_list, label, nbro_risks, ember_risks, fund=None):
    print(f"\n=== {label}")
    print(f"{'NBRO/idx':>8}{'EMBER':>7}{'pass<=21d':>10}{'pass<=1y':>9}{'breach':>8}{'med days':>9}")
    for nr in nbro_risks:
        for er in ember_risks:
            book = combine(nb, nr, [(m, er) for m in emb_list])
            starts = range(0, len(book) - 300, 5)
            r21 = [E.simulate(book, s, 1.0, 1.0, eval_cap=21) for s in starts]       # book already in %, k = 1/100
            r1y = [E.simulate(book, s, 1.0, 1.0) for s in starts]
            P = [x for x in r1y if x["passed"]]
            print(f"{nr:>7.2f}%{er:>6.2f}%{np.mean([x['passed'] for x in r21]):>10.2f}{len(P) / len(r1y):>9.2f}"
                  f"{np.mean([x.get('breach', False) for x in r1y]):>8.2f}{np.median([x['ev_days'] for x in P]) if P else float('nan'):>9.0f}")


if __name__ == "__main__":
    import sys
    S = sys.argv[1]
    nb = nbro_book(f"{S}/realdata/nbro_trades.csv")
    gold = ember_marks(f"{S}/gold/unz/XAUUSD_M5.csv", f"{S}/ember_XAUUSD.csv", 0.45)
    jpy = ember_marks(f"{S}/fx/USDJPY_M5.csv", f"{S}/ember_USDJPY.csv", 0.005)
    run_grid(nb, [gold], "3 markets: NAS100 + SPX500 (NBRO) + gold (EMBER)", (0.5, 0.75, 1.0), (0.5, 0.75, 1.0))
    run_grid(nb, [gold, jpy], "4 markets: + USDJPY (EMBER)", (0.5, 0.75, 1.0), (0.5, 0.75, 1.0))
