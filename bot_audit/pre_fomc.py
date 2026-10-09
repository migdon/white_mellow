"""
Pre-FOMC drift test (see PROTOCOL_PRE_FOMC.md).

    python -m bot_audit.pre_fomc --data SP500.r_M5.csv [--nas NAS100.r_M5.csv]
"""

import argparse

import numpy as np
import pandas as pd

from noise_fx.noise_backtest import load_mt5_m5

# Scheduled FOMC statement days (statement at 14:00 New York). Unscheduled 2020-03-03 / 2020-03-15 excluded.
FOMC = """
2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16
""".split()
FOMC_DAYS = pd.to_datetime(FOMC).date


def windows(path, spread, financing=0.0002):
    """Return per trading day: net return of buying at 14:00 NY the previous trading day, selling 13:55 NY today."""
    df = load_mt5_m5(path)
    ny = df["utc"].dt.tz_convert("America/New_York")
    df["day"], df["hm"] = ny.dt.date, ny.dt.strftime("%H:%M")
    buy = df[df.hm == "14:00"].set_index("day")["open"]
    sell = df[df.hm == "13:55"].set_index("day")["open"]
    days = sorted(set(buy.index) & set(sell.index))
    out = {}
    for prev, cur in zip(days[:-1], days[1:]):
        if (pd.Timestamp(cur) - pd.Timestamp(prev)).days > 4:      # skip holes in the data
            continue
        b = buy[prev] + spread
        out[cur] = sell[cur] / b - 1 - financing
    return pd.Series(out)


def report(name, w):
    f = w[w.index.isin(FOMC_DAYS)]
    c = w[~w.index.isin(FOMC_DAYS)]
    t = f.mean() / f.std() * np.sqrt(len(f))
    print(f"{name}: FOMC n {len(f)}  avg {f.mean() * 100:+.3f}%  t {t:+.2f}  win {(f > 0).mean():.0%}  | "
          f"control n {len(c)} avg {c.mean() * 100:+.3f}%")
    yrs = f.groupby(pd.to_datetime(f.index).year).agg(["count", "mean"])
    print("   by year (avg %):", {y: round(m * 100, 3) for y, m in yrs["mean"].items()})
    half = len(f) // 2
    print(f"   first half avg {f.iloc[:half].mean() * 100:+.3f}%  second half avg {f.iloc[half:].mean() * 100:+.3f}%")
    return t, f.mean(), c.mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--nas", default=None)
    a = ap.parse_args()
    t, fm, cm = report("SP500", windows(a.data, 0.6))
    ok = fm > 0 and t >= 1.65 and fm > cm
    print(f"\nVERDICT (pre-registered, SP500): {'PASS' if ok else 'FAIL'}")
    if a.nas:
        report("NAS100 (info only)", windows(a.nas, 1.7))


if __name__ == "__main__":
    main()
