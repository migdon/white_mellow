"""MTF trend + M15 breakout + news filter. Protocol: PROTOCOL_MTF_BREAKOUT.md"""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0]); sys.path.insert(0, __file__.rsplit("/", 2)[0])
from ifvg import FILES, load, stats
from pre_fomc import FOMC_DAYS


def run(m5, spread, tgt=3.0, news=True, need_h1=True, hold_days=3):
    d = m5.set_index("time")
    def trend(rule):
        c = d["close"].resample(rule, label="right", closed="right").last().dropna()
        return np.sign(c - c.ewm(span=50, adjust=False).mean())
    q = d.resample("15min", label="left", closed="left").agg(high=("high", "max"), low=("low", "min")).dropna()
    hh, ll = q["high"].rolling(20).max(), q["low"].rolling(20).min()
    sh, sl_ = q["high"].rolling(10).max(), q["low"].rolling(10).min()
    # levels known at the START of each M15 bar = values of the bars completed before it
    lv = pd.DataFrame({"hh": hh, "ll": ll, "sh": sh, "sl": sl_}).shift(1)
    lv.index = lv.index  # bar start
    T = m5["time"]
    lv5 = lv.reindex(T.dt.floor("15min")).values
    h4 = pd.merge_asof(m5[["time"]], trend("240min").rename("v").reset_index().rename(columns={"time": "ts"}),
                       left_on="time", right_on="ts", allow_exact_matches=True)["v"].values
    h1 = pd.merge_asof(m5[["time"]], trend("60min").rename("v").reset_index().rename(columns={"time": "ts"}),
                       left_on="time", right_on="ts", allow_exact_matches=True)["v"].values
    O, H, L, C = (m5[c].values for c in ("open", "high", "low", "close"))
    ny = (T - pd.Timedelta(hours=7))
    nymin = (ny.dt.hour * 60 + ny.dt.minute).values
    fomc = np.isin(ny.dt.date.values, FOMC_DAYS)
    day = T.dt.normalize().values
    n, out, i, cur, cnt = len(C), [], 0, None, 0
    while i < n:
        if day[i] != cur:
            cur, cnt = day[i], 0
        side = h4[i]
        if np.isnan(side) or side == 0 or (need_h1 and h1[i] != side) or cnt >= 2 or np.isnan(lv5[i]).any():
            i += 1; continue
        if news and ((480 <= nymin[i] < 570) or (fomc[i] and nymin[i] >= 720)):
            i += 1; continue
        lvl = lv5[i][0] if side == 1 else lv5[i][1]
        stop = lv5[i][3] if side == 1 else lv5[i][2]
        if not ((side == 1 and H[i] >= lvl) or (side == -1 and L[i] <= lvl)):
            i += 1; continue
        e = (max(O[i], lvl) + spread) if side == 1 else min(O[i], lvl)
        st = stop if side == 1 else stop + spread
        risk = (e - st) * side
        if risk <= 0:
            i += 1; continue
        tp = e + side * tgt * risk
        end = min(n - 1, i + 288 * hold_days)
        res, k = None, i
        for k in range(i, end + 1):
            lo, hi = (L[k], H[k]) if side == 1 else (L[k] + spread, H[k] + spread)
            if (side == 1 and lo <= st) or (side == -1 and hi >= st):
                res = -1.0; break
            if k > i and ((side == 1 and hi >= tp) or (side == -1 and lo <= tp)):
                res = tgt; break
        if res is None:
            res = side * ((C[end] if side == 1 else C[end] + spread) - e) / risk
        out.append((T.iloc[i], side, res))
        cnt += 1
        i = k + 1
    return pd.DataFrame(out, columns=["time", "side", "R"])


if __name__ == "__main__":
    for m in sys.argv[1:] or ["XAUUSD"]:
        p, sp = FILES[m]
        m5 = load(p)
        print(f"{m} PRIMARY (3R)    {stats(run(m5, sp))}", flush=True)
        if m == "XAUUSD":
            print(f"{m} 2x spread       {stats(run(m5, 2 * sp))}")
            print(f"{m} 2R              {stats(run(m5, sp, tgt=2.0))}")
            print(f"{m} 1R              {stats(run(m5, sp, tgt=1.0))}")
            print(f"{m} no news filter  {stats(run(m5, sp, news=False))}")
            print(f"{m} H4 only         {stats(run(m5, sp, need_h1=False))}", flush=True)
