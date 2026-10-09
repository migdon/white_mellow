"""
Noise-Area intraday momentum backtest (NBRO's rule), for ANY symbol and ANY session anchor.

Rule (identical to nbro_app.py, EXIT_READING = "X2"):
  session open O = the M5 bar at the anchor time (e.g. 09:30 New York for US indices)
  every 30 min from O+30 to O+360:
    sigma(k) = mean over the previous 14 COMPLETE sessions of |price at O+m_k / that session's open - 1|
    UPPER = max(open, prev close) * (1 + sigma(k))      LOWER = min(open, prev close) * (1 - sigma(k))
    VWAP  = sum((H+L+C)/3 * vol) / sum(vol) over bars [O, check)
    flat: P > UPPER -> long, P < LOWER -> short   (P = open of the check bar)
    long exits when P < min(UPPER, VWAP); short exits when P > max(LOWER, VWAP); re-entry allowed at a LATER check
  everything closes at the open of the bar at O+385; broker-side emergency stop at stop_pct of entry.

Returns are % of notional at 1x (scale-free), net of spread (data = BID prices, so one spread
per round trip) and commission.

Times: MT5 bars are in broker server time. `server_tz`:
  "ny+7"   server clock = New York + 7h all year (Atlas / most NY-close brokers)
  "utc+N"  fixed offset from UTC
"""

from dataclasses import dataclass, field
from datetime import time as dtime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NY = ZoneInfo("America/New_York")
CHECKS = tuple(range(30, 361, 30))
END_MIN = 385
LOOKBACK = 14


@dataclass
class Spec:
    symbol: str
    anchor_tz: str = "America/New_York"
    anchor: str = "09:30"
    spread: float = 0.0            # in price units (e.g. 0.00004 for 0.4 pip EURUSD)
    commission_frac: float = 0.0   # round-trip commission as fraction of notional
    stop_pct: float = 1.0          # emergency stop, % of entry price


def load_mt5_m5(path: str, server_tz: str = "ny+7") -> pd.DataFrame:
    """CSV with time,open,high,low,close and tick_volume or real_volume/volume. Adds tz-aware UTC 'utc' column."""
    d = pd.read_csv(path)
    d["time"] = pd.to_datetime(d["time"])
    vol = next((c for c in ("real_volume", "volume", "tick_volume") if c in d and d[c].sum() > 0), None)
    d["volume"] = d[vol].astype(float) if vol else 1.0
    if server_tz == "ny+7":
        loc = (d["time"] - pd.Timedelta(hours=7)).dt.tz_localize(NY, ambiguous="NaT", nonexistent="NaT")
        d["utc"] = loc.dt.tz_convert("UTC")
    elif server_tz.startswith("utc"):
        off = float(server_tz[3:] or 0)
        d["utc"] = (d["time"] - pd.Timedelta(hours=off)).dt.tz_localize("UTC")
    else:
        raise ValueError(server_tz)
    d = d.dropna(subset=["utc"]).drop_duplicates("utc").sort_values("utc")
    return d[["utc", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def _sessions(df: pd.DataFrame, spec: Spec) -> List[dict]:
    """Slice the bars into sessions [O, O+385] in the anchor's local time (DST-correct)."""
    tz = ZoneInfo(spec.anchor_tz)
    hh, mm = map(int, spec.anchor.split(":"))
    loc = df["utc"].dt.tz_convert(tz)
    dates = pd.Index(loc.dt.date.unique())
    idx = pd.DatetimeIndex(df["utc"])
    out = []
    for d in dates:
        o = pd.Timestamp(pd.Timestamp.combine(d, dtime(hh, mm)), tz=tz).tz_convert("UTC")
        e = o + pd.Timedelta(minutes=END_MIN)
        a, b = idx.searchsorted(o), idx.searchsorted(e, side="right")
        if b <= a:
            continue
        g = df.iloc[a:b]
        out.append({"date": d, "o": o, "e": e, "bars": g})
    return out


def run(df: pd.DataFrame, spec: Spec) -> pd.DataFrame:
    """One row per trade: date, dir, entry_ts, exit_ts, entry, exit, reason, ret (net, fraction of notional)."""
    sess = _sessions(df, spec)
    offs = [pd.Timedelta(minutes=m) for m in CHECKS]
    trades = []
    hist = []          # sigma rows of complete sessions, most recent last
    prev_close = None
    for s in sess:
        g, o, e = s["bars"], s["o"], s["e"]
        px = pd.Series(g["open"].values, index=g["utc"])
        complete = (g["utc"].iloc[0] == o and g["utc"].iloc[-1] >= e - pd.Timedelta(minutes=5)
                    and all((o + f) in px.index for f in offs))
        ready = len(hist) >= LOOKBACK and prev_close is not None and g["utc"].iloc[0] == o
        if ready:
            trades += _trade_session(g, o, e, px, np.mean(hist[-LOOKBACK:], axis=0),
                                     float(g["open"].iloc[0]), prev_close, spec, s["date"])
        if complete:
            op = float(g["open"].iloc[0])
            hist.append([abs(float(px[o + f]) / op - 1.0) for f in offs])
        prev_close = float(g["close"].iloc[-1])
    return pd.DataFrame(trades)


def _trade_session(g, o, e, px, sigma, op, prev, spec, date) -> list:
    hi, lo = max(op, prev), min(op, prev)
    t = [pd.Timestamp(x) for x in g["utc"]]
    pos_of = {ts: i for i, ts in enumerate(t)}
    typ = ((g["high"] + g["low"] + g["close"]) / 3.0).values * g["volume"].values
    cumv, cumtp = np.cumsum(g["volume"].values), np.cumsum(typ)
    H, L, Op, C = g["high"].values, g["low"].values, g["open"].values, g["close"].values
    stop = spec.stop_pct / 100.0
    out, pos = [], None
    nxt = 0                                   # first bar not yet scanned for the stop

    def book(i, price, reason):
        r = pos["dir"] * (price / pos["entry"] - 1.0) - spec.spread / pos["entry"] - spec.commission_frac
        out.append({"date": date, "dir": pos["dir"], "entry_ts": pos["ts"], "exit_ts": t[i],
                    "entry": pos["entry"], "exit": price, "reason": reason, "ret": r})

    def stopped(upto) -> bool:
        """Scan bars [nxt, upto) for the broker-side stop."""
        nonlocal pos, nxt
        for j in range(nxt, upto):
            if pos["dir"] > 0 and L[j] <= pos["sl"]:
                book(j, min(Op[j], pos["sl"]), "stop"); pos = None; nxt = upto; return True
            if pos["dir"] < 0 and H[j] >= pos["sl"]:
                book(j, max(Op[j], pos["sl"]), "stop"); pos = None; nxt = upto; return True
        nxt = max(nxt, upto)
        return False

    for k, m in enumerate(CHECKS):
        i = pos_of.get(o + pd.Timedelta(minutes=m))
        if i is None:
            continue
        if pos is not None:
            stopped(i)
        P = Op[i]
        vwap = cumtp[i - 1] / cumv[i - 1] if i > 0 and cumv[i - 1] > 0 else op
        UB, LB = hi * (1 + sigma[k]), lo * (1 - sigma[k])
        if pos is not None:
            line = min(UB, vwap) if pos["dir"] > 0 else max(LB, vwap)
            if (pos["dir"] > 0 and P < line) or (pos["dir"] < 0 and P > line):
                book(i, P, "exit"); pos = None
                continue                      # no re-entry at the same check
        if pos is None:
            d = 1 if P > UB else (-1 if P < LB else 0)
            if d:
                pos = {"dir": d, "entry": P, "ts": t[i], "sl": P * (1 - stop) if d > 0 else P * (1 + stop)}
                nxt = i                       # the entry bar itself can hit the stop
    if pos is not None:
        j = pos_of.get(e)
        if j is not None:
            if not stopped(j):
                book(j, Op[j], "eod")
        elif not stopped(len(t)):             # session cut short (holiday)
            book(len(t) - 1, float(C[-1]), "eod_short")
    return out


# ----------------------------------------------------------------------------- stats
def daily(trades: pd.DataFrame, all_days: Optional[pd.Index] = None) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float)
    s = trades.groupby("date")["ret"].sum()
    if all_days is not None:
        s = s.reindex(all_days, fill_value=0.0)
    return s


def summary(trades: pd.DataFrame, days: pd.Index) -> Dict:
    if trades.empty:
        return {"trades": 0}
    dly = daily(trades, days)
    x = dly.values
    n = len(x)
    e = x - x.mean()
    s2 = e @ e / n
    for L_ in range(1, 6):
        s2 += 2 * (1 - L_ / 6) * (e[L_:] @ e[:-L_]) / n
    yrs = trades.assign(y=pd.to_datetime(trades["date"]).dt.year).groupby("y")["ret"].sum()
    return {
        "trades": int(len(trades)), "per_day": len(trades) / max(n, 1),
        "avg_trade_pct": float(trades["ret"].mean() * 100),
        "win": float((trades["ret"] > 0).mean()),
        "z": float(x.mean() / np.sqrt(s2 / n)) if s2 > 0 else float("nan"),
        "sharpe_1x": float(x.mean() / x.std() * np.sqrt(252)) if x.std() > 0 else float("nan"),
        "worst_day_pct_1x": float(x.min() * 100),
        "years_pos": f"{int((yrs > 0).sum())}/{len(yrs)}",
        "stops": int((trades["reason"] == "stop").sum()),
    }
