"""
Month-end London 4pm fix test (see PROTOCOL_MONTHEND_FIX.md).

    python -m bot_audit.monthend_fix --fx-dir <folder with EURUSD_M5.csv GBPUSD_M5.csv USDJPY_M5.csv> --spx SP500.r_M5.csv
"""

import argparse
import os

import numpy as np
import pandas as pd

from noise_fx.noise_backtest import load_mt5_m5

LDN = "Europe/London"
PAIRS = {"EURUSD": (+1, 0.00001), "GBPUSD": (+1, 0.00001), "USDJPY": (-1, 0.001)}   # sign of "sell USD", point size


def at_times(df, hm_list):
    loc = df["utc"].dt.tz_convert(LDN)
    df = df.assign(day=loc.dt.date, hm=loc.dt.strftime("%H:%M"))
    return {hm: df[df.hm == hm].set_index("day")["open"] for hm in hm_list}


def spx_price_at(spx, day, hhmm):
    """Last SPX bar open at or before day hh:mm London (the CFD trades almost 24h)."""
    ts = pd.Timestamp(f"{day} {hhmm}", tz=LDN).tz_convert("UTC")
    i = spx["utc"].searchsorted(ts, side="right") - 1
    if i < 0 or (ts - spx["utc"].iloc[i]) > pd.Timedelta(hours=3):
        return None
    return float(spx["open"].iloc[i])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fx-dir", required=True)
    ap.add_argument("--spx", required=True)
    a = ap.parse_args()
    spx = load_mt5_m5(a.spx)
    spx = spx[spx["utc"].diff().dt.total_seconds().fillna(0) <= 3600 * 6]
    spx_start = spx["utc"][spx["utc"].diff().dt.total_seconds() == 300].iloc[0]

    rows = {}
    for pair, (sell_usd_sign, point) in PAIRS.items():
        raw = pd.read_csv(os.path.join(a.fx_dir, f"{pair}_M5.csv"), parse_dates=["time"])
        df = load_mt5_m5(os.path.join(a.fx_dir, f"{pair}_M5.csv"))
        loc = df["utc"].dt.tz_convert(LDN)
        win = (loc.dt.hour >= 14) & (loc.dt.hour < 16)
        sp = raw.loc[raw["time"].isin((df["utc"][win].dt.tz_convert("America/New_York").dt.tz_localize(None)
                                       + pd.Timedelta(hours=7))), "spread"]
        spread = float(sp[sp > 0].median()) * point
        px = at_times(df, ["14:00", "16:00"])
        days = sorted(set(px["14:00"].index) & set(px["16:00"].index))
        s = pd.Series(days, index=pd.to_datetime(days))
        month_last = s.groupby(s.index.to_period("M")).max()
        # drop the running month: its last day in the data is not the real month-end
        if pd.Timestamp(month_last.iloc[-1]).day < pd.Timestamp(month_last.iloc[-1]).days_in_month - 4:
            month_last = month_last.iloc[:-1]
        rows[pair] = (px, month_last, spread, sell_usd_sign)
        print(f"{pair}: spread {spread:.5f} ({spread / point / 10:.1f} pips)")

    months = sorted(set.intersection(*[set(r[1].index) for r in rows.values()]))
    recs = []
    prev_fix_day = None
    for m in months:
        day = rows["EURUSD"][1][m]
        if prev_fix_day is None or pd.Timestamp(day, tz=LDN) < spx_start:
            prev_fix_day = day
            continue
        p0 = spx_price_at(spx, prev_fix_day, "16:00")
        p1 = spx_price_at(spx, day, "14:00")
        prev_fix_day = day
        if p0 is None or p1 is None:
            continue
        sig = np.sign(p1 / p0 - 1)
        rec = {"month": str(m), "spx_mtd": p1 / p0 - 1}
        for pair, (px, ml, spread, sgn) in rows.items():
            d = ml.get(m)
            if d is None or d not in px["14:00"].index or d not in px["16:00"].index:
                continue
            e, x = px["14:00"][d], px["16:00"][d]
            r = x / e - 1
            pos = sig * sgn                              # +1 = long the pair
            rec[pair] = pos * r - spread / e
            rec[pair + "_usd_long"] = -sgn * r - spread / e   # unconditional: buy USD into the fix
        recs.append(rec)
    t = pd.DataFrame(recs).set_index("month")
    t["pooled"] = t[list(PAIRS)].mean(axis=1)
    t["usd_long"] = t[[p + "_usd_long" for p in PAIRS]].mean(axis=1)

    def st(x):
        x = x.dropna()
        return f"n {len(x):>3}  avg {x.mean() * 1e4:+.2f} bp  t {x.mean() / x.std() * np.sqrt(len(x)):+.2f}  win {(x > 0).mean():.0%}"

    h = len(t) // 2
    print(f"\nsample {t.index[0]} -> {t.index[-1]}")
    print("POOLED (test):      ", st(t["pooled"]))
    print("  first half:       ", st(t["pooled"].iloc[:h]))
    print("  second half:      ", st(t["pooled"].iloc[h:]))
    for p in PAIRS:
        print(f"  {p} (info):     ", st(t[p]))
    print("unconditional USD long into fix (info):", st(t["usd_long"]))
    x = t["pooled"].dropna()
    tt = x.mean() / x.std() * np.sqrt(len(x))
    ok = x.mean() > 0 and tt >= 1.65 and x.iloc[:h].mean() > 0 and x.iloc[h:].mean() > 0
    print(f"\nVERDICT (pre-registered): {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
