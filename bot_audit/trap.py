"""Trap / inducement (liquidity sweep reversal). Protocol: PROTOCOL_TRAP.md"""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from ifvg import FILES, load, stats


def run(d, spread, level="asia", tgt=2.0, confirm=3):
    T = d["time"]; O, H, L, C = (d[c].values for c in ("open", "high", "low", "close"))
    mins = (T.dt.hour * 60 + T.dt.minute).values
    days = T.dt.normalize()
    out = []
    groups = list(d.groupby(days).indices.items())
    prev = None
    for day, idx in groups:
        idx = np.asarray(idx)
        if level == "asia":
            a = idx[(mins[idx] >= 120) & (mins[idx] < 540)]
            lv = (H[a].max(), L[a].min()) if len(a) >= 30 else None
        else:
            lv = (H[prev].max(), L[prev].min()) if prev is not None and len(prev) > 50 else None
        prev = idx
        if lv is None:
            continue
        hi, lo = lv
        win = idx[(mins[idx] >= 540) & (mins[idx] < 1140)]
        done = {1: False, -1: False}
        breach = {1: None, -1: None}     # side to trade -> (first breach position in win, extreme)
        cnt, k = 0, 0
        while k < len(win) and cnt < 2:
            i = win[k]
            for side, cond, back in ((-1, H[i] > hi, C[i] < hi), (1, L[i] < lo, C[i] > lo)):
                if done[side]:
                    continue
                b = breach[side]
                if b is None and cond:
                    b = breach[side] = [k, H[i] if side == -1 else L[i]]
                if b is not None:
                    b[1] = max(b[1], H[i]) if side == -1 else min(b[1], L[i])
                    if k - b[0] > confirm:
                        breach[side] = None; continue
                    if back and i + 1 < len(O):
                        done[side] = True
                        j = i + 1
                        e = O[j] + (spread if side == 1 else 0)
                        stop = b[1] + spread if side == -1 else b[1]
                        risk = (e - stop) if side == 1 else (stop - e)
                        if risk <= 0:
                            continue
                        tp = e + side * tgt * risk
                        res, m = None, j
                        end = idx[-1]
                        while m <= end and mins[m] < 1380:
                            lo_, hi_ = (L[m], H[m]) if side == 1 else (L[m] + spread, H[m] + spread)
                            if (side == 1 and lo_ <= stop) or (side == -1 and hi_ >= stop):
                                res = -1.0; break
                            if (side == 1 and hi_ >= tp) or (side == -1 and lo_ <= tp):
                                res = tgt; break
                            m += 1
                        if res is None:
                            m = min(m, end)
                            res = side * ((C[m] if side == 1 else C[m] + spread) - e) / risk
                        out.append((T.iloc[j], side, res))
                        cnt += 1
                        nk = np.searchsorted(win, m, side="right")
                        k = max(k, nk - 1)
                        break
            k += 1
    return pd.DataFrame(out, columns=["time", "side", "R"])


if __name__ == "__main__":
    for m in sys.argv[1:] or FILES:
        p, sp = FILES[m]
        d = load(p)
        for lvl in ("asia", "prevday"):
            print(f"{m} {lvl:<8} PRIMARY  {stats(run(d, sp, lvl))}")
            print(f"{m} {lvl:<8} 2x sprd  {stats(run(d, 2 * sp, lvl))}")
            print(f"{m} {lvl:<8} 1R       {stats(run(d, sp, lvl, tgt=1.0))}")
            print(f"{m} {lvl:<8} 3R       {stats(run(d, sp, lvl, tgt=3.0))}")
            print(f"{m} {lvl:<8} M15      {stats(run(load(p, '15min'), sp, lvl, confirm=1))}", flush=True)
        print()
