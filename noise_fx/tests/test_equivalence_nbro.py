"""
The FX backtester must make EXACTLY the trades nbro_app.py's own functions make.

    python -m noise_fx.tests.test_equivalence_nbro /path/to/nbro_app.py

Synthetic 24h M5 data in broker server time (New York + 7h), spanning a US DST change, with a few
missing bars. The reference loop below drives nbro_app's noise_frame / noise_context /
noise_entry_direction / noise_exit_due exactly the way the live bot does (no emergency stop here,
so both sides are compared on the strategy logic alone).
"""

import importlib.util
import os
import sys

import numpy as np
import pandas as pd

from noise_fx.noise_backtest import Spec, load_mt5_m5, run


def synth(seed=1, start="2026-01-05", days=120) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = pd.date_range(start, periods=days * 288, freq="5min")
    t = t[t.dayofweek < 5]
    n = len(t)
    drift = np.repeat(rng.normal(0, 0.00008, n // 288 + 1), 288)[:n]       # trending days
    r = drift + rng.normal(0, 0.0006, n)
    c = 18000 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.0002, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.0002, n)))
    v = rng.integers(50, 500, n).astype(float)
    df = pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c, "tick_volume": v})
    drop = rng.choice(n, 40, replace=False)                                 # a few missing bars
    return df.drop(index=drop).reset_index(drop=True)


def reference(nb, df: pd.DataFrame) -> list:
    d = df.rename(columns={"tick_volume": "volume"})
    trades = []
    for sd in sorted(set(d["time"].dt.normalize())):
        fr = nb.noise_frame(d, sd)
        if not fr or not fr.get("ready"):
            continue
        pos = None
        for k in range(len(nb.CHECK_MINUTES_AFTER_OPEN)):
            ctx = nb.noise_context(d, fr, sd, k)
            if ctx is None:
                continue
            if pos:
                if nb.noise_exit_due(pos[0], ctx["P"], ctx["vwap"], ctx["UB"], ctx["LB"]):
                    trades.append((pos[1], ctx["ts"], pos[0], "exit"))
                    pos = None
                    continue
            if pos is None:
                dr = nb.noise_entry_direction(ctx["P"], ctx["UB"], ctx["LB"])
                if dr:
                    pos = (dr, ctx["ts"])
        if pos:
            _, e = nb.session_window(sd)
            if (d["time"] == e).any():
                trades.append((pos[1], e, pos[0], "eod"))
            else:   # closing bar missing: the live bot still closes at the session end (last bar's price)
                o, _ = nb.session_window(sd)
                last = d.loc[(d["time"] >= o) & (d["time"] < e), "time"].iloc[-1]
                trades.append((pos[1], last, pos[0], "eod_short"))
    return trades


def main(nbro_path, cases=((1, "2026-01-05", 120), (2, "2025-09-01", 300), (3, "2024-02-15", 260))):
    spec_ = importlib.util.spec_from_file_location("nbro_ref", nbro_path)
    nb = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(nb)
    nb.ORB_SESSION_HOUR = 16
    for seed, start, days in cases:
        _one(nb, synth(seed, start, days))


def _one(nb, df):
    tmp = os.path.join(os.path.dirname(__file__), "_synth.csv")
    df.to_csv(tmp, index=False)
    try:
        mine = run(load_mt5_m5(tmp, "ny+7"), Spec("SYN", "America/New_York", "09:30", stop_pct=1000.0))
    finally:
        os.remove(tmp)
    ref = reference(nb, df)
    # convert mine to server time for comparison
    to_srv = lambda ts: (ts.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7))
    got = [(to_srv(r.entry_ts), to_srv(r.exit_ts), "LONG" if r.dir > 0 else "SHORT", r.reason)
           for r in mine.itertuples()]
    assert len(ref) > 50, f"too few reference trades ({len(ref)}) for a meaningful test"
    if got != ref:
        for a, b in zip(got, ref):
            if a != b:
                print("first mismatch:\n  mine", a, "\n  nbro", b)
                break
        raise SystemExit(f"MISMATCH: mine {len(got)} trades, nbro {len(ref)}")
    print(f"identical: {len(ref)} trades ({df.time.iloc[0].date()} -> {df.time.iloc[-1].date()}), "
          f"same entry/exit times, direction and reason")


if __name__ == "__main__":
    main(sys.argv[1])
