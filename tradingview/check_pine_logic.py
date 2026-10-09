"""
Line-by-line Python port of tradingview/nbro_noise_area.pine, compared trade-for-trade with
noise_fx.noise_backtest (which matches nbro_app.py). Run:
    python -m tradingview.check_pine_logic --data NAS100.r_M5.csv
"""
import argparse

import numpy as np
import pandas as pd

from noise_fx.noise_backtest import Spec, load_mt5_m5, run

NCHK, END = 12, 385


def pine_port(df, lookback=14, stop_pct=1.0):
    ny = df["utc"].dt.tz_convert("America/New_York")
    t0 = ny.dt.normalize() + pd.Timedelta(hours=9, minutes=30)
    M = ((ny - t0).dt.total_seconds() // 60).astype(int).values
    day = ny.dt.date.values
    O, H, L, C, V = (df[c].values for c in ("open", "high", "low", "close", "volume"))
    s_open = s_day = prev_close = last_close = None
    win_close = win_day = None
    reached = False
    moves = [None] * NCHK
    hist = []
    cpv = cv = 0.0
    pos, entry, stop, entry_ts = 0, None, None, None
    last_i = 0
    trades = []

    def close(i, px, why):
        nonlocal pos
        j = last_i if why == "eod_short" else i
        trades.append((entry_ts, df["utc"].iloc[j], pos, why))
        pos = 0

    for i in range(len(df)):
        m = M[i]
        if pos != 0 and (s_day != day[i] or m > END):
            close(i, last_close, "eod_short")
        if m == 0:
            if s_open is not None and reached and all(x is not None for x in moves):
                hist.append(list(moves))
                hist = hist[-lookback:]
            if win_close is not None and win_day != day[i]:
                prev_close = win_close
            s_open, s_day, reached = O[i], day[i], False
            moves = [None] * NCHK
            cpv = cv = 0.0
        in_sess = s_open is not None and s_day == day[i] and 0 <= m <= END
        if 0 <= m <= END:
            win_close, win_day = C[i], day[i]
        if not in_sess:
            continue
        ready = len(hist) >= lookback and prev_close is not None
        hi, lo = max(s_open, prev_close or s_open), min(s_open, prev_close or s_open)
        vwap_prev = cpv / cv if cv > 0 else s_open
        k = m // 30 - 1 if (m % 30 == 0 and 30 <= m <= 360) else -1
        if k >= 0:
            moves[k] = abs(O[i] / s_open - 1)
        if m == END and pos != 0:
            close(i, O[i], "eod")
        exited = False
        if k >= 0 and ready and m < END:
            sig = float(np.mean([h[k] for h in hist]))
            ub, lb = hi * (1 + sig), lo * (1 - sig)
            P = O[i]
            if pos != 0:
                line = min(ub, vwap_prev) if pos > 0 else max(lb, vwap_prev)
                if (pos > 0 and P < line) or (pos < 0 and P > line):
                    close(i, P, "exit")
                    exited = True
            if pos == 0 and not exited:
                d = 1 if P > ub else (-1 if P < lb else 0)
                if d:
                    pos, entry, entry_ts = d, P, df["utc"].iloc[i]
                    stop = P * (1 - stop_pct / 100) if d > 0 else P * (1 + stop_pct / 100)
        if pos != 0 and m < END:
            if (pos > 0 and L[i] <= stop) or (pos < 0 and H[i] >= stop):
                close(i, None, "stop")
        cpv += (H[i] + L[i] + C[i]) / 3 * V[i]
        cv += V[i]
        last_close, last_i = C[i], i
        if m >= END - 5:
            reached = True
    return trades


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    df = load_mt5_m5(a.data)
    df = df[df["utc"] >= df["utc"][df["utc"].diff().dt.total_seconds() == 300].iloc[0]].reset_index(drop=True)
    pine = [(e, x, d, w) for e, x, d, w in pine_port(df)]
    eng = run(df, Spec("X", "America/New_York", "09:30", stop_pct=1.0))
    ref = [(r.entry_ts, r.exit_ts, r.dir, r.reason) for r in eng.itertuples()]
    ps, rs = set(pine), set(ref)
    print(f"pine port {len(pine)} trades, engine {len(ref)} trades, identical {len(ps & rs)}")
    for x in sorted(ps - rs)[:5]:
        print("  only pine  ", x)
    for x in sorted(rs - ps)[:5]:
        print("  only engine", x)


if __name__ == "__main__":
    main()
