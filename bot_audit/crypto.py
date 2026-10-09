"""Published crypto strategies on BTCUSD. Protocol: PROTOCOL_CRYPTO.md"""
import numpy as np
import pandas as pd

D = "/tmp/claude-0/-home-user-white-mellow/17c12a63-a643-5bcb-ae08-5abd467656cb/scratchpad"
m5 = pd.read_csv(f"{D}/btc/BTCUSD_M5.csv", parse_dates=["time"])
m5 = m5[m5["time"] >= "2018-09-01"].reset_index(drop=True)
day = m5.groupby(m5["time"].dt.normalize()).agg(open=("open", "first"), close=("close", "last"))


def report(name, r, k=1.0):
    r = pd.Series(r).dropna()
    h = len(r) // 2
    t = r.mean() / r.std(ddof=1) * np.sqrt(len(r))
    eq = r.cumsum()
    print(f"{name:<40} n={len(r):5d} mean {r.mean()*100:+.4f}%  t {t:+.2f}  halves {r[:h].mean()*100:+.4f}/{r[h:].mean()*100:+.4f}  "
          f"sum {r.sum()*100:+.0f}%  maxDD {(eq - eq.cummax()).min()*100:.0f}%")


def daily_pos_returns(pos, cost):
    """pos[d] = position held from open of day d to open of day d+1 (decided on closes up to d-1)."""
    o = day["open"].values
    ret = np.r_[o[1:] / o[:-1] - 1, np.nan]
    turn = np.abs(np.diff(np.r_[0, pos]))
    return pos * ret - turn * cost - np.abs(pos) * 0.00041 * (cost / 0.0007)


for mult, tag in ((1, ""), (2, " 2x cost")):
    cost = 0.0007 * mult
    c = day["close"].values
    # R1 weekly TSMOM: decide on day d (using closes up to d-1) every 7th day
    pos_l, pos_ls = np.zeros(len(c)), np.zeros(len(c))
    for d in range(8, len(c)):
        if (d - 8) % 7 == 0:
            s = 1.0 if c[d - 1] / c[d - 8] - 1 > 0 else 0.0
            cur_l, cur_ls = s, (1.0 if s else -1.0)
        pos_l[d], pos_ls[d] = cur_l, cur_ls
    report("R1 weekly TSMOM long/flat" + tag, daily_pos_returns(pos_l, cost))
    report("R1 weekly TSMOM long/short (info)" + tag, daily_pos_returns(pos_ls, cost))
    # R3 SMA50 filter
    sma = pd.Series(c).rolling(50).mean().values
    pos3 = np.r_[0, (c[:-1] > sma[:-1]).astype(float)]
    report("R3 close > SMA50 long/flat" + tag, daily_pos_returns(pos3, cost))
    report("   buy & hold (reference)" + tag, daily_pos_returns(np.ones(len(c)), cost))

# R2 intraday TSMOM in UTC
ny = (m5["time"] - pd.Timedelta(hours=7)).dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
m5["utc"] = ny.dt.tz_convert("UTC").dt.tz_localize(None)
m5 = m5.dropna(subset=["utc"])
u = m5.set_index("utc")
first = u.between_time("00:00", "00:25")
last = u.between_time("23:30", "23:55")
g1 = first.groupby(first.index.normalize()).agg(o=("open", "first"), c=("close", "last"))
g2 = last.groupby(last.index.normalize()).agg(o=("open", "first"), c=("close", "last"))
j = g1.join(g2, lsuffix="1", rsuffix="2", how="inner")
sig = np.sign(j["c1"] - j["o1"])
for mult in (1, 2):
    r = sig * (j["c2"] / j["o2"] - 1) - (sig != 0) * 0.0007 * mult
    report(f"R2 intraday TSMOM (UTC){' 2x cost' if mult == 2 else ''}", r.values)
print("R2 gross (no cost):", f"{(sig * (j['c2'] / j['o2'] - 1)).mean()*100:+.4f}% per trade")
