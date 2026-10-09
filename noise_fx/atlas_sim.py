"""
Atlas Funded 1-Step ACCESS, replayed on NBRO's real trade history (from dump_trades.py).

    python -m noise_fx.atlas_sim --trades nbro_trades.csv [--size 50000]

Rules (Atlas help centre, as recorded in ember_app.py, reviewed 27 Sep 2026; screenshot of the user's account):
  EVALUATION  +3% closed balance; max loss 10% of the start size, trailing the equity high;
              daily loss 5% of the previous day's end-of-day equity; no minimum days, no time limit.
  FUNDED      no target; max loss 6% trailing; daily 3%; ATLAS PROTECTOR: an open loss of 2% of the
              start size closes everything and cuts the split to 50% for good, a second one breaches.
              Payout every 14 days if, since the last payout, >= 3 UTC days closed >= +0.5% of the start size
              and the best day is <= 40% of the profit. Split 80%. After a payout the balance is back to the start size.

Conservative on intraday paths: on a day with both indices open, the worst open loss of each trade is assumed to
happen at the same moment (sum of MAE), and the equity high is the sum of MFE. NBRO is flat at the end of every day.

Every 5th trading day of the history is a start date: the evaluation runs from it (at most 1 year), then the funded
stage runs on the trades that follow (1 year). Results are averaged over all start dates.
"""

import argparse

import numpy as np
import pandas as pd


def daily_book(tr: pd.DataFrame) -> pd.DataFrame:
    """Per UTC day: closed return, worst open (sum of MAE), best open (sum of MFE), per unit of notional per market."""
    g = tr.groupby("utc_day")
    return pd.DataFrame({"ret": g["ret"].sum(), "mae": g["mae"].sum(), "mfe": g["mfe"].sum()})


def all_days(tr: pd.DataFrame) -> pd.Index:
    d = pd.bdate_range(tr["utc_day"].min(), tr["utc_day"].max())
    return pd.Index(d.date)


def simulate(book: pd.DataFrame, days: pd.Index, notional: float, shield: float, start_i: int,
             eval_cap=252, funded_len=252):
    R = book.reindex(days).fillna(0.0)
    ret, mae, mfe = R["ret"].values * notional, R["mae"].values * notional, R["mfe"].values * notional
    n = len(days)
    # ---- evaluation (amounts as a fraction of the start size)
    bal, hwm, i, passed, ev_days = 1.0, 1.0, start_i, False, 0
    while i < n and ev_days < eval_cap:
        floor_dd = hwm - 0.10
        floor_day = bal * (1 - 0.05)
        low = bal * (1 + mae[i])
        if low <= floor_dd or low <= floor_day:
            return {"passed": False, "breach": True, "eval_days": ev_days + 1}
        hwm = max(hwm, bal * (1 + mfe[i]))
        bal *= 1 + ret[i]
        hwm = max(hwm, bal)
        i += 1; ev_days += 1
        if bal >= 1.03:
            passed = True
            break
    if not passed:
        return {"passed": False, "breach": False, "eval_days": ev_days}
    # ---- funded
    bal, hwm, split, prot, paid, f_days = 1.0, 1.0, 0.8, 0, 0.0, 0
    cyc_days, cyc_good, cyc_best, n_pay = 0, 0, 0.0, 0
    breached, shield_hits = False, 0
    while i < n and f_days < funded_len:
        day_ret, low = ret[i], bal * (1 + mae[i])
        open_loss = -bal * mae[i]
        if shield > 0 and open_loss >= shield:              # our own shield closes first
            day_ret = -shield / bal; low = bal - shield; shield_hits += 1
        elif open_loss >= 0.02:                              # Atlas Protector
            prot += 1; split = 0.5; day_ret = -0.02 / bal; low = bal - 0.02
            if prot >= 2:
                breached = True; break
        if low <= hwm - 0.06 or low <= bal * (1 - 0.03):
            breached = True; break
        hwm = max(hwm, bal * (1 + mfe[i]))
        pnl = bal * day_ret
        bal += pnl
        hwm = max(hwm, bal)
        cyc_days += 1
        if pnl >= 0.005:
            cyc_good += 1
        cyc_best = max(cyc_best, pnl)
        prof = bal - 1.0
        if cyc_days >= 10 and prof > 0 and cyc_good >= 3 and cyc_best <= 0.4 * prof:
            paid += prof * split; n_pay += 1
            bal, hwm, cyc_days, cyc_good, cyc_best = 1.0, 1.0, 0, 0, 0.0
        i += 1; f_days += 1
    return {"passed": True, "breach": False, "eval_days": ev_days, "funded_breach": breached,
            "protector": prot, "shield_hits": shield_hits, "payouts": n_pay, "paid": paid, "funded_days": f_days}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default="nbro_trades.csv")
    ap.add_argument("--size", type=float, default=50000)
    ap.add_argument("--shield", type=float, default=1.7, help="our close-all line, %% open loss (0 = off)")
    a = ap.parse_args()
    tr = pd.read_csv(a.trades, parse_dates=["utc_day"])
    tr["utc_day"] = tr["utc_day"].dt.date
    book, days = daily_book(tr), all_days(tr)
    starts = range(0, len(days) - 300, 5)
    print(f"{len(tr)} trades, {len(days)} trading days, {len(starts)} start dates, ${a.size:,.0f} account, "
          f"shield {a.shield}%\n")
    print(f"{'risk/idx':>8}{'pass':>7}{'breach':>8}{'med days':>9}{'funded ok':>10}{'protector':>10}"
          f"{'payouts/yr':>11}{'$ paid/yr':>11}{'$ per attempt':>14}")
    for risk in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5):
        notional = risk / 1.0                            # NBRO: risk% is the loss at the 1% emergency stop
        res = [simulate(book, days, notional, a.shield / 100, s) for s in starts]
        P = [r for r in res if r["passed"]]
        p_pass = len(P) / len(res)
        p_breach = np.mean([r["breach"] for r in res])
        med = np.median([r["eval_days"] for r in P]) if P else np.nan
        f_ok = np.mean([not r["funded_breach"] for r in P]) if P else np.nan
        prot = np.mean([r["protector"] > 0 for r in P]) if P else np.nan
        pays = np.mean([r["payouts"] * 252 / max(r["funded_days"], 1) for r in P]) if P else np.nan
        paid = np.mean([r["paid"] * a.size * 252 / max(r["funded_days"], 1) for r in P]) if P else 0.0
        print(f"{risk:>7.2f}%{p_pass:>7.2f}{p_breach:>8.2f}{med:>9.0f}{f_ok:>10.2f}{prot:>10.2f}"
              f"{pays:>11.1f}{paid:>11,.0f}{p_pass * paid:>14,.0f}")
    print("\npass = reached +3% within a year; breach = failed the evaluation; med days = trading days to pass;"
          "\nfunded ok = still alive after a year funded; protector = share hit by Atlas Protector at least once;"
          "\n$ per attempt = pass x payouts in the first funded year (before the Access fee).")


if __name__ == "__main__":
    main()
