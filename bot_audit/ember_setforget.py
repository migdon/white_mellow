"""EMBER gold as a pure set-and-forget trade: the same daily levels (day open +/- 0.8 x ATR10) and 2 x ATR stop,
but the exit is ONLY a take-profit or the stop (no next-day exit; positions still open after 15 days are closed).
One position at a time. Spread $0.45; Atlas swap (long -$0.66, short +$0.30 per oz a night at $4,192, scaled to price,
Wednesday x3) included."""
import numpy as np
import pandas as pd
from bot_audit.ember_bt import load_server_m5, ATR_N

S = "/tmp/claude-0/-home-user-white-mellow/17c12a63-a643-5bcb-ae08-5abd467656cb/scratchpad"
SP = 0.45
m5 = load_server_m5(f"{S}/gold/unz/XAUUSD_M5.csv")
m5 = m5[m5.time >= "2018-09-01"].reset_index(drop=True)
daily = m5.groupby("day").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
pc = daily.close.shift(1)
atr = pd.concat([daily.high - daily.low, (daily.high - pc).abs(), (daily.low - pc).abs()], axis=1).max(axis=1).rolling(ATR_N).mean().shift(1)
days = list(daily.index)
starts = m5.groupby("day").indices
O, H, L, C = (m5[c].values for c in ("open", "high", "low", "close"))
dayidx = {d: i for i, d in enumerate(days)}


def run(tp_atr, stop_atr=2.0, max_days=15):
    out, di = [], 0
    while di < len(days):
        d = days[di]; a = atr.iloc[di]
        if pd.isna(a) or a <= 0:
            di += 1; continue
        idx = starts[d]; op = O[idx[0]]
        up, dn = op + 0.8 * a, op - 0.8 * a
        entry = None
        for j in idx:
            if H[j] >= up or L[j] <= dn:
                side = 1 if (H[j] >= up and (L[j] > dn or abs(O[j] - up) <= abs(O[j] - dn))) else -1
                lvl = up if side == 1 else dn
                e = (max(O[j], lvl) + SP) if side == 1 else min(O[j], lvl)
                entry = (j, side, e, lvl - side * stop_atr * a, e + side * tp_atr * a, a); break
        if entry is None:
            di += 1; continue
        j0, side, e, sl, tp, a0 = entry
        end = min(len(C) - 1, j0 + 288 * max_days)
        res, k = None, j0
        for k in range(j0, end + 1):
            lo, hi = (L[k], H[k]) if side == 1 else (L[k] + SP, H[k] + SP)
            if (side == 1 and lo <= sl) or (side == -1 and hi >= sl):
                px = sl; break
            if k > j0 and ((side == 1 and hi >= tp) or (side == -1 and lo <= tp)):
                px = tp; break
        else:
            px = C[end] + (SP if side == -1 else 0)
        nights = 0
        for dd in pd.date_range(m5.day[j0] + pd.Timedelta(days=1), m5.day[k], freq="D"):
            nights += 3 if dd.weekday() == 3 else (0 if dd.weekday() >= 5 else 1)
        swap = (-0.663 if side == 1 else 0.2992) / 4191.85 * e * nights
        risk = stop_atr * a0
        out.append((m5.time[j0], (side * (px - e) + swap) / risk, nights))
        di = dayidx.get(m5.day[k], di) + 1
    return pd.DataFrame(out, columns=["time", "R", "nights"])


def st(lab, t):
    r = t.R.values; h = len(r) // 2; yrs = (t.time.iloc[-1] - t.time.iloc[0]).days / 365.25
    eq = np.cumsum(r)
    print(f"{lab:<34} n={len(r):4d} ({len(r)/yrs:3.0f}/yr) win {np.mean(r>0)*100:3.0f}% mean {r.mean():+.3f}R "
          f"z {r.mean()/r.std(ddof=1)*np.sqrt(len(r)):+.2f} halves {r[:h].mean():+.3f}/{r[h:].mean():+.3f} "
          f"maxDD {(eq-np.maximum.accumulate(eq)).min():.1f}R avg nights {t.nights.mean():.1f}")


for tp in (1.0, 2.0, 3.0, 4.0):
    st(f"TP {tp:.0f} ATR (= {tp/2:.1f}R), SL 2 ATR", run(tp))
st("no TP, SL only (15-day cap)", run(99.0))
