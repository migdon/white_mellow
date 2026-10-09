"""FVG -> IFVG strategy test. Protocol: PROTOCOL_IFVG.md"""
import sys
import numpy as np
import pandas as pd

D = "/tmp/claude-0/-home-user-white-mellow/17c12a63-a643-5bcb-ae08-5abd467656cb/scratchpad"
FILES = {"NAS100": (f"{D}/realdata/unz/NAS100.r_M5.csv", 1.7), "XAUUSD": (f"{D}/gold/unz/XAUUSD_M5.csv", 0.45),
         "EURUSD": (f"{D}/fx/EURUSD_M5.csv", 0.00012), "GBPUSD": (f"{D}/fx/GBPUSD_M5.csv", 0.00015),
         "USDJPY": (f"{D}/fx/USDJPY_M5.csv", 0.008)}


def load(path, tf="5min"):
    d = pd.read_csv(path, parse_dates=["time"])
    d = d[d["time"] >= "2018-09-01"].reset_index(drop=True)
    d = d[d["time"].diff().dt.total_seconds().fillna(300) <= 3 * 86400].reset_index(drop=True)
    if tf != "5min":
        d = d.set_index("time").resample(tf, label="left", closed="left").agg(
            open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).dropna().reset_index()
    return d


def run(d, spread, tgt=2.0, hours=(15, 19), retest=False, live=24):
    T = d["time"]; O, H, L, C = (d[c].values for c in ("open", "high", "low", "close"))
    n = len(C)
    pc = np.r_[C[0], C[:-1]]
    atr = pd.Series(np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))).rolling(14).mean().values
    mins = (T.dt.hour * 60 + T.dt.minute).values
    day = T.dt.normalize().values
    fvgs = []          # [start_idx, kind(+1 bull/-1 bear), lo, hi, used]
    out, i, cur, cnt = [], 20, None, 0
    while i < n - 2:
        if day[i] != cur:
            cur, cnt = day[i], 0
        if L[i] > H[i - 2] and L[i] - H[i - 2] >= 0.25 * atr[i]:
            fvgs.append([i - 2, 1, H[i - 2], L[i], False])
        elif H[i] < L[i - 2] and L[i - 2] - H[i] >= 0.25 * atr[i]:
            fvgs.append([i - 2, -1, H[i], L[i - 2], False])
        fvgs = [f for f in fvgs if i - (f[0] + 2) <= live and not f[4]]
        sig = None
        for f in fvgs:
            if f[0] + 2 >= i:
                continue
            if f[1] == 1 and C[i] < f[2]:
                sig = (-1, f); break
            if f[1] == -1 and C[i] > f[3]:
                sig = (1, f); break
        ok_time = hours is None or hours[0] * 60 <= mins[i] < hours[1] * 60
        if sig and ok_time and cnt < 2:
            side, f = sig
            f[4] = True
            stop = (H[f[0]:i + 1].max() + spread) if side == -1 else L[f[0]:i + 1].min()   # short stop measured on ask
            j = i + 1
            if retest:          # limit at the IFVG zone edge nearest price, valid 6 bars
                lvl = f[2] if side == -1 else f[3]
                j = next((k for k in range(i + 1, min(n, i + 7)) if (side == -1 and H[k] >= lvl) or (side == 1 and L[k] <= lvl)), None)
                if j is None:
                    i += 1; continue
                e = (max(lvl, O[j]) if side == -1 else min(lvl, O[j]) + spread)
            else:
                e = O[j] + (spread if side == 1 else 0)
            risk = (e - stop) if side == 1 else (stop - e)
            if risk <= 0:
                i += 1; continue
            tp = e + side * tgt * risk
            res, k = None, j
            while k < n and day[k] == day[j] and mins[k] < 23 * 60:
                lo, hi = (L[k], H[k]) if side == 1 else (L[k] + spread, H[k] + spread)
                if (side == 1 and lo <= stop) or (side == -1 and hi >= stop):
                    res = -1.0; break
                if (side == 1 and hi >= tp) or (side == -1 and lo <= tp):
                    res = tgt; break
                k += 1
            if res is None:
                k = min(k, n - 1)
                res = side * ((C[k - 1] if side == 1 else C[k - 1] + spread) - e) / risk
            out.append((T.iloc[j], side, res))
            cnt += 1
            fvgs = []
            i = k + 1
            continue
        i += 1
    return pd.DataFrame(out, columns=["time", "side", "R"])


def stats(t):
    r = t["R"].values
    if len(r) < 10:
        return f"n={len(r)}"
    yrs = (t["time"].iloc[-1] - t["time"].iloc[0]).days / 365.25
    h = len(r) // 2
    return (f"n={len(r):5d} ({len(r)/yrs:4.0f}/yr) win {np.mean(r>0)*100:4.1f}%  meanR {r.mean():+.3f}  "
            f"t {r.mean()/r.std(ddof=1)*np.sqrt(len(r)):+.2f}  halves {r[:h].mean():+.3f}/{r[h:].mean():+.3f}  R/yr {r.sum()/yrs:+.1f}")


if __name__ == "__main__":
    for m in sys.argv[1:] or FILES:
        p, sp = FILES[m]
        d = load(p)
        print(f"\n{m} PRIMARY       {stats(run(d, sp))}")
        print(f"{m} 2x spread     {stats(run(d, 2 * sp))}")
        print(f"{m} 1R            {stats(run(d, sp, tgt=1.0))}")
        print(f"{m} 3R            {stats(run(d, sp, tgt=3.0))}")
        print(f"{m} all hours     {stats(run(d, sp, hours=None))}")
        print(f"{m} retest entry  {stats(run(d, sp, retest=True))}")
        print(f"{m} M15           {stats(run(load(p, '15min'), sp, live=8))}", flush=True)
        if True:
            print(f"{m} London 9-12   {stats(run(d, sp, hours=(9, 12)))}")
            print(f"{m} M15 London    {stats(run(load(p, '15min'), sp, live=8, hours=(9, 12)))}")
            print(f"{m} H1 NY+London  {stats(run(load(p, '60min'), sp, live=4, hours=(9, 19)))}", flush=True)
