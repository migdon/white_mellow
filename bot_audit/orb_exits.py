"""ORB (user's orb_app.py rules) with different exits: does the trade management fix the 1R loss / 0.75R win problem?
Entry as orb_app.py: range = server 16:00-17:15 (NY 9:00-10:15), first M5 CLOSE beyond it in the allowed direction
(EURUSD short, USDJPY long, as SYMBOL_USD_STRENGTH_DIRECTION) -> enter next bar open; stop = opposite range side -/+ max(ATR14(M5), floor).
Assumptions (not read from the bot): entries until 23:00 server, anything open is closed at 23:55 server. Same bar stop+target -> stop."""
import numpy as np
import pandas as pd

D = "/tmp/claude-0/-home-user-white-mellow/17c12a63-a643-5bcb-ae08-5abd467656cb/scratchpad"
MK = {"EURUSD": (f"{D}/fx/EURUSD_M5.csv", -1, 0.00012, 0.00030), "USDJPY": (f"{D}/fx/USDJPY_M5.csv", 1, 0.008, 0.030)}
EXITS = {"current: 50% at 0.75R + BE, rest to 1x range": ("partial", 0.75, None),
         "no partial, all to 1x range (no BE)": ("mm", None, None),
         "fixed 1R": ("fixed", None, 1.0), "fixed 1.5R": ("fixed", None, 1.5), "fixed 2R": ("fixed", None, 2.0),
         "BE at 1R, target 2R": ("be", 1.0, 2.0), "no target (time exit only)": ("fixed", None, 99.0),
         "25% every 0.5R, stop trails 1 step behind": ("ladder", 0.5, None),
         "25% every 0.75R, stop trails 1 step behind": ("ladder", 0.75, None),
         "25% every 1R, stop trails 1 step behind": ("ladder", 1.0, None)}


def trades(path, side, sp, floor):
    global GH, GL, GC
    d = pd.read_csv(path, parse_dates=["time"])
    GH, GL, GC = d.high.values, d.low.values, d.close.values
    pc = d["close"].shift(1)
    d["atr"] = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    out = []
    for day, g in d.groupby(d.time.dt.normalize()):
        h = g.time.dt.hour * 60 + g.time.dt.minute
        rng = g[(h >= 960) & (h < 1035)]
        if len(rng) < 15:
            continue
        hi, lo = rng.high.max(), rng.low.min()
        after = g[(h >= 1035)]
        hh = after.time.dt.hour * 60 + after.time.dt.minute
        O, H, L, C, A = (after[c].values for c in ("open", "high", "low", "close", "atr"))
        gi = after.index.values
        for i in range(len(after) - 1):
            if hh.iloc[i] >= 1380:
                break
            if (NOSIGNAL and i == 0) or (not NOSIGNAL and ((side == 1 and C[i] > hi) or (side == -1 and C[i] < lo))):
                buf = max(A[i], floor)
                e = O[i + 1] + (sp if side == 1 else 0)
                stop = lo - buf if side == 1 else hi + buf
                risk = (e - stop) * side
                if risk <= 0:
                    break
                mm = (hi - lo) / risk           # measured move in R
                # path in R from entry, bar by bar (bid data; shorts close at ask)
                adj = 0 if side == 1 else sp
                if HOLD_DAYS:
                    j0 = gi[i + 1]; j1 = min(len(GH), j0 + 288 * HOLD_DAYS)
                    PH, PL, PC = GH[j0:j1], GL[j0:j1], GC[j0:j1]
                else:
                    PH, PL, PC = H[i + 1:], L[i + 1:], C[i + 1:]
                fav = ((PH - e) if side == 1 else (e - (PL + adj))) / risk
                adv = ((PL - e) if side == 1 else (e - (PH + adj))) / risk
                cl = ((PC - e) if side == 1 else (e - (PC + adj))) / risk
                out.append((day, mm, adv, fav, cl, after.time.iloc[i + 1]))
                break
    return out


def exit_r(adv, fav, cl, mm, kind, trig, tgt):
    if kind == "partial":
        done = False
        for a, f in zip(adv, fav):
            if not done:
                if a <= -1: return -1.0
                if f >= trig:
                    done = True
                    if f >= mm: return 0.5 * trig + 0.5 * min(mm, 4) if mm >= trig else trig
                    continue
            else:
                if a <= 0: return 0.5 * trig
                if f >= min(mm, 4): return 0.5 * trig + 0.5 * min(mm, 4)
        return (0.5 * trig + 0.5 * cl[-1]) if done else cl[-1]
    if kind == "ladder":   # close 25% at step, 2*step, 3*step, 4*step; after the k-th close the stop moves to (k-1)*step
        got, left, stop, k = 0.0, 1.0, -1.0, 0
        for a, f in zip(adv, fav):
            if a <= stop:
                return got + left * stop
            while k < 4 and f >= (k + 1) * trig:
                k += 1; got += 0.25 * k * trig; left -= 0.25; stop = (k - 1) * trig
                if k == 4:
                    return got
        return got + left * cl[-1]
    if kind == "be":
        stop = -1.0
        for a, f in zip(adv, fav):
            if a <= stop: return stop
            if f >= tgt: return tgt
            if f >= trig: stop = 0.0
        return cl[-1]
    t = mm if kind == "mm" else tgt
    for a, f in zip(adv, fav):
        if a <= -1: return -1.0
        if f >= t: return t
    return cl[-1]


import sys
HOLD_DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 0
NOSIGNAL = "nosignal" in sys.argv     # baseline: enter every day at 17:15 server in the same direction, no breakout needed
if "only" in sys.argv:
    MK = {k: v for k, v in MK.items() if k in sys.argv}   # 0 = close at 23:55 server; N = hold up to N days (no time close)
print("time exit:", "23:55 server" if not HOLD_DAYS else f"none (held up to {HOLD_DAYS} days)")
for m, (p, side, sp, fl) in MK.items():
    tr = trades(p, side, sp, fl)
    yrs = (tr[-1][0] - tr[0][0]).days / 365.25
    print(f"\n{m} {'long' if side == 1 else 'short'} only, {len(tr)} trades {tr[0][0]:%Y}-{tr[-1][0]:%Y}, median measured move {np.median([t[1] for t in tr]):.2f}R")
    for lab, (k, a, b) in EXITS.items():
        r = np.array([exit_r(t[2], t[3], t[4], t[1], k, a, b) for t in tr])
        w, l = r[r > 0], r[r <= 0]
        h = len(r) // 2
        print(f"  {lab:<46} win {np.mean(r>0)*100:3.0f}%  avg win {w.mean():+.2f}R  avg loss {l.mean():+.2f}R  "
              f"mean {r.mean():+.3f}R  t {r.mean()/r.std(ddof=1)*np.sqrt(len(r)):+.2f}  halves {r[:h].mean():+.3f}/{r[h:].mean():+.3f}")
