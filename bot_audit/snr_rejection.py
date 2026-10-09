"""S/R rejection + momentum leg + 30m reversal candle, 1R against trend / 2R with trend. Protocol: PROTOCOL_SNR_REJECTION.md"""
import sys
import numpy as np
import pandas as pd

D = "/tmp/claude-0/-home-user-white-mellow/17c12a63-a643-5bcb-ae08-5abd467656cb/scratchpad"
FILES = {"XAUUSD": (f"{D}/gold/unz/XAUUSD_M5.csv", 0.45), "NAS100": (f"{D}/realdata/unz/NAS100.r_M5.csv", 1.7),
         "EURUSD": (f"{D}/fx/EURUSD_M5.csv", 0.00012)}
K = 3


def load(path):
    d = pd.read_csv(path, parse_dates=["time"])
    d = d[d["time"] >= "2018-09-01"].reset_index(drop=True)
    d = d[d["time"].diff().dt.total_seconds().fillna(300) <= 3 * 86400]
    b = d.set_index("time").resample("30min", label="left", closed="left").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")).dropna().reset_index()
    return d.reset_index(drop=True), b


def run(m5, b, spread, leg_min=3, zone=0.3, mode="trend", stop_after_loss=True):
    O, H, L, C = (b[c].values for c in ("open", "high", "low", "close"))
    T = b["time"].values
    n = len(b)
    pc = np.r_[C[0], C[:-1]]
    atr = pd.Series(np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))).rolling(14).mean().values
    ema = pd.Series(C).ewm(span=200, adjust=False).mean().values
    rng = np.maximum(H - L, 1e-12)
    clean = np.abs(C - O) / rng >= 0.5
    bear = (C < O) & clean & (C < pc)
    bull = (C > O) & clean & (C > pc)
    run_bear = np.zeros(n, int); run_bull = np.zeros(n, int)
    for i in range(1, n):
        run_bear[i] = run_bear[i - 1] + 1 if bear[i] else 0
        run_bull[i] = run_bull[i - 1] + 1 if bull[i] else 0
    sl_idx = [j for j in range(K, n - K) if L[j] == L[j - K:j + K + 1].min()]
    sh_idx = [j for j in range(K, n - K) if H[j] == H[j - K:j + K + 1].max()]
    m5t = m5["time"].values
    mO, mH, mL, mC = (m5[c].values for c in ("open", "high", "low", "close"))
    pos_of = np.searchsorted(m5t, T)
    trades = []
    busy_until = -1
    day_count, day_lost, cur_day = 0, False, None
    for r in range(260, n - 2):
        day = T[r + 1].astype("datetime64[D]")
        if day != cur_day:
            cur_day, day_count, day_lost = day, 0, False
        if r + 1 <= busy_until or day_count >= 3 or (stop_after_loss and day_lost) or not atr[r] > 0:
            continue
        for side in (1, -1):
            legn = run_bear[r - 1] if side == 1 else run_bull[r - 1]
            if legn < leg_min or not ((C[r] > O[r]) if side == 1 else (C[r] < O[r])):
                continue
            s = r - legn
            if side == 1:
                ext = L[s:r + 1].min()
                lv = [L[j] for j in sl_idx if r - 240 <= j and j + K < s]
            else:
                ext = H[s:r + 1].max()
                lv = [H[j] for j in sh_idx if r - 240 <= j and j + K < s]
            if not lv or min(abs(ext - x) for x in lv) > zone * atr[r]:
                continue
            trig = H[r] if side == 1 else L[r]
            # fill during bar r+1 on M5
            a, z = pos_of[r + 1], pos_of[r + 2] if r + 2 < n else len(m5t)
            fill = None
            for j in range(a, z):
                if side == 1 and mH[j] >= trig:
                    fill = (j, max(trig, mO[j]) + spread); break
                if side == -1 and mL[j] <= trig:
                    fill = (j, min(trig, mO[j])); break
            if fill is None:
                continue
            j0, px = fill
            risk = (px - ext) if side == 1 else (ext - px)
            if risk <= 0:
                continue
            aligned = (C[r] > ema[r]) if side == 1 else (C[r] < ema[r])
            tgt = {"trend": 2.0 if aligned else 1.0, "1R": 1.0, "2R": 2.0}[mode]
            tp = px + side * tgt * risk
            end = min(len(m5t) - 1, j0 + 288)
            res, jx = None, end
            for j in range(j0, end + 1):
                lo, hi = (mL[j], mH[j]) if side == 1 else (mL[j] + spread, mH[j] + spread)
                if j > j0 or True:
                    if (side == 1 and lo <= ext) or (side == -1 and hi >= ext):
                        res, jx = -1.0 - (0 if side == 1 else 0), j; break
                    if (side == 1 and hi >= tp) or (side == -1 and lo <= tp):
                        res, jx = tgt, j; break
            if res is None:
                exitpx = mC[end] if side == 1 else mC[end] + spread
                res = side * (exitpx - px) / risk
            trades.append((T[r + 1], side, aligned, res, risk / atr[r]))
            day_count += 1
            day_lost = res < 0
            busy_until = int(np.searchsorted(T, m5t[jx], side="right")) - 1
            break
    return pd.DataFrame(trades, columns=["time", "side", "aligned", "R", "risk_atr"])


def stats(t):
    r = t["R"].values
    if len(r) < 10:
        return f"n={len(r)}"
    yrs = (t["time"].iloc[-1] - t["time"].iloc[0]).days / 365.25
    h = len(r) // 2
    tt = r.mean() / r.std(ddof=1) * np.sqrt(len(r))
    return (f"n={len(r):5d} ({len(r)/yrs:4.0f}/yr) win {np.mean(r>0)*100:4.1f}%  meanR {r.mean():+.3f}  t {tt:+.2f}  "
            f"halves {r[:h].mean():+.3f}/{r[h:].mean():+.3f}  sumR/yr {r.sum()/yrs:+.1f}")


if __name__ == "__main__":
    for m in sys.argv[1:] or FILES:
        path, sp = FILES[m]
        m5, b = load(path)
        base = run(m5, b, sp)
        print(f"\n{m}  PRIMARY      {stats(base)}")
        print(f"{m}  2x spread    {stats(run(m5, b, 2 * sp))}")
        if m == "XAUUSD":
            print(f"{m}  aligned(2R)  {stats(base[base.aligned])}")
            print(f"{m}  against(1R)  {stats(base[~base.aligned])}")
            for lab, kw in [("leg>=4", dict(leg_min=4)), ("zone 0.2", dict(zone=0.2)), ("zone 0.5", dict(zone=0.5)),
                            ("always 1R", dict(mode="1R")), ("always 2R", dict(mode="2R")), ("no stop-after-loss", dict(stop_after_loss=False))]:
                print(f"{m}  {lab:<12} {stats(run(m5, b, sp, **kw))}")
        base.to_csv(f"{D}/snr_{m}.csv", index=False)
