"""
NBRO on FundedNext Stellar plans, replayed on NBRO's real trade history (same daily book as noise_fx/atlas_sim.py).

    python -m bot_audit.fundednext_sim --trades nbro_trades.csv

Rules (third-party summaries, Sep 2026 -- confirm on fundednext.com):
  2-Step  phase 1 +8%, phase 2 +5%; daily 5%, max loss 10% static; funded 5% / 10%
  1-Step  +10%;                  daily 3%, max loss 6% static;  funded 3% / 6%
  Lite    phase 1 +8%, phase 2 +4%; daily 4%, max loss 8% static;  funded 4% / 8%
Daily loss = % of the start size, counted from the day's starting balance (NBRO is flat overnight).
Min 5 trading days per phase (2 for 1-Step). Funded: profit withdrawn every 14 trading days (balance back to start).
Every 5th trading day is a start date; evaluation capped at 1 year, funded 1 year. Conservative intraday paths (sum of MAE).
"""
import argparse

import numpy as np
import pandas as pd

from noise_fx import atlas_sim as A

PLANS = {"2step": {"targets": [8, 5], "daily": 5, "maxdd": 10, "mindays": 5},
         "1step": {"targets": [10], "daily": 3, "maxdd": 6, "mindays": 2},
         "lite": {"targets": [8, 4], "daily": 4, "maxdd": 8, "mindays": 5}}


def phase(ret, low, traded, i, n, target, daily, maxdd, mindays, cap=252):
    bal, d, tdays = 1.0, 0, 0
    while i < n and d < cap:
        if bal * (1 + low[i]) <= 1 - maxdd or bal * low[i] <= -daily:
            return "breach", d + 1, i
        bal *= 1 + ret[i]
        tdays += traded[i]
        i += 1; d += 1
        if bal >= 1 + target and tdays >= mindays:
            return "pass", d, i
    return "timeout", d, i


def funded(ret, low, i, n, daily, maxdd, length=252):
    bal, paid, d = 1.0, 0.0, 0
    while i < n and d < length:
        if bal * (1 + low[i]) <= 1 - maxdd or bal * low[i] <= -daily:
            return paid, True
        bal *= 1 + ret[i]
        i += 1; d += 1
        if d % 14 == 0 and bal > 1:
            paid += bal - 1; bal = 1.0
    return paid, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default="nbro_trades.csv")
    ap.add_argument("--risks", type=float, nargs="*", default=[0.5, 0.75, 1.0, 1.25])
    ap.add_argument("--funded-risks", type=float, nargs="*", default=[0.35, 0.5, 0.75])
    a = ap.parse_args()
    tr = pd.read_csv(a.trades, parse_dates=["utc_day"])
    tr["utc_day"] = tr["utc_day"].dt.date
    book = A.daily_book(tr)
    days = A.all_days(tr)
    R = book.reindex(days).fillna(0.0)
    traded = R.index.isin(book.index).astype(int)
    n = len(days)
    starts = range(0, n - 60, 5)
    for name, p in PLANS.items():
        print(f"\n=== Stellar {name}: targets {p['targets']}%  daily {p['daily']}%  max {p['maxdd']}% static")
        for r in a.risks:
            ret, low = R["ret"].values * r, R["low"].values * r
            res = []
            for s in starts:
                i, tot, ok = s, 0, True
                for t in p["targets"]:
                    st, d, i = phase(ret, low, traded, i, n, t / 100, p["daily"] / 100, p["maxdd"] / 100, p["mindays"])
                    tot += d
                    if st != "pass":
                        ok = False; break
                res.append((ok, st if not ok else "pass", tot))
            ok = np.array([x[0] for x in res]); br = np.array([x[1] == "breach" for x in res])
            dd = np.array([x[2] for x in res])
            within = lambda k: np.mean(ok & (dd <= k)) * 100
            med = np.median(dd[ok]) if ok.any() else float("nan")
            print(f"  risk {r:.2f}%/index: pass 1m {within(21):3.0f}%  3m {within(63):3.0f}%  6m {within(126):3.0f}%"
                  f"  all {ok.mean()*100:3.0f}%  breached {br.mean()*100:3.0f}%  median {med:.0f} trading days")
        for r in a.funded_risks:
            ret, low = R["ret"].values * r, R["low"].values * r
            out = [funded(ret, low, s, n, p["daily"] / 100, p["maxdd"] / 100) for s in starts if s + 252 <= n]
            paid = np.array([o[0] for o in out]); br = np.array([o[1] for o in out])
            print(f"  FUNDED risk {r:.2f}%: alive after 1y {100-br.mean()*100:3.0f}%  avg profit/yr {paid.mean()*100:.1f}% of size"
                  f"  (median {np.median(paid)*100:.1f}%)")


if __name__ == "__main__":
    main()
