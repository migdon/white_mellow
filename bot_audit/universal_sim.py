"""
NBRO solo on generic prop-firm rules, with the AUTO risk formula of nbro_app.py --firm-daily/--firm-max:
    evaluation risk per index = min(daily/5, max/10) x 1.0 % (capped 1.0; x0.85 when the max loss trails)
    funded risk               = half of that
Replays NBRO's real trades (same daily book as noise_fx/atlas_sim.py; conservative intraday paths).

    python -m bot_audit.universal_sim --trades nbro_trades.csv
"""
import argparse

import numpy as np
import pandas as pd

from noise_fx import atlas_sim as A


def auto_risk(daily, maxdd, trailing, funded):
    r = min(daily / 5.0, maxdd / 10.0, 1.0)
    if trailing:
        r *= 0.85
    if funded:
        r *= 0.5
    return round(r, 2)


def run_eval(ret, low, high, n, daily, maxdd, trailing, target, cap=504):
    out = []
    for s in range(0, n - 60, 5):
        bal, hwm, i, d, st = 1.0, 1.0, s, 0, "timeout"
        while i < n and d < cap:
            floor = (hwm if trailing else 1.0) - maxdd
            if bal * (1 + low[i]) <= floor or bal * low[i] <= -daily:
                st = "breach"; break
            if trailing:
                hwm = max(hwm, bal * (1 + high[i]))
            bal *= 1 + ret[i]; i += 1; d += 1
            hwm = max(hwm, bal)
            if target and bal >= 1 + target:
                st = "pass"; break
        out.append((st, d))
    return out


def run_funded(ret, low, high, n, daily, maxdd, trailing, length=252):
    alive, paid = [], []
    for s in range(0, n - length, 5):
        bal, hwm, p, ok = 1.0, 1.0, 0.0, True
        for k in range(length):
            i = s + k
            floor = (hwm if trailing else 1.0) - maxdd
            if bal * (1 + low[i]) <= floor or bal * low[i] <= -daily:
                ok = False; break
            if trailing:
                hwm = max(hwm, bal * (1 + high[i]))
            bal *= 1 + ret[i]
            hwm = max(hwm, bal)
            if (k + 1) % 14 == 0 and bal > 1:
                p += bal - 1; bal = 1.0; hwm = 1.0
        alive.append(ok); paid.append(p)
    return np.mean(alive) * 100, np.mean(paid) * 100


RULESETS = [  # name, daily %, max %, trailing, eval targets %
    ("2-Step 5/10 static (FTMO, FundedNext, FundingPips, The5ers type)", 5, 10, False, [8, 5]),
    ("2-Step 5/10 static, 10% first phase", 5, 10, False, [10, 5]),
    ("Lite 4/8 static", 4, 8, False, [8, 4]),
    ("1-Step 3/6 static", 3, 6, False, [10]),
    ("1-Step 4/6 trailing", 4, 6, True, [10]),
    ("1-Step 5/10 trailing, +3% (Atlas Access type)", 5, 10, True, [3]),
    ("1-Step 3/4 trailing (instant-type tight)", 3, 4, True, [8]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default="nbro_trades.csv")
    a = ap.parse_args()
    tr = pd.read_csv(a.trades, parse_dates=["utc_day"])
    tr["utc_day"] = tr["utc_day"].dt.date
    book = A.daily_book(tr)
    days = A.all_days(tr)
    R = book.reindex(days).fillna(0.0)
    n = len(days)
    for name, daily, maxdd, trailing, targets in RULESETS:
        r = auto_risk(daily, maxdd, trailing, False)
        ret, low, high = (R[c].values * r for c in ("ret", "low", "high"))
        # chain the phases: each phase is a fresh account starting where the previous one passed
        res = None
        for t in targets:
            ph = run_eval(ret, low, high, n, daily / 100, maxdd / 100, trailing, t / 100)
            if res is None:
                res = ph
            else:   # approximate: phase 2 from the same start (independent draw), add days
                res = [(x[0] if x[0] != "pass" else y[0], x[1] + y[1]) for x, y in zip(res, ph)]
        st = np.array([x[0] for x in res]); dd = np.array([x[1] for x in res])
        p = lambda k: np.mean((st == "pass") & (dd <= k)) * 100
        fr = auto_risk(daily, maxdd, trailing, True)
        alive, paid = run_funded(*(R[c].values * fr for c in ("ret", "low", "high")), n, daily / 100, maxdd / 100, trailing)
        print(f"{name}\n   eval auto risk {r}%: pass 3m {p(63):3.0f}%  6m {p(126):3.0f}%  1y {p(252):3.0f}%  "
              f"breach {np.mean(st == 'breach') * 100:3.0f}%\n   funded auto risk {fr}%: alive 1y {alive:3.0f}%  "
              f"profit {paid:.1f}% of size a year")


if __name__ == "__main__":
    main()
