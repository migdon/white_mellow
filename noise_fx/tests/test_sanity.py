"""
    python -m noise_fx.tests.test_sanity

1. Random walk (no edge)         -> z small across seeds.
2. Planted intraday trend        -> clearly positive.
3. Costs are charged             -> avg trade drops by exactly spread/price + commission.
4. Emergency stop                -> no trade loses much more than the stop.
"""

import os
import tempfile

import numpy as np
import pandas as pd

from noise_fx.noise_backtest import Spec, load_mt5_m5, run, summary


def fx_synth(seed, days=750, trend=0.0):
    """24h EURUSD-like M5 bars in server time (NY+7). `trend` = per-day drift that persists through the session."""
    rng = np.random.default_rng(seed)
    t = pd.date_range("2022-01-03", periods=days * 288, freq="5min")
    t = t[t.dayofweek < 5]
    n = len(t)
    day_dir = np.repeat(rng.choice([-1, 1], n // 288 + 1), 288)[:n]
    r = trend * day_dir / 288 + rng.normal(0, 0.0003, n)
    c = 1.10 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.0001, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.0001, n)))
    return pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c,
                         "tick_volume": rng.integers(50, 500, n)})


def _load(df):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "x.csv")
        df.to_csv(f, index=False)
        return load_mt5_m5(f, "ny+7")


def _days(df, tz="America/New_York"):
    return pd.Index(sorted(set(df["utc"].dt.tz_convert(tz).dt.date)))


def test_no_edge():
    zs = []
    for s in range(4):
        df = _load(fx_synth(s, days=500))
        tr = run(df, Spec("X", "America/New_York", "08:00", stop_pct=0.5))
        zs.append(summary(tr, _days(df))["z"])
    assert max(abs(z) for z in zs) < 2.6, zs
    print(f"no edge: z = {[round(z, 2) for z in zs]}  OK")


def test_planted_trend():
    df = _load(fx_synth(7, days=500, trend=0.004))
    tr = run(df, Spec("X", "America/New_York", "08:00", stop_pct=0.5))
    z = summary(tr, _days(df))["z"]
    assert z > 3, z
    print(f"planted trend: z = {z:.1f}  OK")


def test_costs():
    df = _load(fx_synth(3, days=200))
    a = run(df, Spec("X", "America/New_York", "08:00", 0.0, 0.0, 0.5))
    b = run(df, Spec("X", "America/New_York", "08:00", 0.00004, 0.00007, 0.5))
    exp = 0.00004 / a["entry"] + 0.00007
    assert np.allclose(a["ret"] - b["ret"], exp)
    print("costs: charged exactly once per round trip  OK")


def test_stop():
    df = _load(fx_synth(5, days=300, trend=0.004))
    tr = run(df, Spec("X", "America/New_York", "08:00", stop_pct=0.1))
    assert (tr["reason"] == "stop").sum() > 0
    worst = tr.loc[tr["reason"] == "stop", "ret"].min()
    assert worst > -0.0035, worst          # 0.1% stop; only a gapped open can be worse
    print(f"stop: {int((tr['reason'] == 'stop').sum())} stops, worst {worst * 100:.3f}%  OK")


if __name__ == "__main__":
    test_no_edge()
    test_planted_trend()
    test_costs()
    test_stop()
