"""
5-minute ORB on NAS100 / SPX500 CFDs (Vantage M5, server clock = New York + 7h), real spread cost.

  A  "break" version: first 5-min bar (09:30-09:35 NY) sets the range; the first later bar that trades through the
     high goes long AT the high (stop order), through the low goes short at the low; stop = other side of the range;
     exit at 15:55 NY. One trade a day. A bar that touches both stop and entry side counts the stop (conservative).
  B  Zarattini/Aziz QQQ version: direction of the first 5-min bar (up bar -> long, down -> short, doji -> none),
     enter at the 2nd bar's open, stop = 10% of the 14-day ATR, target 10R, else exit 15:55 NY.
Result in R per trade after one spread per round trip; also as % of price (what the account sees at fixed notional).
"""
import sys
import numpy as np
import pandas as pd

SPREAD = {"NAS100": 1.87, "SPX500": 0.9}
FILES = {"NAS100": "NAS100.r_M5.csv", "SPX500": "SP500.r_M5.csv"}


def load(path):
    d = pd.read_csv(path, parse_dates=["time"])
    d["day"] = d.time.dt.date
    d["hm"] = d.time.dt.hour * 100 + d.time.dt.minute
    return d


def run(d, spread):
    daily = d.groupby("day").agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    tr = np.maximum(daily.h - daily.l, np.maximum((daily.h - daily.c.shift()).abs(), (daily.l - daily.c.shift()).abs()))
    atr = tr.rolling(14).mean().shift()
    A, B = [], []
    for day, g in d.groupby("day"):
        s = g[(g.hm >= 1630) & (g.hm < 2300)]
        if len(s) < 70 or s.hm.iloc[0] != 1630:
            continue
        f = s.iloc[0]; rest = s.iloc[1:]
        hi, lo = f.high, f.low
        rng = hi - lo
        last = rest.iloc[-1].close
        # ---- A
        if rng > 0:
            for _, b in rest.iterrows():
                up, dn = b.high > hi, b.low < lo
                if up and dn:
                    A.append((day, -1 - spread / rng, -(rng + spread) / hi)); break
                if up or dn:
                    side = 1 if up else -1
                    entry = hi if up else lo
                    stop = lo if up else hi
                    after = rest.loc[b.name:]
                    pnl = None
                    for _, x in after.iterrows():
                        if (side == 1 and x.low <= stop) or (side == -1 and x.high >= stop):
                            pnl = -rng; break
                    if pnl is None:
                        pnl = side * (last - entry)
                    A.append((day, (pnl - spread) / rng, (pnl - spread) / entry)); break
        # ---- B
        a = atr.get(day, np.nan)
        if np.isnan(a) or f.close == f.open:
            continue
        side = 1 if f.close > f.open else -1
        entry = rest.iloc[0].open
        risk = 0.10 * a
        stop, tgt = entry - side * risk, entry + side * 10 * risk
        pnl = None
        for _, x in rest.iterrows():
            if (side == 1 and x.low <= stop) or (side == -1 and x.high >= stop):
                pnl = -risk; break
            if (side == 1 and x.high >= tgt) or (side == -1 and x.low <= tgt):
                pnl = 10 * risk; break
        if pnl is None:
            pnl = side * (last - entry)
        B.append((day, (pnl - spread) / risk, (pnl - spread) / entry))
    return pd.DataFrame(A, columns=["day", "R", "pct"]), pd.DataFrame(B, columns=["day", "R", "pct"])


def report(name, t):
    t = t.copy(); t["day"] = pd.to_datetime(t.day)
    n = len(t); m = t.R.mean(); z = m / t.R.std() * np.sqrt(n)
    half = t.day.iloc[n // 2]
    h1, h2 = t[t.day < half].R.mean(), t[t.day >= half].R.mean()
    yrs = t.groupby(t.day.dt.year).R.mean().round(3).to_dict()
    print(f"{name}: {n} trades {t.day.min():%Y-%m}..{t.day.max():%Y-%m}  win {(t.R > 0).mean()*100:.0f}%  "
          f"avg {m:+.3f}R  z {z:+.2f}  halves {h1:+.3f}/{h2:+.3f}  avg/trade {t.pct.mean()*100:+.4f}% of price")
    print(f"    by year: {yrs}")


if __name__ == "__main__":
    base = sys.argv[1]
    for sym, fn in FILES.items():
        d = load(f"{base}/{fn}")
        d = d[d.time >= "2019-01-01"]
        A, B = run(d, SPREAD[sym])
        report(f"{sym} A break-of-range", A)
        report(f"{sym} B first-bar direction 10R", B)
