"""Gold around the clock: long Asia session, short London/NY. Protocol: PROTOCOL_GOLD_CLOCK.md"""
import numpy as np
import pandas as pd

S = "/tmp/claude-0/-home-user-white-mellow/17c12a63-a643-5bcb-ae08-5abd467656cb/scratchpad"
SP = 0.43
d = pd.read_csv(f"{S}/gold/unz/XAUUSD_M5.csv", parse_dates=["time"])
d = d[d.time >= "2018-09-01"]
d["day"] = d.time.dt.normalize()
hm = d.time.dt.hour * 60 + d.time.dt.minute


def price_at(minute):
    x = d[hm >= minute].groupby("day").first()
    return x["open"]


p0105, p1000, p2350 = price_at(65), price_at(600), price_at(1430)
df = pd.DataFrame({"a": p0105, "b": p1000, "c": p2350}).dropna()
df = df[df.index.dayofweek < 5]


def st(name, r):
    r = r.dropna(); h = len(r) // 2
    print(f"{name:<34} n={len(r):5d} mean {r.mean()*100:+.4f}%/day  t {r.mean()/r.std(ddof=1)*np.sqrt(len(r)):+.2f}  "
          f"win {np.mean(r>0)*100:3.0f}%  halves {r.iloc[:h].mean()*100:+.4f}/{r.iloc[h:].mean()*100:+.4f}  "
          f"per year {r.mean()*252*100:+.1f}%")


for mult, tag in ((0, " (no cost)"), (1, ""), (2, " (2x spread)")):
    g1 = df.b / df.a - 1 - mult * SP / df.a
    g2 = -(df.c / df.b - 1) - mult * SP / df.b
    st("G1 long Asia 01:05-10:00" + tag, g1)
    st("G2 short London/NY 10:00-23:50" + tag, g2)
g1 = df.b / df.a - 1 - SP / df.a
g2 = -(df.c / df.b - 1) - SP / df.b
print("\nyear by year (net, % per year):")
print(pd.DataFrame({"G1": g1.groupby(g1.index.year).sum() * 100, "G2": g2.groupby(g2.index.year).sum() * 100,
                    "gold buy&hold": (df.c / df.a - 1).groupby(df.index.year).sum() * 100}).round(1).to_string())
