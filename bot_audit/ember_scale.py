"""EMBER gold: scale in while the move continues / hold winners longer. Screen on EMBER's own trades (ember_XAUUSD.csv).
B (add-on): when price reaches entry + k x ATR in the trade's favour, add a second equal position; its stop = the first entry
   (so the add-on risks k x ATR = k/2 R); everything exits at EMBER's normal exit time or at its stop.
A (hold longer): at EMBER's normal exit, a trade that is in profit is kept with a 2 x ATR trailing stop (from the best price),
   up to 10 more days. Spread $0.45 on every entry/exit, no swap (the longer holds would pay more of it)."""
import numpy as np
import pandas as pd
from bot_audit.ember_bt import load_server_m5

S = "/tmp/claude-0/-home-user-white-mellow/17c12a63-a643-5bcb-ae08-5abd467656cb/scratchpad"
SP = 0.45
m5 = load_server_m5(f"{S}/gold/unz/XAUUSD_M5.csv")
T = m5["time"].values; H, L, C = m5["high"].values, m5["low"].values, m5["close"].values
t = pd.read_csv(f"{S}/ember_XAUUSD.csv", parse_dates=["entry_time", "exit_time"])
ei = np.searchsorted(T, t.entry_time.values); xi = np.searchsorted(T, t.exit_time.values)


def addon(k):
    out = []
    for r, a, b in zip(t.itertuples(), ei, xi):
        d, atr, base = r.dir, r.risk / 2, r.R
        lvl = r.entry + d * k * atr
        extra = 0.0
        for j in range(a + 1, b):
            if (d > 0 and L[j] <= r.entry - r.risk) or (d < 0 and H[j] + SP >= r.entry + r.risk):
                break                                            # the first trade was stopped before any add
            if (d > 0 and H[j] >= lvl) or (d < 0 and L[j] <= lvl):
                e2 = lvl + (SP if d > 0 else 0); st2 = r.entry
                px = None
                for q in range(j + 1, b + 1):
                    if (d > 0 and L[q] <= st2) or (d < 0 and H[q] + SP >= st2):
                        px = st2; break
                if px is None:
                    px = r.exit
                extra = d * (px - e2) / r.risk
                break
        out.append(base + extra)
    return np.array(out)


def hold_longer(trail=2.0, max_days=10):
    out = []
    for r, a, b in zip(t.itertuples(), ei, xi):
        if r.reason == "stop" or r.R <= 0:
            out.append(r.R); continue
        d, atr = r.dir, r.risk / 2
        best = r.exit; px = None
        for q in range(b, min(len(T), b + 288 * max_days)):
            best = max(best, H[q]) if d > 0 else min(best, L[q])
            stop = best - d * trail * atr
            if (d > 0 and L[q] <= stop) or (d < 0 and H[q] + SP >= stop):
                px = stop; break
        if px is None:
            px = C[min(len(T) - 1, b + 288 * max_days - 1)] + (SP if d < 0 else 0)
        out.append(d * (px - r.entry) / r.risk)
    return np.array(out)


def st(name, r):
    h = len(r) // 2
    eq = np.cumsum(r)
    print(f"{name:<38} mean {r.mean():+.3f}R  z {r.mean()/r.std(ddof=1)*np.sqrt(len(r)):+.2f}  total {r.sum():+.0f}R  "
          f"halves {r[:h].mean():+.3f}/{r[h:].mean():+.3f}  worst drawdown {(eq - np.maximum.accumulate(eq)).min():.1f}R")


st("EMBER now", t.R.values)
for k in (0.5, 1.0, 1.5):
    st(f"B add-on at +{k} ATR (stop = first entry)", addon(k))
for tr in (1.5, 2.0, 3.0):
    st(f"A hold winners, {tr} ATR trailing stop", hold_longer(tr))
