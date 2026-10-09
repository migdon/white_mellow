"""
Pre-registered (2026-10-09, written before running): two classic public strategies, daily bars, tradable prices.
  RSI2   (Connors) long-only on SPX500, NAS100: close > SMA200 and RSI(2) < 10 -> buy next open; exit next open after close > SMA5
  TURTLE (System 1, simplified) on XAUUSD, NAS100, SPX500, BTCUSD, long+short: close > 20d high -> long next open
         (< 20d low -> short); exit next open after the opposite 10d break, or stop 2xATR(20) from entry
Costs: spread once per round trip (SPX 0.6, NAS 1.7, gold 0.45, BTC 67) + financing per night held
       (indices 0.02%, gold 0.02%, BTC 0.041% = 15%/yr). Returns at 1x notional.
PASS (per strategy, all markets pooled): t >= 2.24 on daily P&L (Bonferroni, 2 tests), both halves positive, >= 100 trades.
"""
import sys
import numpy as np
import pandas as pd

D = sys.argv[1]
FILES = {"SPX500": (f"{D}/realdata/unz/SP500.r_M5.csv", 0.6, 0.0002), "NAS100": (f"{D}/realdata/unz/NAS100.r_M5.csv", 1.7, 0.0002),
         "XAUUSD": (f"{D}/gold/unz/XAUUSD_M5.csv", 0.45, 0.0002), "BTCUSD": (f"{D}/btc/BTCUSD_M5.csv", 67.0, 0.00041)}


def daily(path):
    d = pd.read_csv(path, parse_dates=["time"])
    d["day"] = d["time"].dt.normalize()            # pre-2018 rows are already daily bars; M5 rows aggregate per server day
    return d.groupby("day").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))


def rsi(c, n=2):
    ch = c.diff()
    up, dn = ch.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(), (-ch.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def simulate(df, sig_entry, sig_exit, spread, fin, stop_mult=None):
    """sig_entry: +1/-1/0 decided at close t (trade at open t+1); sig_exit(pos, i) -> bool at close i."""
    O, H, L, C = (df[c].values for c in ("open", "high", "low", "close"))
    tr = (pd.concat([df.high - df.low, (df.high - df.close.shift()).abs(), (df.low - df.close.shift()).abs()], axis=1)
          .max(axis=1).rolling(20).mean().values)
    pnl = np.zeros(len(df)); trades = []
    pos, entry, stop, ei = 0, 0.0, None, 0
    for i in range(1, len(df)):
        if pos:                                    # mark the day
            if stop is not None and ((pos > 0 and L[i] <= stop) or (pos < 0 and H[i] >= stop)):
                px = min(O[i], stop) if pos > 0 else max(O[i], stop)
                pnl[i] += pos * (px - C[i - 1]) / entry - spread / entry
                trades.append(pnl[ei:i + 1].sum()); pos = 0
                continue
            pnl[i] += pos * (C[i] - C[i - 1]) / entry - fin
            if sig_exit(pos, i):                   # exit at next open
                if i + 1 < len(df):
                    pnl[i + 1] += pos * (O[i + 1] - C[i]) / entry - spread / entry
                    trades.append(pnl[ei:i + 2].sum())
                pos = 0
                continue
        if not pos and sig_entry[i] and i + 1 < len(df):
            pos, entry, ei = int(sig_entry[i]), O[i + 1], i + 1
            stop = entry - pos * stop_mult * tr[i] if stop_mult else None
            pnl[i + 1] += pos * (C[i + 1] - O[i + 1]) / entry - fin
            if pos and stop is not None and ((pos > 0 and L[i + 1] <= stop) or (pos < 0 and H[i + 1] >= stop)):
                pass                               # handled on the next loop iteration's bar is skipped; rare, ignored
    return pd.Series(pnl, index=df.index), trades


def stats(p, n_tr):
    p = p[p.ne(0).idxmax():]
    t = p.mean() / p.std() * np.sqrt(len(p)); h = len(p) // 2
    return t, p.iloc[:h].sum(), p.iloc[h:].sum(), p.mean() / p.std() * np.sqrt(252), p.sum()


res = {"RSI2": [], "TURTLE": []}
for m, (f, sp, fin) in FILES.items():
    df = daily(f)
    if m in ("SPX500", "NAS100"):
        c = df.close; r = rsi(c)
        ent = ((c > c.rolling(200).mean()) & (r < 10)).astype(int).values
        sma5 = c.rolling(5).mean().values
        p, t = simulate(df, ent, lambda pos, i: df.close.values[i] > sma5[i], sp, fin)
        res["RSI2"].append((m, p, t))
    c = df.close
    hi20, lo20 = df.high.rolling(20).max().shift(), df.low.rolling(20).min().shift()
    hi10, lo10 = df.high.rolling(10).max().shift().values, df.low.rolling(10).min().shift().values
    ent = np.where(c > hi20, 1, np.where(c < lo20, -1, 0))
    p, t = simulate(df, ent, lambda pos, i: (pos > 0 and c.values[i] < lo10[i]) or (pos < 0 and c.values[i] > hi10[i]), sp, fin, 2.0)
    res["TURTLE"].append((m, p, t))

for name, rows in res.items():
    print(f"\n== {name}")
    for m, p, t in rows:
        tt, h1, h2, sh, tot = stats(p, len(t))
        dd = ((1 + p.cumsum()) - (1 + p.cumsum()).cummax()).min()
        print(f"  {m:<7} {p.index[p.ne(0).idxmax() == p.index].min() if False else p[p.ne(0)].index[0].date()}  trades {len(t):>4}  "
              f"win {np.mean(np.array(t) > 0):.0%}  total {tot * 100:+6.1f}%  Sharpe {sh:+.2f}  t {tt:+.2f}  maxDD {dd * 100:.1f}%  halves {h1 * 100:+.1f}/{h2 * 100:+.1f}%")
    pool = pd.concat([p / p[p.ne(0)].std() for _, p, _ in rows], axis=1).fillna(0).mean(axis=1)
    ntr = sum(len(t) for _, _, t in rows)
    tt, h1, h2, sh, _ = stats(pool, ntr)
    ok = tt >= 2.24 and h1 > 0 and h2 > 0 and ntr >= 100
    print(f"  POOLED: t {tt:+.2f}  Sharpe {sh:+.2f}  halves {'+' if h1 > 0 else '-'}/{'+' if h2 > 0 else '-'}  trades {ntr} -> {'PASS' if ok else 'FAIL'}")
