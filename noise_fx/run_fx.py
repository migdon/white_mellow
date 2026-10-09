"""
Run the pre-registered NBRO -> FX protocol (see PROTOCOL.md).

    python -m noise_fx.run_fx --data m5_export [--server-tz ny+7] [--commission 7]

Expects <data>/<SYMBOL>_M5.csv from export_m5.py. Missing pairs are reported and skipped
(they still count in the family of 18).
"""

import argparse
import json
import os

import numpy as np
import pandas as pd

from noise_fx.noise_backtest import Spec, load_mt5_m5, run, summary

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY"]
SPREAD_PIPS = {"EURUSD": 0.4, "GBPUSD": 0.5, "USDJPY": 0.5, "USDCAD": 0.5,
               "AUDUSD": 0.6, "USDCHF": 0.8, "NZDUSD": 1.0, "EURJPY": 1.0, "GBPJPY": 1.5}
ANCHORS = {"NY0800": ("America/New_York", "08:00"), "LDN0800": ("Europe/London", "08:00")}
STOP_PCT = 0.5
FAMILY = len(PAIRS) * len(ANCHORS)


def pip(sym):
    return 0.01 if sym.endswith("JPY") else 0.0001


def verdict(rec, old, dbl, full):
    if rec.get("trades", 0) == 0:
        return "NO DATA"
    ok = (rec["z"] >= 2.8 and old.get("z", -9) >= 2.0 and old.get("avg_trade_pct", -1) > 0
          and dbl.get("avg_trade_pct", -1) > 0 and full["trades"] >= 300)
    if ok:
        return "PASS"
    return "WEAK" if rec["z"] >= 2.0 else "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--server-tz", default="ny+7")
    ap.add_argument("--commission", type=float, default=7.0, help="USD per 100k round trip")
    ap.add_argument("--out", default="reports/noise_fx_results.json")
    a = ap.parse_args()

    rows, res = [], {"protocol": "noise_fx/PROTOCOL.md", "family": FAMILY, "results": {}}
    for sym in PAIRS:
        f = os.path.join(a.data, f"{sym}{a.suffix}_M5.csv")
        if not os.path.exists(f):
            print(f"-- {sym}: no file {f}")
            continue
        df = load_mt5_m5(f, a.server_tz)
        mid = df["utc"].iloc[0] + (df["utc"].iloc[-1] - df["utc"].iloc[0]) / 2
        for an, (tz, hhmm) in ANCHORS.items():
            base = Spec(sym, tz, hhmm, SPREAD_PIPS[sym] * pip(sym), a.commission / 1e5, STOP_PCT)
            dbl = Spec(sym, tz, hhmm, 2 * base.spread, 2 * base.commission_frac, STOP_PCT)
            tr, trd = run(df, base), run(df, dbl)
            if tr.empty:
                continue
            days = pd.Index(sorted(set(df["utc"].dt.tz_convert(tz).dt.date)))
            cut = mid.tz_convert(tz).date()
            older, recent = days[days < cut], days[days >= cut]
            full = summary(tr, days)
            rec = summary(tr[tr["date"] >= cut], recent)
            old = summary(tr[tr["date"] < cut], older)
            dsum = summary(trd, days)
            v = verdict(rec, old, dsum, full)
            res["results"][f"{sym}_{an}"] = {"full": full, "recent": rec, "older": old,
                                             "doubled_costs": dsum, "verdict": v,
                                             "span": [str(days[0]), str(days[-1])]}
            rows.append((sym, an, full, rec, old, dsum, v))

    # engine check: on NAS100 the same engine must land near NBRO's own header numbers
    nas = os.path.join(a.data, "NAS100_M5.csv")
    if os.path.exists(nas):
        df = load_mt5_m5(nas, a.server_tz)
        tr = run(df, Spec("NAS100", "America/New_York", "09:30", spread=1.0, stop_pct=1.0))
        s = summary(tr, pd.Index(sorted(set(df["utc"].dt.tz_convert("America/New_York").dt.date))))
        res["engine_check_nas100"] = s
        print(f"\nENGINE CHECK NAS100 09:30 NY (spread 1.0 pt assumed): {s['trades']} trades, "
              f"{s['avg_trade_pct']:+.4f}%/trade, Sharpe {s['sharpe_1x']:.2f}  "
              f"[nbro_app.py header: +0.048%/trade, Sharpe 1.04 on 2012-2026]")

    print(f"\nNBRO rule on FX — family of {FAMILY}; PASS needs recent z>=2.8, older z>=2.0, doubled cost >0, >=300 trades\n")
    print(f"{'pair':<8}{'anchor':<9}{'trades':>7}{'avg%':>8}{'z full':>8}{'z recent':>9}{'z older':>8}"
          f"{'dbl avg%':>9}{'Sh 1x':>7}{'years+':>8}  verdict")
    for sym, an, full, rec, old, dsum, v in rows:
        print(f"{sym:<8}{an:<9}{full['trades']:>7}{full['avg_trade_pct']:>8.4f}{full['z']:>8.2f}"
              f"{rec.get('z', np.nan):>9.2f}{old.get('z', np.nan):>8.2f}{dsum['avg_trade_pct']:>9.4f}"
              f"{full['sharpe_1x']:>7.2f}{full['years_pos']:>8}  {v}")
    n_pass = sum(r[-1] == "PASS" for r in rows)
    print(f"\nPASS: {n_pass} of {len(rows)} tested (expected by luck alone ~0.05)")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
