"""
Write NBRO's trades (NAS100 + SPX500) with their worst/best open excursion, for atlas_sim.py.

    python -m noise_fx.dump_trades --data m5_export --nas NAS100.r --spx SP500.r --out nbro_trades.csv

Each row: market, utc_day, entry/exit (UTC), dir, ret (net of spread, fraction of notional),
mae (worst open P&L incl. spread, <= 0), mfe (best open P&L, >= 0), reason.
"""

import argparse
import os

import numpy as np
import pandas as pd

from noise_fx.noise_backtest import Spec, load_mt5_m5, run

MARKETS = {"NAS100": 1.0, "SPX500": 0.5}     # spread in index points (Atlas to be measured)


def excursions(df: pd.DataFrame, tr: pd.DataFrame, spread: float) -> pd.DataFrame:
    t = df["utc"].values
    H, L = df["high"].values, df["low"].values
    mae, mfe = [], []
    for r in tr.itertuples():
        a = np.searchsorted(t, np.datetime64(r.entry_ts.tz_convert("UTC").tz_localize(None)))
        b = np.searchsorted(t, np.datetime64(r.exit_ts.tz_convert("UTC").tz_localize(None)), side="right")
        hi, lo = H[a:b].max(), L[a:b].min()
        c = spread / r.entry
        if r.dir > 0:
            mae.append(min(lo / r.entry - 1 - c, r.ret)); mfe.append(max(hi / r.entry - 1 - c, r.ret, 0.0))
        else:
            mae.append(min(1 - hi / r.entry - c, r.ret)); mfe.append(max(1 - lo / r.entry - c, r.ret, 0.0))
    out = tr.copy()
    out["mae"], out["mfe"] = mae, mfe
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--nas", default="NAS100")
    ap.add_argument("--spx", default="SPX500")
    ap.add_argument("--server-tz", default="ny+7")
    ap.add_argument("--out", default="nbro_trades.csv")
    a = ap.parse_args()
    frames = []
    for m, sym in (("NAS100", a.nas), ("SPX500", a.spx)):
        df = load_mt5_m5(os.path.join(a.data, f"{sym}_M5.csv"), a.server_tz)
        tr = run(df, Spec(m, "America/New_York", "09:30", spread=MARKETS[m], stop_pct=1.0))
        tr = excursions(df, tr, MARKETS[m])
        tr.insert(0, "market", m)
        frames.append(tr)
        print(f"{m}: {len(tr)} trades, avg {tr.ret.mean() * 100:+.4f}%, worst open {tr.mae.min() * 100:.2f}%")
    out = pd.concat(frames)
    out["utc_day"] = pd.to_datetime(out["entry_ts"], utc=True).dt.date
    out = out.sort_values("entry_ts")
    out[["market", "utc_day", "entry_ts", "exit_ts", "dir", "ret", "mae", "mfe", "reason"]].to_csv(a.out, index=False)
    print(f"saved {a.out}")


if __name__ == "__main__":
    main()
