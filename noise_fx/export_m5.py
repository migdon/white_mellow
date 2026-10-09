"""
Export M5 history for the 9 FX pairs from MT5 (run on the Windows PC with MT5 logged in).

    pip install MetaTrader5 pandas
    python -m noise_fx.export_m5 --out m5_export --from 2012-01-01 [--suffix .r]

IMPORTANT: MT5 only returns as many bars as "Tools > Options > Charts > Max bars in chart" allows.
Set it to Unlimited and restart MT5 first. Brokers also keep limited M5 history; the script prints
the first date it got for each pair. If a pair has less than ~4 years, use another history source
(e.g. Dukascopy) saved in the same CSV format: time,open,high,low,close,tick_volume.
"""

import argparse
import os
from datetime import datetime, timezone

import pandas as pd

# kept here (not imported from run_fx) so the exporter needs no timezone data on Windows
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY"]


def main():
    import MetaTrader5 as mt5

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="m5_export")
    ap.add_argument("--from", dest="start", default="2012-01-01")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--extra", nargs="*", default=["NAS100", "SPX500"],
                    help="also export these (to check the engine reproduces NBRO's own numbers)")
    a = ap.parse_args()
    if not mt5.initialize():
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}")
    os.makedirs(a.out, exist_ok=True)
    start = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc)
    try:
        for sym in PAIRS + a.extra:
            name = sym + (a.suffix if sym in PAIRS else "")
            if not mt5.symbol_select(name, True):
                print(f"!! {name}: not available")
                continue
            parts, y = [], start.year
            while y <= datetime.now(timezone.utc).year:
                lo = max(start, datetime(y, 1, 1, tzinfo=timezone.utc))
                hi = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
                r = mt5.copy_rates_range(name, mt5.TIMEFRAME_M5, lo, hi)
                if r is not None and len(r):
                    parts.append(pd.DataFrame(r))
                y += 1
            if not parts:
                print(f"!! {name}: no M5 history ({mt5.last_error()})")
                continue
            df = pd.concat(parts).drop_duplicates("time").sort_values("time")
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df[["time", "open", "high", "low", "close", "tick_volume", "real_volume", "spread"]].to_csv(
                os.path.join(a.out, f"{name}_M5.csv"), index=False)
            print(f"{name}: {len(df):,} bars  {df.time.iloc[0]} -> {df.time.iloc[-1]}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
