"""
Independent backtest of EMBER's rule (ember_app.py) on MT5 M5 data, at tradable prices.

  day       = broker server day (server time = New York + 7h: midnight = 17:00 New York)
  levels    = day's first-bar open +/- 0.8 x ATR(10) of the 10 COMPLETE days before (no lookahead)
  entry     = the first level touched that day (stop order: fills at the level, at the open if price gapped through)
  stop      = level -/+ 2 x ATR(10)
  exit      = at the start of the second server day after entry (= "close of the day after entry");
              USDJPY waits until 01:05 server time (exit_delay_min=65) and, like the live bot, does not trade a level
              that was crossed during that wait
  one position at a time per market; data are BID: a long pays the spread at entry, a short pays it at exit
  both levels inside one M5 bar (rare): the side nearer the bar's open is taken, and the same bar is checked for the stop

Returns one row per trade with R (P&L / 2xATR) plus the per-bar marks needed by the Atlas simulation.
"""

import numpy as np
import pandas as pd

STRETCH, ATR_N, STOP_MULT = 0.8, 10, 2.0


def load_server_m5(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=["time"])
    first = d["time"][d["time"].diff().dt.total_seconds() == 300].iloc[0]
    d = d[d["time"] >= first].reset_index(drop=True)
    d["day"] = d["time"].dt.normalize()
    return d


def run(m5: pd.DataFrame, spread: float, exit_delay_min: int = 0):
    daily = m5.groupby("day").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    pc = daily["close"].shift(1)
    tr = pd.concat([daily["high"] - daily["low"], (daily["high"] - pc).abs(), (daily["low"] - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(ATR_N).mean().shift(1)
    days = list(daily.index)
    starts = m5.groupby("day").indices
    T, O, H, L = m5["time"].values, m5["open"].values, m5["high"].values, m5["low"].values
    mins = (m5["time"].dt.hour * 60 + m5["time"].dt.minute).values

    trades = []
    pos = None            # dict(dir, entry, sl, risk, entry_day_i, entry_bar)
    for di, day in enumerate(days):
        idx = starts[day]
        first, last = idx[0], idx[-1]
        scan_from = first
        # ---- exit due: start of the 2nd day after entry
        if pos is not None and di >= pos["di"] + 2:
            j = first
            if exit_delay_min:
                while j <= last and mins[j] < exit_delay_min:
                    # the stop still protects it while it waits
                    if _stop_hit(pos, H[j], L[j], spread):
                        break
                    j += 1
            if j <= last and pos is not None:
                if _stop_hit(pos, H[j], L[j], spread) and (not exit_delay_min or mins[j] < exit_delay_min):
                    trades.append(_close(pos, _stop_px(pos, O[j], spread), T[j], "stop"))
                else:
                    px = O[j] + (spread if pos["dir"] < 0 else 0.0)
                    trades.append(_close(pos, px, T[j], "next_day_close"))
                pos = None
                scan_from = j
        # ---- open position: stop checks through the day
        if pos is not None:
            for j in range(scan_from, last + 1):
                if _stop_hit(pos, H[j], L[j], spread):
                    trades.append(_close(pos, _stop_px(pos, O[j], spread), T[j], "stop"))
                    pos = None
                    break
            continue                       # still in a trade (or just stopped): no new levels today
        a = atr.iloc[di]
        if pd.isna(a) or a <= 0:
            continue
        op = O[first]
        up, dn, risk = op + STRETCH * a, op - STRETCH * a, STOP_MULT * a
        # a level crossed while an exit was waiting is not traded (live bot: day_skipped)
        if scan_from > first and (H[first:scan_from].max() >= up or L[first:scan_from].min() <= dn):
            continue
        for j in range(scan_from, last + 1):
            if pos is None:
                hit_u, hit_d = H[j] >= up, L[j] <= dn
                if hit_u or hit_d:
                    if hit_u and hit_d:
                        d = 1 if abs(O[j] - up) <= abs(O[j] - dn) else -1
                    else:
                        d = 1 if hit_u else -1
                    lvl = up if d > 0 else dn
                    fill = max(O[j], lvl) if d > 0 else min(O[j], lvl)     # gap through the level fills at the open
                    entry = fill + (spread if d > 0 else 0.0)
                    pos = dict(dir=d, entry=entry, sl=lvl - d * risk, risk=risk, di=di, t=T[j])
                    if _stop_hit(pos, H[j], L[j], spread):      # same bar also reached the stop: assume entry first, then stop
                        trades.append(_close(pos, pos["sl"], T[j], "stop"))
                        pos = None
                        break
            else:
                if _stop_hit(pos, H[j], L[j], spread):
                    trades.append(_close(pos, _stop_px(pos, O[j], spread), T[j], "stop"))
                    pos = None
                    break
    return pd.DataFrame(trades)


def _stop_hit(p, h, l, spread):
    return (p["dir"] > 0 and l <= p["sl"]) or (p["dir"] < 0 and h + spread >= p["sl"])


def _stop_px(p, o, spread):
    return min(o, p["sl"]) if p["dir"] > 0 else max(o + spread, p["sl"])


def _close(p, px, t, why):
    pnl = (px - p["entry"]) * p["dir"]
    return {"entry_time": pd.Timestamp(p["t"]), "exit_time": pd.Timestamp(t), "dir": p["dir"], "entry": p["entry"],
            "exit": px, "risk": p["risk"], "R": pnl / p["risk"], "reason": why}


def summary(tr: pd.DataFrame) -> str:
    x = tr["R"]
    z = x.mean() / x.std() * np.sqrt(len(x))
    return (f"n {len(x):>4}  win {(x > 0).mean():.0%}  avg {x.mean():+.3f}R  z {z:+.2f}  total {x.sum():+.1f}R  "
            f"worst {x.min():+.2f}R")
