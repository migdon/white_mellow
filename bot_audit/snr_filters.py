"""Screen of POI / entry filters on the S/R rejection trades (gold). Protocol addendum in PROTOCOL_SNR_REJECTION.md."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from snr_rejection import FILES, K, load, run

m5, b = load(FILES["XAUUSD"][0])
t = run(m5, b, FILES["XAUUSD"][1])
O, H, L, C, TV = (b[c].values for c in ("open", "high", "low", "close", "tv"))
T = b["time"]
pc = np.r_[C[0], C[:-1]]
atr = pd.Series(np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))).rolling(14).mean().values
day = (T.dt.floor("D")).values
dh = b.groupby(day)["high"].max(); dl = b.groupby(day)["low"].min()
prev_h = pd.Series(day).map(dh.shift(1)).values; prev_l = pd.Series(day).map(dl.shift(1)).values
tvavg = pd.Series(TV).rolling(20).mean().shift(1).values
f = {k: [] for k in ("F1 touches>=2", "F2 prev-day H/L", "F3 London/NY", "F4 pin/hammer", "F5 volume spike", "F6 round $10")}
for _, x in t.iterrows():
    r, s, e, a = int(x.r), x.side, x.ext, atr[int(x.r)]
    piv = [j for j in range(max(K, r - 240), r - K) if (L[j] == L[j - K:j + K + 1].min() if s == 1 else H[j] == H[j - K:j + K + 1].max())]
    f["F1 touches>=2"].append(sum(abs((L[j] if s == 1 else H[j]) - e) <= 0.3 * a for j in piv) >= 2)
    f["F2 prev-day H/L"].append(abs(e - (prev_l[r] if s == 1 else prev_h[r])) <= 0.3 * a)
    f["F3 London/NY"].append(10 <= pd.Timestamp(x.time).hour < 23)
    wick = (min(O[r], C[r]) - L[r]) if s == 1 else (H[r] - max(O[r], C[r]))
    f["F4 pin/hammer"].append(wick >= 0.5 * (H[r] - L[r]))
    f["F5 volume spike"].append(TV[r] > 1.5 * tvavg[r])
    f["F6 round $10"].append(abs(e - round(e / 10) * 10) <= 0.3 * a)
print(f"ALL      n={len(t)} win {np.mean(t.R>0)*100:.0f}% meanR {t.R.mean():+.3f}")
for k, m in f.items():
    for lab, mm in (("keep", np.array(m)), ("drop", ~np.array(m))):
        r = t.R.values[mm]; h = len(r) // 2
        tt = r.mean() / r.std(ddof=1) * np.sqrt(len(r)) if len(r) > 2 else 0
        print(f"{k:<17}{lab}  n={len(r):4d} win {np.mean(r>0)*100:3.0f}%  meanR {r.mean():+.3f}  t {tt:+.2f}  halves {r[:h].mean():+.3f}/{r[h:].mean():+.3f}")
