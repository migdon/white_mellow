"""
NBRO rule on other stock indices (see PROTOCOL_INDICES.md), plus the NAS100/SPX500 engine check.

    python -m noise_fx.run_indices --data m5_export --names JPN225=JPN225 HK50=HK50 AUS200=AUS200 GER40=GER40 UK100=UK100 NAS100=NAS100 SPX500=SPX500

--names maps each market to the broker's symbol (file <data>/<broker symbol>_M5.csv). Markets with no file are skipped.
"""

import argparse
import json
import os

import numpy as np
import pandas as pd

from noise_fx.noise_backtest import Spec, load_mt5_m5, run, summary

MARKETS = {   # anchor tz, anchor time, spread (points)
    "JPN225": ("Asia/Tokyo", "09:00", 9.0),
    "HK50": ("Asia/Hong_Kong", "09:30", 8.0),
    "AUS200": ("Australia/Sydney", "10:00", 2.0),
    "GER40": ("Europe/Berlin", "09:00", 1.5),
    "UK100": ("Europe/London", "08:00", 1.5),
}
CHECKS = {    # engine check vs nbro_app.py header (not part of the family)
    "NAS100": ("America/New_York", "09:30", 1.0, "+0.048%/trade, Sharpe 1.04 (2012-2026)"),
    "SPX500": ("America/New_York", "09:30", 0.5, "+0.033%/trade, Sharpe 0.85 (2019-2026)"),
}
FAMILY = len(MARKETS)
STOP_PCT = 1.0


def verdict(rec, old, dbl, full):
    ok = (rec.get("z", -9) >= 2.33 and old.get("z", -9) >= 2.0 and old.get("avg_trade_pct", -1) > 0
          and dbl.get("avg_trade_pct", -1) > 0 and full["trades"] >= 300)
    return "PASS" if ok else ("WEAK" if rec.get("z", -9) >= 2.0 else "FAIL")


def evaluate(df, tz, hhmm, spread, comm):
    base, dbl = Spec("X", tz, hhmm, spread, comm, STOP_PCT), Spec("X", tz, hhmm, 2 * spread, 2 * comm, STOP_PCT)
    tr, trd = run(df, base), run(df, dbl)
    days = pd.Index(sorted(set(df["utc"].dt.tz_convert(tz).dt.date)))
    if tr.empty:
        return None
    mid = df["utc"].iloc[0] + (df["utc"].iloc[-1] - df["utc"].iloc[0]) / 2
    cut = mid.tz_convert(tz).date()
    full = summary(tr, days)
    rec = summary(tr[tr["date"] >= cut], days[days >= cut])
    old = summary(tr[tr["date"] < cut], days[days < cut])
    return full, rec, old, summary(trd, days), [str(days[0]), str(days[-1])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--names", nargs="*", default=[], help="MARKET=BROKERSYMBOL pairs")
    ap.add_argument("--server-tz", default="ny+7")
    ap.add_argument("--commission", type=float, default=0.0, help="round trip, fraction of notional")
    ap.add_argument("--out", default="reports/noise_indices_results.json")
    a = ap.parse_args()
    names = {m: m for m in list(MARKETS) + list(CHECKS)}
    names.update(dict(x.split("=", 1) for x in a.names))

    res = {"protocol": "noise_fx/PROTOCOL_INDICES.md", "family": FAMILY, "results": {}, "engine_check": {}}
    print("\nENGINE CHECK (NBRO's own markets, 09:30 New York):")
    for m, (tz, hhmm, sp, ref) in CHECKS.items():
        f = os.path.join(a.data, f"{names[m]}_M5.csv")
        if not os.path.exists(f):
            print(f"  {m}: no file {f}")
            continue
        r = evaluate(load_mt5_m5(f, a.server_tz), tz, hhmm, sp, a.commission)
        if r:
            full = r[0]
            res["engine_check"][m] = {"full": full, "span": r[4]}
            print(f"  {m} {r[4][0]}->{r[4][1]}: {full['trades']} trades, {full['avg_trade_pct']:+.4f}%/trade, "
                  f"Sharpe {full['sharpe_1x']:.2f}, z {full['z']:.2f}   [nbro header: {ref}]")

    rows = []
    for m, (tz, hhmm, sp) in MARKETS.items():
        f = os.path.join(a.data, f"{names[m]}_M5.csv")
        if not os.path.exists(f):
            print(f"-- {m}: no file {f}")
            continue
        r = evaluate(load_mt5_m5(f, a.server_tz), tz, hhmm, sp, a.commission)
        if not r:
            print(f"-- {m}: no trades (check the anchor / data hours)")
            continue
        full, rec, old, dbl, span = r
        v = verdict(rec, old, dbl, full)
        res["results"][m] = {"full": full, "recent": rec, "older": old, "doubled_costs": dbl, "verdict": v, "span": span}
        rows.append((m, span, full, rec, old, dbl, v))

    print(f"\nNBRO rule on other indices: family of {FAMILY}. PASS needs recent z>=2.33, older z>=2.0, doubled cost >0, >=300 trades\n")
    print(f"{'market':<8}{'from':>11}{'trades':>7}{'/day':>6}{'avg%':>8}{'z full':>8}{'z rec':>7}{'z old':>7}"
          f"{'dbl avg%':>9}{'Sh 1x':>7}{'yrs+':>7}  verdict")
    for m, span, full, rec, old, dbl, v in rows:
        print(f"{m:<8}{span[0]:>11}{full['trades']:>7}{full['per_day']:>6.2f}{full['avg_trade_pct']:>8.4f}{full['z']:>8.2f}"
              f"{rec.get('z', np.nan):>7.2f}{old.get('z', np.nan):>7.2f}{dbl['avg_trade_pct']:>9.4f}"
              f"{full['sharpe_1x']:>7.2f}{full['years_pos']:>7}  {v}")
    print(f"\nPASS: {sum(r[-1] == 'PASS' for r in rows)} of {len(rows)} tested")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
