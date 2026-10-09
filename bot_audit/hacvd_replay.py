"""
Replay hacvd_app.py's OWN process_bar() over M5 history, then re-price every trade at prices you could
actually have traded.

    python -m bot_audit.hacvd_replay --bot path/to/hacvd_app.py --data XAUUSD_M5.csv [--from 2025-01-01]

"As designed": the bot's own bookkeeping. Entries and exits are at the Heikin-Ashi close
(O+H+L+C)/4 of the signal bar, which is not a price that ever traded.
"Real": the same decisions, executed at the NEXT bar's open (the earliest a live bot can act after a bar
closes). Data are BID prices, so a buy pays the spread on entry and a sell pays it on exit. The broker-side
stop is hit by the real high/low; trailing moves decided at a bar's close apply from the next bar.
"""

import argparse
import importlib.util
import sys

import numpy as np
import pandas as pd

from noise_fx.noise_backtest import load_mt5_m5


def load_bot(path):
    spec = importlib.util.spec_from_file_location("hacvd_bot", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["hacvd_bot"] = m               # dataclasses look the module up while it loads
    spec.loader.exec_module(m)
    m.log_event = lambda *a, **k: None          # silence per-bar logging
    return m


def replay(hm, df: pd.DataFrame, symbol="XAUUSD", equity=50000.0):
    ha = hm.heikin_ashi(df)
    cvd = hm.session_anchored_cvd(df)
    atr_s = hm.atr(ha.rename(columns={"ha_high": "high", "ha_low": "low", "ha_close": "close"}))
    base = atr_s.rolling(hm.DYNAMIC_DECAY_ATR_LOOKBACK).mean()
    ma = hm.moving_average(ha["ha_close"], hm.MA_PERIOD)
    _, up, lo = hm.session_vwap_and_bands(df)
    st = hm.BotState()
    n = len(df)
    stop_main = np.full(n, np.nan)
    stop_abs = np.full(n, np.nan)
    for i in range(max(hm.MA_PERIOD, 60), n):
        hm.process_bar(st, ha, cvd, i, symbol, equity, atr_series=atr_s, vwap_upper=up, vwap_lower=lo,
                       atr_baseline_series=base, ma_series=ma)
        if st.open_trade is not None:
            stop_main[i] = st.open_trade.stop_price
        if st.open_absorption_trade is not None:
            stop_abs[i] = st.open_absorption_trade.stop_price
    return pd.DataFrame(st.closed_trades), ha, stop_main, stop_abs


def reprice(trades, df, stop_main, stop_abs, spread):
    idx = {t: i for i, t in enumerate(df.index)}
    O, H, L = df["open"].values, df["high"].values, df["low"].values
    out = []
    for r in trades.itertuples():
        e, x = idx[r.entry_time], idx[r.exit_time]
        if x + 1 >= len(df) or e + 1 >= len(df):
            continue
        buy = r.direction == "BUY"
        strat = getattr(r, "strategy", None)
        strat = "absorption" if strat == "absorption" else "breakout"
        stops = stop_abs if strat == "absorption" else stop_main
        orig_stop = stops[e]
        entry = O[e + 1] + (spread if buy else 0.0)
        risk = abs(entry - orig_stop)
        exitp, why = None, r.reason
        for k in range(e + 1, x + 1):
            s = stops[k - 1]
            if buy and L[k] <= s:
                exitp, why = min(O[k], s), "stop"
                break
            if not buy and H[k] + spread >= s:
                exitp, why = max(O[k] + spread, s), "stop"
                break
        if exitp is None:
            exitp = O[x + 1] + (0.0 if buy else spread)
        pnl = (exitp - entry) if buy else (entry - exitp)
        out.append({"entry_time": r.entry_time, "direction": r.direction, "strategy": strat,
                    "R_design": r.r_multiple, "R_real": pnl / risk if risk > 0 else 0.0, "reason_real": why})
    return pd.DataFrame(out)


def stats(x: pd.Series) -> str:
    x = x.dropna()
    if len(x) < 2:
        return "n/a"
    z = x.mean() / x.std() * np.sqrt(len(x))
    return f"n {len(x):>5}  avg {x.mean():+.3f}R  z {z:+.2f}  total {x.sum():+.1f}R"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--server-tz", default="ny+7")
    ap.add_argument("--from", dest="start", default=None)
    ap.add_argument("--to", dest="end", default=None, help="exclusive end date (run years in parallel: the bot's "
                    "daily-loss guard rescans every closed trade on every bar, so one long run is O(bars x trades))")
    ap.add_argument("--spread", type=float, nargs="*", default=[0.18, 0.30, 0.45])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    hm = load_bot(a.bot)
    d = load_mt5_m5(a.data, a.server_tz)
    d = d.set_index(pd.DatetimeIndex(d["utc"])).drop(columns="utc")          # tz-aware UTC, like fetch_bars()
    d = d[d.index.to_series().diff().dt.total_seconds().fillna(300) <= 3 * 86400]   # drop daily-bar prehistory gaps
    first_m5 = d.index[d.index.to_series().diff().dt.total_seconds() == 300][0]
    d = d[d.index >= first_m5]
    if a.start:
        d = d[d.index >= pd.Timestamp(a.start, tz="UTC")]
    if a.end:
        d = d[d.index < pd.Timestamp(a.end, tz="UTC")]
    d = d.rename(columns={"volume": "tick_volume"})
    d["real_volume"] = 0.0
    print(f"bars {len(d):,}  {d.index[0]} -> {d.index[-1]}  (UTC)")
    trades, ha, sm, sa = replay(hm, d)
    print(f"bot closed {len(trades)} trades")
    for sp in a.spread:
        rp = reprice(trades, d, sm, sa, sp)
        print(f"\nspread ${sp:.2f}")
        for name, g in [("ALL", rp)] + list(rp.groupby("strategy")):
            print(f"  {name:<11} as designed: {stats(g.R_design)}")
            print(f"  {'':<11} real prices: {stats(g.R_real)}")
        if a.out and sp == a.spread[0]:
            rp.to_csv(a.out, index=False)
    rp = reprice(trades, d, sm, sa, a.spread[0])
    rp["y"] = pd.to_datetime(rp.entry_time).dt.year
    print("\nby year (first spread), real prices:")
    print(rp.groupby("y").R_real.agg(["count", "mean", "sum"]).round(3).to_string())


if __name__ == "__main__":
    main()
