"""Last-half-hour intraday momentum on NAS100 / SPX500. Protocol: PROTOCOL_LAST_HALF_HOUR.md"""
import numpy as np
import pandas as pd

S = "/tmp/claude-0/-home-user-white-mellow/17c12a63-a643-5bcb-ae08-5abd467656cb/scratchpad"
MK = {"NAS100": (f"{S}/realdata/unz/NAS100.r_M5.csv", 1.87), "SPX500": (f"{S}/realdata/unz/SP500.r_M5.csv", 0.8)}


def st(name, r):
    r = r.dropna(); h = len(r) // 2
    print(f"  {name:<36} n={len(r):5d} mean {r.mean()*100:+.4f}%  t {r.mean()/r.std(ddof=1)*np.sqrt(len(r)):+.2f}  "
          f"win {np.mean(r>0)*100:3.0f}%  halves {r.iloc[:h].mean()*100:+.4f}/{r.iloc[h:].mean()*100:+.4f}  "
          f"per year {r.mean()*252*100:+.1f}%")


for m, (p, sp) in MK.items():
    d = pd.read_csv(p, parse_dates=["time"])
    d = d[d.time >= "2018-09-01"]
    ny = d.time - pd.Timedelta(hours=7)
    d["date"] = ny.dt.normalize(); mins = ny.dt.hour * 60 + ny.dt.minute
    at = lambda t: d[mins == t].groupby("date").open.first()
    px = pd.DataFrame({"p1000": at(600), "p1530": at(930), "p1555": at(955)}).dropna()
    px = px[px.index.dayofweek < 5]
    prev = px.p1555.shift(1)
    s1 = np.sign(px.p1000 / prev - 1); s2 = np.sign(px.p1530 / prev - 1)
    last = px.p1555 / px.p1530 - 1
    print(m)
    for mult, tag in ((0, " (no cost)"), (1, ""), (2, " (2x spread)")):
        c = mult * sp / px.p1530
        st("R1 first 30 min -> last 30 min" + tag, s1 * last - c * (s1 != 0))
        st("R2 rest of day -> last 30 min" + tag, s2 * last - c * (s2 != 0))
    for name, sig, raw in (("R1", s1, px.p1000 / prev - 1), ("R2", s2, px.p1530 / prev - 1)):
        big = raw.abs() >= raw.abs().rolling(250, min_periods=60).quantile(0.8).shift(1)
        st(f"{name} top-20% signal days only", (sig * last - sp / px.p1530)[big])
