"""
Measure the REAL spread (and swap) of symbols at your broker, from MT5's own tick history.

    python measure_spread.py                      # BTCUSD, XAUUSD, NAS100, SPX500, last 7 days
    python measure_spread.py --days 14 --symbols BTCUSD ETHUSD
    python measure_spread.py --mt5-path "C:\\...\\terminal64.exe"

Open MT5, log in to the Atlas account, then run it. It prints, per symbol:
  spread now, median / average / 90th percentile over the period, and the median per server hour,
  the contract size, and the swap long/short.
It also writes spread_report.csv next to this file. Send me the printed text (or the csv).
Nothing is traded.
"""

import argparse
import os
from datetime import datetime, timedelta, timezone

import numpy as np

try:
    import MetaTrader5 as mt5
except ImportError:
    raise SystemExit("pip install MetaTrader5")

NAMES = {"BTCUSD": ["BTCUSD", "BTCUSD.r", "BTCUSDT", "BITCOIN", "BTC/USD"],
         "ETHUSD": ["ETHUSD", "ETHUSD.r", "ETHEREUM"],
         "XAUUSD": ["XAUUSD", "GOLD", "XAUUSD.r"],
         "NAS100": ["NAS100", "US100", "USTEC", "NAS100.r"],
         "SPX500": ["SPX500", "US500", "SP500", "SP500.r"]}
SWAP_MODES = {0: "disabled", 1: "points", 2: "base currency", 3: "margin currency", 4: "deposit currency",
              5: "% of current price", 6: "% of open price", 7: "reopen at close", 8: "reopen at bid"}


def resolve(sym):
    for n in [sym] + NAMES.get(sym, []):
        if mt5.symbol_select(n, True):
            return n
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["BTCUSD", "XAUUSD", "NAS100", "SPX500"])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--mt5-path", default=None)
    a = ap.parse_args()
    if not (mt5.initialize(path=a.mt5_path) if a.mt5_path else mt5.initialize()):
        raise SystemExit(f"MT5 init failed: {mt5.last_error()}  (is MT5 open and logged in?)")
    acc = mt5.account_info()
    print(f"Account {acc.login} @ {acc.server}  ({acc.company})\n")
    rows = []
    to = datetime.now(timezone.utc) + timedelta(days=1)
    frm = to - timedelta(days=a.days + 1)
    for s in a.symbols:
        n = resolve(s)
        if not n:
            print(f"{s}: NOT FOUND at this broker\n")
            continue
        info, tick = mt5.symbol_info(n), mt5.symbol_info_tick(n)
        ticks = mt5.copy_ticks_range(n, frm, to, mt5.COPY_TICKS_INFO)
        now_sp = (tick.ask - tick.bid) if tick else float("nan")
        print(f"=== {s} (broker name {n})  digits {info.digits}  contract size {info.trade_contract_size}  "
              f"min lot {info.volume_min}")
        print(f"    swap long {info.swap_long}  swap short {info.swap_short}  ({SWAP_MODES.get(info.swap_mode, info.swap_mode)}), "
              f"triple swap on day {info.swap_rollover3days}")
        print(f"    spread now {now_sp:.{info.digits}f}  (price {tick.bid if tick else 'n/a'})")
        if ticks is None or len(ticks) == 0:
            print(f"    no tick history returned ({mt5.last_error()}); open a chart of {n} for a while and run again\n")
            continue
        sp = ticks["ask"] - ticks["bid"]
        ok = (ticks["ask"] > 0) & (ticks["bid"] > 0) & (sp >= 0)
        sp, t, bid = sp[ok], ticks["time"][ok], ticks["bid"][ok]
        hours = (t % 86400) // 3600
        med, avg, p90 = np.median(sp), sp.mean(), np.percentile(sp, 90)
        pct = med / np.median(bid) * 100
        print(f"    {len(sp):,} ticks over {a.days} days: median {med:.{info.digits}f}  average {avg:.{info.digits}f}  "
              f"90% {p90:.{info.digits}f}   (median = {pct:.4f}% of price)")
        per_h = []
        for h in range(24):
            x = sp[hours == h]
            if len(x):
                per_h.append(f"{h:02d}:{np.median(x):.{min(info.digits, 2)}f}")
                rows.append((s, n, h, len(x), float(np.median(x)), float(x.mean()), float(np.percentile(x, 90))))
        print("    median by SERVER hour: " + "  ".join(per_h) + "\n")
        rows.append((s, n, "all", len(sp), float(med), float(avg), float(p90)))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spread_report.csv")
    with open(out, "w") as f:
        f.write("symbol,broker_name,server_hour,ticks,median_spread,avg_spread,p90_spread\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")
    print(f"Saved {out}")
    mt5.shutdown()


if __name__ == "__main__":
    main()
