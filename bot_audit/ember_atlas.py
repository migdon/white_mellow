"""
Atlas 1-Step ACCESS replayed on EMBER's trades (from ember_bt.py), positions held overnight.

Per server day, per market, in R (multiply by risk % to get % of the account):
  realized   R of trades closed that day
  eod        realized + unrealized at the day's last bar        (equity change uses eod - previous eod_unrealized)
  low/high   lowest / highest (realized-so-far + unrealized) inside the day, from the M5 path
  open_min   worst unrealized R inside the day (Atlas Protector counts OPEN loss)
Markets are summed with each one's worst moments assumed to coincide (conservative).

Rules as in noise_fx/atlas_sim.py: evaluation +3% closed balance, 10% trailing, 5% daily; funded 6% trailing, 3% daily,
Protector at 2% open loss (our shield closes first at --shield), payout every 10 trading days when >= 3 days closed >= +0.5%
and the best day <= 40% of the cycle profit, 80% split (50% after a Protector hit).
"""

import argparse

import numpy as np
import pandas as pd

from bot_audit.ember_bt import load_server_m5


def daily_marks(m5: pd.DataFrame, trades: pd.DataFrame, spread: float) -> pd.DataFrame:
    t = m5["time"].values
    H, L, C = m5["high"].values, m5["low"].values, m5["close"].values
    day = m5["day"].values
    rows = {}
    for r in trades.itertuples():
        a = np.searchsorted(t, np.datetime64(r.entry_time))
        b = np.searchsorted(t, np.datetime64(r.exit_time))
        d0 = None
        for j in range(a, b + 1):
            dj = day[j]
            rec = rows.setdefault(dj, {"realized": 0.0, "unreal_eod": 0.0, "low": 0.0, "high": 0.0, "open_min": 0.0})
            if j == b:
                rec["realized"] += r.R
                break
            # unrealized at this bar's worst / best / close (bid data: a long marks at bid, a short pays the spread to close)
            if r.dir > 0:
                worst, best, cl = (L[j] - r.entry) / r.risk, (H[j] - r.entry) / r.risk, (C[j] - r.entry) / r.risk
            else:
                worst, best, cl = (r.entry - H[j] - spread) / r.risk, (r.entry - L[j] - spread) / r.risk, (r.entry - C[j] - spread) / r.risk
            rec["open_min"] = min(rec["open_min"], worst)
            rec["low"] = min(rec["low"], rec["realized"] + worst)
            rec["high"] = max(rec["high"], rec["realized"] + best)
            if j + 1 < len(t) and day[j + 1] != dj:
                rec["unreal_eod"] += cl
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def build_book(markets):
    """markets: list of (marks_df, risk_weight). Returns per-day arrays in units of 'risk %' (weight x R)."""
    idx = sorted(set().union(*[set(m.index) for m, _ in markets]))
    book = pd.DataFrame(0.0, index=idx, columns=["realized", "unreal_eod", "low", "high", "open_min"])
    for m, w in markets:
        book = book.add(m.reindex(idx).fillna(0.0) * w, fill_value=0.0)
    return book


def simulate(book, start, r_eval, r_fund, shield=1.7, eval_cap=252, fund_len=252):
    real, ue, low, high, omin = (book[c].values for c in ("realized", "unreal_eod", "low", "high", "open_min"))
    n = len(book)
    # low/high/open_min/unreal_eod are measured from each trade's ENTRY price, i.e. they already are the full
    # unrealized amount: equity = closed balance + k x unrealized, nothing carried over separately
    # ---- evaluation (fractions of the start size)
    bal, hwm, eq_prev, i, days = 1.0, 1.0, 1.0, start, 0
    while i < n and days < eval_cap:
        k = r_eval / 100
        day_low = bal + k * low[i]
        if day_low <= hwm - 0.10 or day_low <= eq_prev * 0.95:
            return dict(passed=False, breach=True, days=days + 1)
        hwm = max(hwm, bal + k * high[i])
        bal += k * real[i]
        eq_prev = bal + k * ue[i]
        hwm = max(hwm, eq_prev)
        i += 1
        days += 1
        if bal >= 1.03:
            break
    else:
        return dict(passed=False, breach=False, days=days)
    if bal < 1.03:
        return dict(passed=False, breach=False, days=days)
    ev_days = days
    # ---- funded: restart flat (open trades from the evaluation are not carried over)
    k = r_fund / 100
    bal, hwm, eq_prev, split, prot, paid, pays, f = 1.0, 1.0, 1.0, 0.8, 0, 0.0, 0, 0
    cyc_days, good, best = 0, 0, 0.0
    while i < n and f < fund_len:
        day_real = k * real[i]
        open_loss = -k * omin[i]
        day_low = bal + k * low[i]
        flat_today = False
        # (approximation: after a shield/Protector close, trades of that day that would have closed later still book later)
        if shield > 0 and open_loss >= shield / 100:
            day_real = -(shield / 100); day_low = bal - shield / 100; flat_today = True
        elif open_loss >= 0.02:
            prot += 1; split = 0.5; day_real = -0.02; day_low = bal - 0.02; flat_today = True
            if prot >= 2:
                return dict(passed=True, ev_days=ev_days, f_breach=True, paid=paid, pays=pays, f_days=f, prot=prot)
        if day_low <= hwm - 0.06 or day_low <= eq_prev * 0.97:
            return dict(passed=True, ev_days=ev_days, f_breach=True, paid=paid, pays=pays, f_days=f, prot=prot)
        hwm = max(hwm, bal + k * high[i])
        bal += day_real
        eq_prev = bal + (0.0 if flat_today else k * ue[i])
        hwm = max(hwm, eq_prev)
        cyc_days += 1
        if day_real >= 0.005:
            good += 1
        best = max(best, day_real)
        prof = bal - 1.0
        if cyc_days >= 10 and prof > 0 and good >= 3 and best <= 0.4 * prof:
            paid += prof * split; pays += 1
            bal, hwm, eq_prev, cyc_days, good, best = 1.0, 1.0, 1.0 + (eq_prev - bal), 0, 0, 0.0
            hwm = max(hwm, eq_prev)
        i += 1
        f += 1
    return dict(passed=True, ev_days=ev_days, f_breach=False, paid=paid, pays=pays, f_days=f, prot=prot)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", nargs=4, action="append", metavar=("NAME", "M5_CSV", "TRADES_CSV", "SPREAD"), required=True)
    ap.add_argument("--size", type=float, default=50000)
    a = ap.parse_args()
    marks = []
    for name, m5p, trp, sp in a.market:
        m5 = load_server_m5(m5p)
        tr = pd.read_csv(trp, parse_dates=["entry_time", "exit_time"])
        mk = daily_marks(m5, tr, float(sp))
        marks.append(mk)
        print(f"{name}: {len(tr)} trades, {len(mk)} days with a position or a close; days closing a trade: {(mk.realized != 0).sum()}")
    book = build_book([(m, 1.0) for m in marks])
    common_start = max(m.index.min() for m in marks)        # only the period every market has data for
    book = book[book.index >= common_start]
    days_all = pd.bdate_range(book.index.min(), book.index.max())
    book = book.reindex(days_all).fillna(0.0)
    print(f"days with an open or closing trade: {((book != 0).any(axis=1)).mean():.0%} of weekdays\n")
    starts = range(0, len(book) - 300, 5)
    print("EVALUATION (+3%, 10% trailing, 5% daily)")
    for r in (0.5, 1.0, 1.5, 2.0):
        res = [simulate(book, s, r, 0.5) for s in starts]
        P = [x for x in res if x["passed"]]
        print(f"  risk {r:.1f}%/trade: pass {len(P) / len(res):.2f}  breach {np.mean([x.get('breach', False) for x in res]):.2f}  "
              f"median days {np.median([x['ev_days'] for x in P]) if P else float('nan'):.0f}")
    print("\nFUNDED, one year after passing at 1.0% (6% trailing, 3% daily, Protector, payout rule)")
    for rf in (0.25, 0.5, 0.75, 1.0):
        res = [simulate(book, s, 1.0, rf) for s in starts]
        P = [x for x in res if x["passed"]]
        alive = np.mean([not x["f_breach"] for x in P])
        pays = np.mean([x["pays"] * 252 / max(x["f_days"], 1) for x in P])
        paid = np.mean([x["paid"] * a.size * 252 / max(x["f_days"], 1) for x in P])
        prot = np.mean([x["prot"] > 0 for x in P])
        print(f"  risk {rf:.2f}%/trade: alive {alive:.2f}  protector {prot:.2f}  payouts/yr {pays:.1f}  $ paid/yr {paid:,.0f}")


if __name__ == "__main__":
    main()
